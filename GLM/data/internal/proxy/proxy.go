package proxy

import (
	"bufio"
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"mistral-reverse-proxy/internal/config"
	"mistral-reverse-proxy/internal/httpx"
	"mistral-reverse-proxy/internal/keys"
)

// glmModelRE 匹配 glm-5-2 的常见变体写法，统一映射到上游真实模型名。
var glmModelRE = regexp.MustCompile(`(?i)^(zai-)?glm[._-]?5[._-]?2(-latest)?$`)

// playgroundTools 对应 Playground 会话中的内置工具。
// chat/completions 接口只接受 function 格式的工具，因此把 Playground 的内置工具
// 描述为 function schema；code_interpreter/image_generation 由上游按名识别。
var playgroundTools = []any{
	map[string]any{"type": "function", "function": map[string]any{
		"name":        "code_interpreter",
		"description": "在沙盒中执行 Python 代码并返回结果",
		"parameters":  map[string]any{"type": "object", "properties": map[string]any{}},
	}},
	map[string]any{"type": "function", "function": map[string]any{
		"name":        "image_generation",
		"description": "根据描述生成一张图片",
		"parameters":  map[string]any{"type": "object", "properties": map[string]any{}},
	}},
	map[string]any{"type": "function", "function": map[string]any{
		"name":        "web_search",
		"description": "搜索互联网并返回相关结果",
		"parameters":  map[string]any{"type": "object", "properties": map[string]any{}},
	}},
}

// playgroundBareTools Conversations API 的裸类型工具格式（与 Playground 会话一致）。
var playgroundBareTools = []any{
	map[string]any{"type": "code_interpreter"},
	map[string]any{"type": "image_generation"},
	map[string]any{"type": "web_search", "open_results": false},
}

const maxBodySize = 16 << 20 // 本地请求体上限 16MB

// conversation 本地会话历史缓存（按 conversation_id 索引）。
type conversation struct {
	ID        string    `json:"conversation_id"`
	Model     string    `json:"model"`
	CreatedAt time.Time `json:"created_at"`
	Messages  []any     `json:"messages"`
}

// Proxy 核心反向代理。
type Proxy struct {
	cfg       *config.Config
	pool      *keys.Pool
	proxyPool *Pool
	client    *http.Client
	sysPrompt string

	sysPromptMu sync.RWMutex

	convMu    sync.Mutex
	convs     map[string]*conversation
	convOrder []string

	// sessionMu 保护 sessionMap：X-Session-ID → conversation_id。
	// 客户端用任意稳定的 session 标识即可让代理自动延续会话，无需手动传 conversation_id。
	// sessionMap 持久化到 <DataDir>/sessions.json，重启不丢；sessionLocks 串行化同一 session 的并发请求。
	sessionMu     sync.Mutex
	sessionMap    map[string]string
	sessionLocks  map[string]*sync.Mutex
}

func New(cfg *config.Config, pool *keys.Pool, pp *Pool, sysPrompt string) *Proxy {
	p := &Proxy{
		cfg:       cfg,
		pool:      pool,
		proxyPool: pp,
		client: &http.Client{
			Transport: pp.Transport(cfg.UpstreamProxy),
			Timeout:   cfg.HTTPTimeout,
		},
		sysPrompt:    sysPrompt,
		convs:        map[string]*conversation{},
		sessionMap:   map[string]string{},
		sessionLocks: map[string]*sync.Mutex{},
	}
	p.loadSessions()
	return p
}

// loadSessions 从 data/sessions.json 恢复 session → conversation_id 映射（进程重启不丢会话）。
func (p *Proxy) loadSessions() {
	if p.cfg.DataDir == "" {
		return
	}
	b, err := os.ReadFile(filepath.Join(p.cfg.DataDir, "sessions.json"))
	if err != nil {
		return
	}
	var m map[string]string
	if json.Unmarshal(b, &m) == nil && len(m) > 0 {
		p.sessionMu.Lock()
		p.sessionMap = m
		p.sessionMu.Unlock()
	}
}

// saveSessions 持久化 sessionMap 到 data/sessions.json（原子写）。
func (p *Proxy) saveSessions() {
	if p.cfg.DataDir == "" {
		return
	}
	if err := os.MkdirAll(p.cfg.DataDir, 0o755); err != nil {
		return
	}
	b, _ := json.Marshal(p.sessionMap)
	tmp := filepath.Join(p.cfg.DataDir, "sessions.json.tmp")
	if os.WriteFile(tmp, b, 0o600) == nil {
		_ = os.Rename(tmp, filepath.Join(p.cfg.DataDir, "sessions.json"))
	}
}

// GetSysPrompt 返回当前默认系统提示词（可被页面运行时修改）。
func (p *Proxy) GetSysPrompt() string {
	p.sysPromptMu.RLock()
	defer p.sysPromptMu.RUnlock()
	return p.sysPrompt
}

// SetSysPrompt 设置默认系统提示词并持久化到 data/system_prompt.txt。
func (p *Proxy) SetSysPrompt(s string) error {
	p.sysPromptMu.Lock()
	p.sysPrompt = s
	p.sysPromptMu.Unlock()
	if p.cfg.DataDir == "" {
		return nil
	}
	if err := os.MkdirAll(p.cfg.DataDir, 0o755); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(p.cfg.DataDir, "system_prompt.txt"), []byte(s), 0o644)
}

// HandleChat 处理 POST /v1/chat/completions（非流式 + SSE 流式）。
func (p *Proxy) HandleChat(w http.ResponseWriter, r *http.Request) {
	raw, err := io.ReadAll(io.LimitReader(r.Body, maxBodySize))
	if err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "读取请求体失败: "+err.Error(), "bad_request")
		return
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "请求体不是合法 JSON: "+err.Error(), "bad_request")
		return
	}
	if err := p.prepareRequest(m); err != nil {
		httpx.WriteError(w, http.StatusBadRequest, err.Error(), "bad_request")
		return
	}

	stream := isStream(m)
	model, _ := m["model"].(string)
	convID, _ := m["conversation_id"].(string)

	// GLM 模型 + 有工具 → 走会话工具通道（passthrough 或 local 闭环）。
	// passthrough（默认）：GLM 返回 function.call 时转 tool_calls 交给客户端执行；local 由代理闭环执行。
	_, hasTools := m["tools"].([]any)
	if isGLMModel(model) && hasTools {
		m["stream"] = false
		b, cid, status, err := p.chatWithToolsMode(r.Context(), convID, m, p.cfg.ToolMode == "local")
		if err != nil {
			if status != 0 {
				p.writeUpstreamError(w, status, b)
			} else {
				httpx.WriteError(w, http.StatusBadGateway, "工具闭环失败: "+errText(err), "upstream_error")
			}
			return
		}
		if stream {
			// 用完整响应模拟流式 SSE 输出（含 tool_calls）
			p.writeSimulatedStream(w, r, b, model, cid)
		} else {
			p.writeConvertedResponse(w, r, b, model, cid)
		}
		return
	}

	resp, status, upstreamBody, lastErr := p.doUpstream(r.Context(), m)
	if resp == nil {
		if status != 0 {
			p.writeUpstreamError(w, status, upstreamBody)
		} else {
			httpx.WriteError(w, http.StatusBadGateway, "上游不可达: "+errText(lastErr), "upstream_unreachable")
		}
		return
	}
	defer resp.Body.Close()

	if stream {
		p.streamSSE(w, r, resp, m)
	} else {
		p.writeJSONResponse(w, r, resp, m)
	}
}

// writeConvertedResponse 非流式写 GLM 转换后的 OpenAI 响应（含 conversation_id）。
func (p *Proxy) writeConvertedResponse(w http.ResponseWriter, r *http.Request, b []byte, model, convID string) {
	var out map[string]any
	if err := json.Unmarshal(b, &out); err != nil {
		httpx.WriteError(w, http.StatusBadGateway, "响应解析失败: "+errText(err), "upstream_error")
		return
	}
	if convID != "" {
		out["conversation_id"] = convID
		w.Header().Set("X-Conversation-ID", convID)
	}
	httpx.WriteJSON(w, http.StatusOK, out)
}

// writeSimulatedStream 用完整 OpenAI 响应模拟 SSE 流式输出（含 tool_calls）。
func (p *Proxy) writeSimulatedStream(w http.ResponseWriter, r *http.Request, b []byte, model, convID string) {
	var comp struct {
		Choices []struct {
			Message struct {
				Content          string `json:"content"`
				ReasoningContent string `json:"reasoning_content"`
				ToolCalls        []struct {
					ID       string `json:"id"`
					Type     string `json:"type"`
					Function struct {
						Name      string `json:"name"`
						Arguments string `json:"arguments"`
					} `json:"function"`
				} `json:"tool_calls"`
			} `json:"message"`
			FinishReason string `json:"finish_reason"`
		} `json:"choices"`
	}
	_ = json.Unmarshal(b, &comp)
	text := ""
	reasoning := ""
	var toolCalls []struct {
		ID       string `json:"id"`
		Type     string `json:"type"`
		Function struct {
			Name      string `json:"name"`
			Arguments string `json:"arguments"`
		} `json:"function"`
	}
	finishReason := "stop"
	if len(comp.Choices) > 0 {
		text = comp.Choices[0].Message.Content
		reasoning = comp.Choices[0].Message.ReasoningContent
		toolCalls = comp.Choices[0].Message.ToolCalls
		finishReason = comp.Choices[0].FinishReason
		if finishReason == "" {
			finishReason = "stop"
		}
	}
	flusher, _ := w.(http.Flusher)
	h := w.Header()
	h.Set("Content-Type", "text/event-stream; charset=utf-8")
	h.Set("Cache-Control", "no-cache")
	h.Set("Connection", "keep-alive")
	h.Set("X-Accel-Buffering", "no")
	if convID != "" {
		h.Set("X-Conversation-ID", convID)
	}
	w.WriteHeader(http.StatusOK)
	writeSSE := func(payload map[string]any) {
		b, _ := json.Marshal(payload)
		fmt.Fprintf(w, "data: %s\n\n", string(b))
		if flusher != nil {
			flusher.Flush()
		}
	}
	// 思考文本（reasoning_content）作为 content 流式发送（客户端可忽略或显示）。
	if reasoning != "" {
		writeSSE(map[string]any{
			"id": "chatcmpl-" + convID, "object": "chat.completion.chunk", "created": time.Now().Unix(), "model": model,
			"choices": []any{map[string]any{"index": 0, "delta": map[string]any{"reasoning_content": reasoning}, "finish_reason": nil}},
		})
	}
	// 工具调用：首个 chunk 带完整 tool_calls（多数客户端要求首块完整）。
	if len(toolCalls) > 0 {
		tcs := make([]any, 0, len(toolCalls))
		for _, tc := range toolCalls {
			tcs = append(tcs, map[string]any{
				"id":       tc.ID,
				"type":     "function",
				"function": map[string]any{"name": tc.Function.Name, "arguments": tc.Function.Arguments},
			})
		}
		writeSSE(map[string]any{
			"id": "chatcmpl-" + convID, "object": "chat.completion.chunk", "created": time.Now().Unix(), "model": model,
			"choices": []any{map[string]any{"index": 0, "delta": map[string]any{"tool_calls": tcs}, "finish_reason": nil}},
		})
	}
	// 分块发送文本，模拟流式（按 rune 切块，避免切断 UTF-8 多字节字符）
	const chunkSize = 20
	for _, part := range runeChunks(text, chunkSize) {
		writeSSE(map[string]any{
			"id": "chatcmpl-" + convID, "object": "chat.completion.chunk", "created": time.Now().Unix(), "model": model,
			"choices": []any{map[string]any{"index": 0, "delta": map[string]any{"content": part}, "finish_reason": nil}},
		})
	}
	writeSSE(map[string]any{
		"id": "chatcmpl-" + convID, "object": "chat.completion.chunk", "created": time.Now().Unix(), "model": model,
		"choices": []any{map[string]any{"index": 0, "delta": map[string]any{}, "finish_reason": finishReason}},
	})
	fmt.Fprintf(w, "data: [DONE]\n\n")
	if flusher != nil {
		flusher.Flush()
	}
}

// prepareRequest 模型映射 + 默认值注入（system 提示词 / temperature / max_tokens / reasoning_effort / tools）。
func (p *Proxy) prepareRequest(m map[string]any) error {
	rawModel, ok := m["model"].(string)
	if !ok || rawModel == "" {
		return fmt.Errorf("缺少必填字段 model")
	}
	m["model"] = normalizeModel(rawModel)

	msgs, ok := m["messages"].([]any)
	if !ok {
		return fmt.Errorf("缺少必填字段 messages")
	}
	hasSystem := false
	for _, mm := range msgs {
		if om, ok := mm.(map[string]any); ok {
			if role, _ := om["role"].(string); role == "system" {
				hasSystem = true
				break
			}
		}
	}
	// 客户端未显式给 system 消息时，自动注入导出的 Playground 系统提示词。
	// INJECT_SYSTEM_PROMPT=false 时跳过（避免大提示词拖慢 sub2api/Claude Code 场景）。
	if p.cfg.InjectSystemPrompt {
		sp := p.GetSysPrompt()
		if !hasSystem && strings.TrimSpace(sp) != "" {
			m["messages"] = append([]any{
				map[string]any{"role": "system", "content": sp},
			}, msgs...)
		}
	}
	if _, ok := m["temperature"]; !ok {
		m["temperature"] = 0.7
	} else if isGLMModel(m["model"].(string)) {
		// GLM conversations 只接受 temperature ∈ [0,1]，超限上游 422（实测 >1 报
		// "Input should be less than or equal to 1"）。钳制到 [0,1] 避免客户端传入非法值。
		if t, ok := m["temperature"].(float64); ok {
			if t < 0 {
				m["temperature"] = 0.0
			} else if t > 1 {
				m["temperature"] = 1.0
			}
		}
	}
	if _, ok := m["max_tokens"]; !ok {
		m["max_tokens"] = 4096
	}
	if _, ok := m["reasoning_effort"]; !ok {
		// GLM-5.2 合法值仅 none/high。默认取 DEFAULT_REASONING_EFFORT（默认 none=最快 ~2s；
		// 长任务/agent 场景必须 none，否则 high 深度思考单请求 60s+ 极易触发上游/客户端超时）。
		// 需要深度思考时显式传 reasoning_effort=high，或设环境变量 DEFAULT_REASONING_EFFORT=high。
		if isGLMModel(m["model"].(string)) {
			m["reasoning_effort"] = p.cfg.DefaultReasoningEffort
		}
	} else if isGLMModel(m["model"].(string)) {
		// 归一化 effort：GLM 上游只接受 none/high，但客户端（Claude Code / opencode 等）可能传
		// low/medium/max/xhigh/ultra 等更细粒度等级。统一映射：
		//   none/low/medium/minimal/off/disabled → none（快速）
		//   high/max/xhigh/x-high/maximum/ultra/extreme → high（深度思考）
		if v, ok := m["reasoning_effort"].(string); ok {
			m["reasoning_effort"] = normalizeEffort(v)
		}
	}
	if p.cfg.InjectPlaygroundTools {
		if _, ok := m["tools"]; !ok {
			// GLM 走 Conversations 通道，tools 用裸类型格式（code_interpreter 等）。
			// 非 GLM 走 chat/completions，tools 用 function 格式。
			if isGLMModel(m["model"].(string)) {
				m["tools"] = playgroundBareTools
			} else {
				m["tools"] = playgroundTools
			}
		} else {
			// 客户端已带 tools：非 GLM 模型必须把裸类型工具（{type:"code_interpreter"}）转成 function 格式，
			// 否则上游 chat/completions 报 "connector is not supported" (400/422)。
			if !isGLMModel(m["model"].(string)) {
				m["tools"] = normalizeBareToolsToFunctions(m["tools"])
			}
		}
	}
	return nil
}

// normalizeBareToolsToFunctions 把裸类型工具数组转成 function 格式。
// 裸类型：{"type":"code_interpreter"} / {"type":"web_search","open_results":false}
// function：{"type":"function","function":{"name":"code_interpreter",...}}
func normalizeBareToolsToFunctions(tools any) []any {
	arr, ok := tools.([]any)
	if !ok {
		return []any{}
	}
	out := make([]any, 0, len(arr))
	for _, t := range arr {
		om, ok := t.(map[string]any)
		if !ok {
			continue
		}
		tp, _ := om["type"].(string)
		if tp == "" {
			continue
		}
		if tp == "function" {
			out = append(out, om)
			continue
		}
		desc := ""
		switch tp {
		case "code_interpreter":
			desc = "在沙盒中执行 Python 代码并返回结果"
		case "image_generation":
			desc = "根据描述生成一张图片"
		case "web_search":
			desc = "搜索互联网并返回相关结果"
		}
		out = append(out, map[string]any{
			"type": "function",
			"function": map[string]any{
				"name":        tp,
				"description": desc,
				"parameters":  map[string]any{"type": "object", "properties": map[string]any{}},
			},
		})
	}
	return out
}

// doUpstream 带 key 轮询与失败切换地转发请求到上游；成功时返回可用的 http.Response。
func (p *Proxy) doUpstream(ctx context.Context, body map[string]any) (*http.Response, int, []byte, error) {
	model, _ := body["model"].(string)
	isGLM := isGLMModel(model)
	// GLM 走 Conversations 通道（/v1/conversations），其余走 /chat/completions。
	payload := body
	convID := ""
	if isGLM {
		payload = buildConversationsReq(body)
		// 支持 append：body 带 conversation_id 时对既有会话追加（POST /conversations/{id}，
		// 只带 inputs + completion_args，不带 model/conversation_id 字段，否则上游 422）。
		if cid, _ := body["conversation_id"].(string); cid != "" {
			convID = cid
			delete(payload, "model")
			delete(payload, "conversation_id")
			if _, ok := payload["inputs"]; !ok {
				payload["inputs"] = []any{}
			}
		}
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return nil, 0, nil, err
	}
	ep := conversationsEndpoint(model)
	if convID != "" {
		ep = "/conversations/" + convID
	}
	var lastStatus int
	var lastBody []byte
	var lastErr error
	for attempt := 0; attempt < p.cfg.MaxRetries; attempt++ {
		entry := p.pool.PickUpstream()
		if entry == nil {
			return nil, 0, nil, fmt.Errorf("上游 key 池为空")
		}
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, p.cfg.UpstreamBase+ep, bytes.NewReader(raw))
		if err != nil {
			return nil, 0, nil, err
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", "Bearer "+entry.Key)
		if s, _ := body["stream"].(bool); s {
			req.Header.Set("Accept", "text/event-stream")
		} else {
			req.Header.Set("Accept", "application/json")
		}
		resp, err := p.client.Do(req)
		if err != nil {
			lastErr = err
			p.pool.ReportFailure(entry, 0, "transport: "+errText(err))
			continue
		}
		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			lastStatus = resp.StatusCode
			lastBody, _ = io.ReadAll(io.LimitReader(resp.Body, 1<<20))
			_ = resp.Body.Close()
			reason := lastBody
			if len(reason) > 300 {
				reason = reason[:300]
			}
			p.pool.ReportFailure(entry, resp.StatusCode, fmt.Sprintf("upstream %d: %s", resp.StatusCode, string(reason)))
			continue
		}
		p.pool.ReportSuccess(entry)
		return resp, 0, nil, nil
	}
	if lastStatus != 0 {
		return nil, lastStatus, lastBody, nil
	}
	return nil, 0, nil, lastErr
}

// writeJSONResponse 非流式：GLM 会话响应转 OpenAI 格式；其余透传。
// 两者都注入 conversation_id 到返回体与响应头。
func (p *Proxy) writeJSONResponse(w http.ResponseWriter, r *http.Request, resp *http.Response, req map[string]any) {
	body, err := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	if err != nil {
		httpx.WriteError(w, http.StatusBadGateway, "读取上游响应失败: "+errText(err), "upstream_error")
		return
	}
	model, _ := req["model"].(string)
	var out map[string]any
	if isGLMModel(model) {
		converted := convertConversationsToOpenAI(body)
		if err := json.Unmarshal(converted, &out); err != nil {
			httpx.WriteError(w, http.StatusBadGateway, "上游响应不是合法 JSON: "+errText(err), "upstream_error")
			return
		}
	} else {
		if err := json.Unmarshal(body, &out); err != nil {
			httpx.WriteError(w, http.StatusBadGateway, "上游响应不是合法 JSON: "+errText(err), "upstream_error")
			return
		}
	}
	cid := p.extractConversationID(resp.Header, body)
	if cid != "" {
		out["conversation_id"] = cid
		w.Header().Set("X-Conversation-ID", cid)
		p.storeConversation(cid, req)
	}
	httpx.WriteJSON(w, http.StatusOK, out)
}

// streamSSE 手写 SSE 转发：先读首个事件提取 conversation_id，再边读边 flush，客户端断开即停。
func (p *Proxy) streamSSE(w http.ResponseWriter, r *http.Request, resp *http.Response, req map[string]any) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		// 客户端不支持 flush，退化为一次性透传。
		_, _ = io.Copy(w, resp.Body)
		return
	}

	reader := bufio.NewReader(resp.Body)
	var first bytes.Buffer
	for {
		line, err := reader.ReadBytes('\n')
		if len(line) > 0 {
			first.Write(line)
		}
		if err != nil {
			break
		}
		if strings.TrimSpace(string(line)) == "" {
			break // 首个 SSE 事件结束
		}
	}

	// 在写响应头前确定 conversation_id（优先上游，否则本地生成）。
	cid := p.extractConversationID(resp.Header, first.Bytes())
	if cid != "" {
		p.storeConversation(cid, req)
	}
	h := w.Header()
	h.Set("Content-Type", "text/event-stream; charset=utf-8")
	h.Set("Cache-Control", "no-cache")
	h.Set("Connection", "keep-alive")
	h.Set("X-Accel-Buffering", "no")
	if cid != "" {
		h.Set("X-Conversation-ID", cid)
	}
	w.WriteHeader(http.StatusOK)
	if _, err := w.Write(first.Bytes()); err != nil {
		return
	}
	flusher.Flush()

	for {
		line, err := reader.ReadBytes('\n')
		if len(line) > 0 {
			if _, werr := w.Write(line); werr != nil {
				return // 客户端断开
			}
		}
		flusher.Flush()
		if err != nil {
			return // EOF 或上游异常
		}
		if r.Context().Err() != nil {
			return // 客户端已取消
		}
	}
}

// handleModels GET /v1/models，OpenAI 兼容格式。
func (p *Proxy) HandleModels(w http.ResponseWriter, r *http.Request) {
	data := make([]map[string]any, 0, len(p.cfg.Models))
	for _, m := range p.cfg.Models {
		data = append(data, map[string]any{
			"id": m, "object": "model", "created": 0, "owned_by": "mistralai",
		})
	}
	httpx.WriteJSON(w, http.StatusOK, map[string]any{"object": "list", "data": data})
}

// handleConfig 供 UI 拉取模型列表 / 默认系统提示词 / 工具；PUT 时更新默认系统提示词并持久化。
func (p *Proxy) HandleConfig(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPut {
		var req struct {
			SystemPrompt string `json:"system_prompt"`
		}
		if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
			httpx.WriteError(w, http.StatusBadRequest, "请求体错误: "+errText(err), "bad_request")
			return
		}
		if err := p.SetSysPrompt(req.SystemPrompt); err != nil {
			httpx.WriteError(w, http.StatusInternalServerError, "保存失败: "+errText(err), "internal")
			return
		}
		httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true, "default_system_prompt": p.GetSysPrompt()})
		return
	}
	httpx.WriteJSON(w, http.StatusOK, map[string]any{
		"models":                 p.cfg.Models,
		"default_system_prompt":  p.GetSysPrompt(),
		"inject_playground_tools": p.cfg.InjectPlaygroundTools,
		"playground_tools":       playgroundTools,
		"reasoning_efforts":      []string{"none", "high"},
	})
}

// HandleConversationsRaw POST /v1/conversations（新建）或 POST /v1/conversations/{id}（append）：
// 原样透传 conversations 请求到上游（不转换，不注入系统提示词），供外部客户端直接用原生格式调用。
// 与 OpenAI 兼容通道不同，这里要求请求体自带 model 等 conversations 字段。
//
// 自动会话延续：客户端传 X-Session-ID 头（或 body session_id）后，代理在服务端维护
// session → conversation_id 映射。客户端每次请求都不用带 conversation_id，代理自动 append 到该会话；
// 首次请求自动新建。这样"不加 id 也能多轮"。也兼容显式传 conversation_id（body 或 URL 路径）。
func (p *Proxy) HandleConversationsRaw(w http.ResponseWriter, r *http.Request) {
	raw, err := io.ReadAll(io.LimitReader(r.Body, maxBodySize))
	if err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "读取请求体失败: "+err.Error(), "bad_request")
		return
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "请求体不是合法 JSON: "+err.Error(), "bad_request")
		return
	}

	// 会话标识：优先 X-Session-ID 头，其次 body session_id。
	session := strings.TrimSpace(r.Header.Get("X-Session-ID"))
	if session == "" {
		if v, ok := m["session_id"].(string); ok {
			session = strings.TrimSpace(v)
		}
	}

	// 同一 session 的并发请求串行化：先取会话锁，覆盖「查映射→上游请求→绑定」整段窗口，
	// 避免两个并发首次请求各自新建会话（会话分裂）。session 为空时不锁。
	var sl *sync.Mutex
	if session != "" {
		sl = p.sessionLock(session)
		sl.Lock()
		defer sl.Unlock()
	}

	// 路径：POST /v1/conversations/{id} → append 到既有会话；POST /v1/conversations → 新建。
	ep := "/conversations"
	if id := r.PathValue("id"); id != "" {
		ep = "/conversations/" + id
	}

	// 自动延续：POST /conversations 且 body 无 conversation_id 时，查 session 映射。
	explicitConv, _ := m["conversation_id"].(string)
	if ep == "/conversations" && explicitConv == "" && session != "" {
		if prev := p.sessionConv(session); prev != "" {
			explicitConv = prev
			ep = "/conversations/" + prev
		}
	}

	// 透传上游。conversations 原生请求 model 字段创建时必填。
	entry := p.pool.PickUpstream()
	if entry == nil {
		httpx.WriteError(w, http.StatusInternalServerError, "上游 key 池为空", "no_keys")
		return
	}

	// 新建会话时若未带 instructions 且代理配置了默认系统提示词，则自动注入（可用 INJECT_SYSTEM_PROMPT=false 关闭）
	if ep == "/conversations" && p.cfg.InjectSystemPrompt {
		if _, ok := m["instructions"]; !ok {
			if sp := p.GetSysPrompt(); strings.TrimSpace(sp) != "" {
				m["instructions"] = sp
			}
		}
	}
	// append 时清理不合法的字段（model/conversation_id 不该带，上游 422）
	if explicitConv != "" {
		delete(m, "model")
		delete(m, "conversation_id")
		delete(m, "session_id")
	}
	body, _ := json.Marshal(m)

	req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, p.cfg.UpstreamBase+ep, bytes.NewReader(body))
	if err != nil {
		httpx.WriteError(w, http.StatusInternalServerError, errText(err), "internal")
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+entry.Key)
	req.Header.Set("Accept", "application/json")

	resp, err := p.client.Do(req)
	if err != nil {
		httpx.WriteError(w, http.StatusBadGateway, "上游不可达: "+errText(err), "upstream_unreachable")
		return
	}
	defer resp.Body.Close()
	respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 32<<20))

	if resp.StatusCode != http.StatusOK {
		p.writeUpstreamError(w, resp.StatusCode, respBody)
		return
	}

	// 缓存会话（供 GET /v1/conversations/{id} 查询）+ 绑定 session → 新 conv
	cid := conversationIDFromOutputs(respBody)
	if cid != "" {
		p.storeConversation(cid, nil)
		if session != "" {
			p.bindSession(session, cid)
		}
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	if cid != "" {
		w.Header().Set("X-Conversation-ID", cid)
	}
	if session != "" {
		w.Header().Set("X-Session-ID", session)
	}
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(respBody)
}

// HandleConversation GET /v1/conversations/{id}：优先本地缓存，否则透传上游。
func (p *Proxy) HandleConversation(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	p.convMu.Lock()
	cv, ok := p.convs[id]
	p.convMu.Unlock()
	if ok {
		httpx.WriteJSON(w, http.StatusOK, cv)
		return
	}

	entry := p.pool.PickUpstream()
	if entry == nil {
		httpx.WriteError(w, http.StatusInternalServerError, "上游 key 池为空", "no_keys")
		return
	}
	req, err := http.NewRequestWithContext(r.Context(), http.MethodGet,
		p.cfg.UpstreamBase+"/conversations/"+id, nil)
	if err != nil {
		httpx.WriteError(w, http.StatusInternalServerError, errText(err), "internal")
		return
	}
	req.Header.Set("Authorization", "Bearer "+entry.Key)
	req.Header.Set("Accept", "application/json")
	resp, err := p.client.Do(req)
	if err != nil {
		httpx.WriteError(w, http.StatusBadGateway, "上游不可达: "+errText(err), "upstream_unreachable")
		return
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if resp.StatusCode == http.StatusNotFound {
		httpx.WriteError(w, http.StatusNotFound, "未找到会话 "+id+"（上游 404）", "not_found")
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(resp.StatusCode)
	_, _ = w.Write(body)
}

// writeUpstreamError 把上游错误码映射成可读 JSON（含上游 body）。
func (p *Proxy) writeUpstreamError(w http.ResponseWriter, status int, body []byte) {
	code, msg := mapUpstreamError(status, body)
	httpx.WriteJSON(w, code, map[string]any{
		"error": map[string]any{
			"message":         msg,
			"type":            "upstream_error",
			"code":            code,
			"status":          code,
			"upstream_status": status,
			"upstream_body":   string(body),
		},
	})
}

func mapUpstreamError(status int, body []byte) (int, string) {
	lb := strings.ToLower(string(body))
	switch status {
	case http.StatusUnauthorized:
		return 401, "上游 API Key 无效或已过期 (401)"
	case http.StatusPaymentRequired:
		return 402, "上游额度已耗尽 (402)"
	case http.StatusTooManyRequests:
		return 429, "上游限流 (429)，请稍后重试"
	case http.StatusServiceUnavailable:
		if strings.Contains(lb, "no healthy upstream") {
			return 502, "上游服务暂不可用 (no healthy upstream)，请稍后重试"
		}
		return 503, "上游服务暂不可用 (503)"
	default:
		if status >= 500 {
			return 502, fmt.Sprintf("上游返回错误 (%d)", status)
		}
		return status, fmt.Sprintf("上游请求被拒绝 (%d)", status)
	}
}

// extractConversationID 从上游响应头或首个 SSE 事件中提取 conversation_id；没有则本地生成。
func (p *Proxy) extractConversationID(h http.Header, buf []byte) string {
	for _, k := range []string{"X-Conversation-ID", "X-Mistral-Conversation-Id"} {
		if v := strings.TrimSpace(h.Get(k)); v != "" {
			return v
		}
	}
	var m struct {
		ConversationID string `json:"conversation_id"`
	}
	if json.Unmarshal(buf, &m) == nil && m.ConversationID != "" {
		return m.ConversationID
	}
	return ""
}

func genConversationID() string {
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		return "conv_" + fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return "conv_" + hex.EncodeToString(buf)
}

// storeConversation 记录最近 200 个会话，供 GET /v1/conversations/{id} 本地查询。
// sessionLock 返回该 session 的互斥锁（串行化同一 session 的并发请求，
// 避免两个并发首次请求各自新建会话导致会话分裂）。跨进程/重启无效，仅防单实例并发。
func (p *Proxy) sessionLock(session string) *sync.Mutex {
	p.sessionMu.Lock()
	defer p.sessionMu.Unlock()
	l, ok := p.sessionLocks[session]
	if !ok {
		l = &sync.Mutex{}
		p.sessionLocks[session] = l
	}
	return l
}

// sessionConv 返回 X-Session-ID 关联的 conversation_id（无则空）。
func (p *Proxy) sessionConv(session string) string {
	if session == "" {
		return ""
	}
	p.sessionMu.Lock()
	defer p.sessionMu.Unlock()
	return p.sessionMap[session]
}

// bindSession 把 X-Session-ID 关联到 conversation_id（响应拿到新 conv 时调用），并持久化。
func (p *Proxy) bindSession(session, convID string) {
	if session == "" || convID == "" {
		return
	}
	p.sessionMu.Lock()
	// 限制映射数量，防内存增长
	if len(p.sessionMap) >= 5000 {
		for k := range p.sessionMap {
			delete(p.sessionMap, k)
			delete(p.sessionLocks, k)
			if len(p.sessionMap) <= 2500 {
				break
			}
		}
	}
	p.sessionMap[session] = convID
	p.sessionMu.Unlock()
	p.saveSessions()
}

func (p *Proxy) storeConversation(id string, req map[string]any) {
	if id == "" {
		return
	}
	p.convMu.Lock()
	defer p.convMu.Unlock()
	msgRaw, _ := json.Marshal(req["messages"])
	var msgs []any
	_ = json.Unmarshal(msgRaw, &msgs)
	model, _ := req["model"].(string)
	p.convs[id] = &conversation{ID: id, Model: model, CreatedAt: time.Now(), Messages: msgs}
	p.convOrder = append(p.convOrder, id)
	if len(p.convOrder) > 200 {
		old := p.convOrder[0]
		p.convOrder = p.convOrder[1:]
		delete(p.convs, old)
	}
}

func normalizeModel(m string) string {
	if glmModelRE.MatchString(m) {
		return "glm-5-2"
	}
	return m
}

// isGLMModel 判断是否走 Conversations 通道（GLM-5.2 仅在 /v1/conversations 可用，
// /v1/chat/completions 对该模型 API 配额为 0 会返回 429）。
func isGLMModel(model string) bool {
	return model == "glm-5-2" || model == "zai-glm-5-2"
}

// normalizeEffort 把客户端的各种 reasoning_effort 等级映射到 GLM 上游接受的 two 档。
// GLM conversations API 只接受 "none" 或 "high"（实测 max/xhigh/maximum/ultra/low/medium 全部 422），
// 但 Claude Code / opencode 等客户端会传细粒度等级，统一映射：
//
//	none/low/medium/minimal/off/disabled → none（快速）
//	high/max/xhigh/x-high/maximum/ultra/extreme/very-high → high（深度思考）
func normalizeEffort(v string) string {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "none", "low", "medium", "minimal", "off", "disabled", "0":
		return "none"
	case "high", "max", "xhigh", "x-high", "maximum", "ultra", "supreme", "extreme", "very-high", "2", "10":
		return "high"
	default:
		return "none"
	}
}

// conversationsEndpoint 按模型选择上游端点：GLM 走 /v1/conversations，其余走 /v1/chat/completions。
func conversationsEndpoint(model string) string {
	if isGLMModel(model) {
		return "/conversations"
	}
	return "/chat/completions"
}

// buildConversationsReq 把 OpenAI 兼容请求体转换为 Conversations API 请求体。
// messages → inputs(message.input)；system 消息提升为顶层 instructions 字段（Conversations API 用 instructions 存系统提示词）；
// assistant 消息的 tool_calls → function.call 条目，tool 消息 → function.result 条目（多轮工具上下文不丢）；
// temperature/top_p/max_tokens/reasoning_effort/tool_choice → completion_args。
func buildConversationsReq(m map[string]any) map[string]any {
	out := map[string]any{"model": m["model"]}
	if msgs, ok := m["messages"].([]any); ok {
		inputs := make([]any, 0, len(msgs))
		var sysParts []string
		for _, mm := range msgs {
			om, ok := mm.(map[string]any)
			if !ok {
				continue
			}
			role, _ := om["role"].(string)
			content, _ := om["content"].(string)
			if role == "system" {
				// Conversations API 不支持 role=system 消息，也拒绝顶层 system 字段，
				// 系统提示词统一走 instructions 字段。
				sysParts = append(sysParts, content)
				continue
			}
			if role == "tool" {
				// tool 消息 → function.result 条目（匹配 runTools 生成的格式）
				if tid, _ := om["tool_call_id"].(string); tid != "" {
					inputs = append(inputs, map[string]any{
						"type":         "function.result",
						"tool_call_id": tid,
						"result":       content,
					})
				}
				continue
			}
			if role == "assistant" {
				// assistant 消息：文本 → message.input；tool_calls → function.call 条目
				if content != "" {
					inputs = append(inputs, map[string]any{
						"type":    "message.input",
						"role":    role,
						"content": content,
					})
				}
				if tcs, ok := om["tool_calls"].([]any); ok {
					for _, tc := range tcs {
						tcMap, _ := tc.(map[string]any)
						id, _ := tcMap["id"].(string)
						fn, _ := tcMap["function"].(map[string]any)
						name, _ := fn["name"].(string)
						args, _ := fn["arguments"].(string)
						if args == "" {
							args = "{}"
						}
						inputs = append(inputs, map[string]any{
							"type":         "function.call",
							"tool_call_id": id,
							"name":         name,
							"arguments":    args,
						})
					}
				}
				continue
			}
			if role != "user" {
				continue
			}
			inputs = append(inputs, map[string]any{
				"type":    "message.input",
				"role":    role,
				"content": content,
			})
		}
		out["inputs"] = inputs
		if len(sysParts) > 0 {
			out["instructions"] = strings.TrimSpace(strings.Join(sysParts, "\n"))
		}
	}
	args := map[string]any{}
	if v, ok := m["temperature"]; ok {
		args["temperature"] = v
	}
	if v, ok := m["top_p"]; ok {
		args["top_p"] = v
	}
	if v, ok := m["max_tokens"]; ok {
		args["max_tokens"] = v
	}
	if v, ok := m["reasoning_effort"]; ok {
		args["reasoning_effort"] = v
	}
	if v, ok := m["tool_choice"]; ok {
		args["tool_choice"] = v
	}
	if len(args) > 0 {
		out["completion_args"] = args
	}
	if tools, ok := m["tools"]; ok {
		out["tools"] = tools
	}
	return out
}

// convertConversationsToOpenAI 把 Conversations API 响应转换为 OpenAI 兼容响应。
func convertConversationsToOpenAI(body []byte) []byte {
	var in struct {
		ConversationID string `json:"conversation_id"`
		Outputs        []struct {
			Type        string          `json:"type"`
			Role        string          `json:"role"`
			Content     json.RawMessage `json:"content"`
			ToolCallID  string          `json:"tool_call_id"`
			Name        string          `json:"name"`
			Arguments   string          `json:"arguments"`
			Result      string          `json:"result"`
			MessageOutput json.RawMessage `json:"message_output"`
			ToolCallOutput json.RawMessage `json:"tool_call_output"`
		} `json:"outputs"`
		Usage *struct {
			PromptTokens     int `json:"prompt_tokens"`
			CompletionTokens int `json:"completion_tokens"`
			TotalTokens      int `json:"total_tokens"`
		} `json:"usage"`
	}
	if err := json.Unmarshal(body, &in); err != nil {
		return body
	}
	// 提取 message.output 的最终文本（跳过 thinking 块）+ thinking 文本。
	content := ""
	reasoning := ""
	var toolCalls []map[string]any
	for _, o := range in.Outputs {
		if o.Type == "message.output" {
			if content == "" {
				content = extractAssistantText(o.Content)
			}
			if reasoning == "" {
				reasoning = extractReasoningText(o.Content)
			}
		}
		if o.Type == "function.call" {
			name := o.Name
			args := o.Arguments
			if name == "" {
				// 尝试从嵌套 tool_call_output 提取
				var tco struct {
					Name      string `json:"name"`
					Arguments string `json:"arguments"`
				}
				if len(o.ToolCallOutput) > 0 && json.Unmarshal(o.ToolCallOutput, &tco) == nil {
					name = tco.Name
					args = tco.Arguments
				}
			}
			if args == "" {
				args = "{}"
			}
			toolCalls = append(toolCalls, map[string]any{
				"id":       o.ToolCallID,
				"type":     "function",
				"function": map[string]any{"name": name, "arguments": args},
			})
		}
	}
	usage := map[string]any{}
	if in.Usage != nil {
		usage = map[string]any{
			"prompt_tokens":     in.Usage.PromptTokens,
			"completion_tokens": in.Usage.CompletionTokens,
			"total_tokens":      in.Usage.TotalTokens,
		}
	}
	msg := map[string]any{
		"role":    "assistant",
		"content": content,
	}
	if reasoning != "" {
		msg["reasoning_content"] = reasoning
	}
	finishReason := "stop"
	if len(toolCalls) > 0 {
		msg["tool_calls"] = toolCalls
		finishReason = "tool_calls"
	}
	out := map[string]any{
		"id":      "chatcmpl-" + in.ConversationID,
		"object":  "chat.completion",
		"created": time.Now().Unix(),
		"model":   "glm-5-2",
		"choices": []any{
			map[string]any{
				"index":    0,
				"message":  msg,
				"finish_reason": finishReason,
			},
		},
		"usage": usage,
	}
	if in.ConversationID != "" {
		out["conversation_id"] = in.ConversationID
	}
	b, _ := json.Marshal(out)
	return b
}

// extractAssistantText 从 Conversations 响应的 content 字段提取最终助手文本。
// content 可能是字符串，也可能是数组（含 thinking 块 + text 块）。
func extractAssistantText(raw json.RawMessage) string {
	// 尝试字符串
	var s string
	if json.Unmarshal(raw, &s) == nil {
		return s
	}
	// 尝试数组（thinking/text/... 块）
	var parts []struct {
		Type string `json:"type"`
		Text string `json:"text"`
	}
	if json.Unmarshal(raw, &parts) != nil {
		return ""
	}
	var sb strings.Builder
	for _, p := range parts {
		if p.Type == "text" && strings.TrimSpace(p.Text) != "" {
			if sb.Len() > 0 {
				sb.WriteString("\n")
			}
			sb.WriteString(p.Text)
		}
	}
	return sb.String()
}

// extractReasoningText 从 Conversations 响应的 content 字段提取 thinking 块文本。
// GLM 的思考过程以 {type:"thinking", thinking:[{type:"text",text:"..."}], closed:true} 形式存在，
// thinking 字段可能是字符串、数组或 {text/thinking} 对象。
func extractReasoningText(raw json.RawMessage) string {
	var s string
	if json.Unmarshal(raw, &s) == nil {
		return ""
	}
	var parts []struct {
		Type     string          `json:"type"`
		Text     string          `json:"text"`
		Content  string          `json:"content"`
		Thinking json.RawMessage `json:"thinking"`
	}
	if json.Unmarshal(raw, &parts) != nil {
		return ""
	}
	var sb strings.Builder
	for _, p := range parts {
		if p.Type != "thinking" || len(p.Thinking) == 0 || string(p.Thinking) == "null" {
			continue
		}
		t := reasoningTextFromRaw(p.Thinking)
		if t == "" {
			t = p.Content
		}
		if t == "" {
			t = p.Text
		}
		if t == "" {
			continue
		}
		if sb.Len() > 0 {
			sb.WriteString("\n")
		}
		sb.WriteString(t)
	}
	return sb.String()
}

// reasoningTextFromRaw 从 thinking 字段（字符串 / 数组 / 对象）提取纯文本。
func reasoningTextFromRaw(raw json.RawMessage) string {
	// 字符串
	var s string
	if json.Unmarshal(raw, &s) == nil {
		return s
	}
	// 数组 [{type:"text", text:"..."}]
	var arr []struct {
		Type string `json:"type"`
		Text string `json:"text"`
	}
	if json.Unmarshal(raw, &arr) == nil {
		var sb strings.Builder
		for _, it := range arr {
			if it.Type == "text" && it.Text != "" {
				if sb.Len() > 0 {
					sb.WriteString("\n")
				}
				sb.WriteString(it.Text)
			}
		}
		return sb.String()
	}
	// 对象 {text/thinking/content}
	var obj struct {
		Text     string `json:"text"`
		Thinking string `json:"thinking"`
		Content  string `json:"content"`
	}
	if json.Unmarshal(raw, &obj) == nil {
		if obj.Thinking != "" {
			return obj.Thinking
		}
		if obj.Text != "" {
			return obj.Text
		}
		return obj.Content
	}
	return ""
}

func isStream(m map[string]any) bool {
	if v, ok := m["stream"]; ok {
		if b, ok := v.(bool); ok {
			return b
		}
	}
	return false
}

// runeChunks 把字符串按 rune 边界切成 ≤size 字节的块，避免切断 UTF-8 多字节字符。
// 上游文本可能含 emoji（4 字节）等，按字节切片会产生非法 UTF-8，json.Marshal 会替换成 U+FFFD。
// 空字符串返回空切片（不产生任何 chunk）。
func runeChunks(s string, size int) []string {
	if size <= 0 || len(s) == 0 {
		return nil
	}
	rs := []rune(s)
	per := size / 4 // 最坏情况下 1 rune 最多 4 字节
	if per < 1 {
		per = 1
	}
	var out []string
	for i := 0; i < len(rs); i += per {
		end := i + per
		if end > len(rs) {
			end = len(rs)
		}
		out = append(out, string(rs[i:end]))
	}
	return out
}

// HandleMessages POST /v1/messages（Anthropic 协议统一出口）：
// 请求 Anthropic messages → 转 OpenAI chat/completions → 转发上游（GLM 走 conversations 通道）→
// 响应转回 Anthropic message 格式。保证所有客户端只对接本项目一个出口。
func (p *Proxy) HandleMessages(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, maxBodySize))
	if err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "读取请求体失败: "+err.Error(), "bad_request")
		return
	}
	chatBody, streaming, err := anthropicToOpenAI(body)
	if err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "convert messages: "+err.Error(), "bad_request")
		return
	}
	var mm struct {
		Model string `json:"model"`
	}
	_ = json.Unmarshal(body, &mm)
	model := normalizeModel(mm.Model)

	// 解析转换后的 chatBody
	var m map[string]any
	if err := json.Unmarshal(chatBody, &m); err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "内部转换失败: "+err.Error(), "bad_request")
		return
	}
	// 注入默认参数（temperature/max_tokens/reasoning_effort/system）
	if err := p.prepareRequest(m); err != nil {
		httpx.WriteError(w, http.StatusBadRequest, err.Error(), "bad_request")
		return
	}

	if streaming {
		// 流式：转回 Anthropic SSE。先走工具闭环（若有），再流式。
		p.handleMessagesStream(w, r, m, model)
		return
	}

	// 非流式：GLM + 有工具 → 会话工具通道（passthrough 客户端驱动 / local 闭环）。
	// passthrough 时 GLM 返回 tool_calls → openaiToAnthropic 转 tool_use 块给客户端本机执行。
	_, hasTools := m["tools"].([]any)
	if isGLMModel(model) && hasTools {
		m["stream"] = false
		b, _, status, err := p.chatWithToolsMode(r.Context(), "", m, p.cfg.ToolMode == "local")
		if err != nil {
			if status != 0 {
				p.writeUpstreamError(w, status, b)
			} else {
				httpx.WriteError(w, http.StatusBadGateway, "工具闭环失败: "+errText(err), "upstream_error")
			}
			return
		}
		if err := openaiToAnthropic(w, bytes.NewReader(b), model); err != nil {
			httpx.WriteError(w, http.StatusBadGateway, "转换响应失败: "+err.Error(), "upstream_error")
		}
		return
	}

	resp, status, upBody, upErr := p.doUpstream(r.Context(), m)
	if resp == nil {
		if status != 0 {
			p.writeUpstreamError(w, status, upBody)
		} else {
			httpx.WriteError(w, http.StatusBadGateway, "上游不可达: "+errText(upErr), "upstream_unreachable")
		}
		return
	}
	defer resp.Body.Close()
	// 上游可能是 chat 格式或（GLM）conversations 格式，统一转 OpenAI 再转 Anthropic。
	all, _ := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	var openaiBody []byte
	if isGLMModel(model) {
		openaiBody = convertConversationsToOpenAI(all)
	} else {
		openaiBody = all
	}
	// 写 Anthropic 格式
	if err := openaiToAnthropic(w, strings.NewReader(string(openaiBody)), model); err != nil {
		httpx.WriteError(w, http.StatusBadGateway, "转换响应失败: "+err.Error(), "upstream_error")
	}
}

// ChatRaw 供账号管理模块调用的对话入口：GLM 走工具闭环，其余走普通转发。
// 返回 (OpenAI 兼容响应字节, 新 conversation_id, 上游状态码, error)。
// convID 非空时对该会话做 append（多轮）。
func (p *Proxy) ChatRaw(ctx context.Context, convID string, body map[string]any) ([]byte, string, int, error) {
	model, _ := body["model"].(string)
	// 非流式，移除 stream
	body["stream"] = false
	_, hasTools := body["tools"].([]any)
	if isGLMModel(model) && hasTools {
		return p.chatWithTools(ctx, convID, body)
	}
	// 普通转发：GLM 走 conversations（无工具），非 GLM 走 chat/completions
	if isGLMModel(model) {
		// GLM 无工具：走 doUpstream 的 conversations 通道（convID 非空时 append）
		if convID != "" {
			body["conversation_id"] = convID
		}
		resp, status, upBody, err := p.doUpstream(ctx, body)
		if resp == nil {
			return upBody, "", status, err
		}
		defer resp.Body.Close()
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
		conv := conversationIDFromOutputs(b)
		if conv == "" {
			conv = p.extractConversationID(resp.Header, b)
		}
		return convertConversationsToOpenAI(b), conv, 0, nil
	}
	resp, status, upBody, err := p.doUpstream(ctx, body)
	if resp == nil {
		return upBody, "", status, err
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	return b, "", 0, nil
}