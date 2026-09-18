package proxy

import (
	"bufio"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"mistral-reverse-proxy/internal/httpx"
)

// ============================================================================
// Anthropic messages 协议 ↔ OpenAI chat/completions 协议转换
// 参照 flex go_backend/internal/gateway/gateway.go 的实现移植。
// ============================================================================

// anMsg Anthropic 消息。
type anMsg struct {
	Role    string          `json:"role"`
	Content json.RawMessage `json:"content"`
}

type anTool struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	InputSchema json.RawMessage `json:"input_schema"`
}

// anthropicToOpenAI 将 Anthropic messages 请求体转为 OpenAI chat/completions 请求体。
// 返回 (chatBody, streaming, err)。
func anthropicToOpenAI(body []byte) ([]byte, bool, error) {
	var req struct {
		Model       string          `json:"model"`
		Messages    []anMsg         `json:"messages"`
		System      json.RawMessage `json:"system"`
		MaxTokens   int             `json:"max_tokens"`
		Stream      bool            `json:"stream"`
		Temperature *float64        `json:"temperature"`
		TopP        *float64        `json:"top_p"`
		Stop        json.RawMessage `json:"stop"`
		Tools       []anTool        `json:"tools"`
		ToolChoice  json.RawMessage `json:"tool_choice"`
		Thinking    json.RawMessage `json:"thinking"`
	}
	if err := json.Unmarshal(body, &req); err != nil {
		return nil, false, err
	}
	if req.Model == "" {
		return nil, false, fmt.Errorf("missing model")
	}
	if len(req.Messages) == 0 {
		return nil, false, fmt.Errorf("missing messages")
	}

	chat := map[string]interface{}{"model": normalizeModel(req.Model), "stream": req.Stream}
	msgs := []map[string]interface{}{}
	if sysText := anContentText(req.System); sysText != "" {
		msgs = append(msgs, map[string]interface{}{"role": "system", "content": sysText})
	}
	for _, m := range req.Messages {
		switch m.Role {
		case "assistant":
			texts, toolUses := anContentParts(m.Content)
			text := strings.Join(texts, "\n")
			if len(toolUses) > 0 {
				tcs := []map[string]interface{}{}
				for _, tu := range toolUses {
					input := json.RawMessage("{}")
					if len(tu.Input) > 0 && string(tu.Input) != "null" {
						input = tu.Input
					}
					tcs = append(tcs, map[string]interface{}{
						"id":       tu.ID,
						"type":     "function",
						"function": map[string]interface{}{"name": tu.Name, "arguments": string(input)},
					})
				}
				msg := map[string]interface{}{"role": "assistant", "tool_calls": tcs}
				if text != "" {
					msg["content"] = text
				} else {
					msg["content"] = nil
				}
				msgs = append(msgs, msg)
			} else if text != "" {
				msgs = append(msgs, map[string]interface{}{"role": "assistant", "content": text})
			}
			// 纯 thinking / 空 content 的 assistant 消息跳过
		case "user":
			texts, toolResults := anContentParts(m.Content)
			for _, tr := range toolResults {
				msgs = append(msgs, map[string]interface{}{
					"role":         "tool",
					"tool_call_id": tr.ToolUseID,
					"content":      tr.ResultText,
				})
			}
			if len(texts) > 0 || len(toolResults) == 0 {
				text := strings.Join(texts, "\n")
				if text == "" {
					continue
				}
				msgs = append(msgs, map[string]interface{}{"role": "user", "content": text})
			}
		default:
			msgs = append(msgs, map[string]interface{}{"role": "user", "content": anContentText(m.Content)})
		}
	}
	chat["messages"] = msgs
	if req.MaxTokens > 0 {
		chat["max_tokens"] = req.MaxTokens
	}
	// Anthropic thinking 参数 → reasoning_effort
	// GLM 只接受 none/high，thinking enabled 即开启深度思考（high），disabled 关闭（none）。
	if len(req.Thinking) > 0 && string(req.Thinking) != "null" {
		var th struct {
			Type         string `json:"type"`
			BudgetTokens int    `json:"budget_tokens"`
		}
		if json.Unmarshal(req.Thinking, &th) == nil {
			if th.Type == "enabled" {
				chat["reasoning_effort"] = "high"
			} else {
				chat["reasoning_effort"] = "none"
			}
		}
	}
	if req.Temperature != nil {
		chat["temperature"] = *req.Temperature
	}
	if req.TopP != nil {
		chat["top_p"] = *req.TopP
	}
	if len(req.Stop) > 0 && string(req.Stop) != "null" {
		var s string
		if json.Unmarshal(req.Stop, &s) == nil {
			chat["stop"] = s
		} else {
			var sl []string
			if json.Unmarshal(req.Stop, &sl) == nil {
				chat["stop"] = sl
			}
		}
	}
	if len(req.Tools) > 0 {
		tools := []map[string]interface{}{}
		for _, t := range req.Tools {
			fn := map[string]interface{}{"name": t.Name}
			if t.Description != "" {
				fn["description"] = t.Description
			}
			if len(t.InputSchema) > 0 && string(t.InputSchema) != "null" {
				fn["parameters"] = json.RawMessage(t.InputSchema)
			}
			tools = append(tools, map[string]interface{}{"type": "function", "function": fn})
		}
		chat["tools"] = tools
	}
	if len(req.ToolChoice) > 0 && string(req.ToolChoice) != "null" {
		var tc struct {
			Type string `json:"type"`
			Name string `json:"name"`
		}
		if json.Unmarshal(req.ToolChoice, &tc) == nil {
			switch tc.Type {
			case "any":
				chat["tool_choice"] = "required"
			case "tool":
				chat["tool_choice"] = map[string]interface{}{
					"type":     "function",
					"function": map[string]interface{}{"name": tc.Name},
				}
			case "auto":
				chat["tool_choice"] = "auto"
			default:
				if tc.Type != "" {
					chat["tool_choice"] = tc.Type
				}
			}
		}
	}
	out, err := json.Marshal(chat)
	return out, req.Stream, err
}

// anContentText 提取 Anthropic content/system 纯文本。
func anContentText(raw json.RawMessage) string {
	if len(raw) == 0 || string(raw) == "null" {
		return ""
	}
	var s string
	if json.Unmarshal(raw, &s) == nil {
		return s
	}
	texts, _ := anContentParts(raw)
	return strings.Join(texts, "\n")
}

type anContentPart struct {
	IsToolUse    bool
	IsToolResult bool
	ID           string
	Name         string
	Input        json.RawMessage
	ToolUseID    string
	ResultText   string
}

// anContentParts 解析 Anthropic content 块，返回 (texts, toolUses/toolResults)。
func anContentParts(raw json.RawMessage) ([]string, []anContentPart) {
	if len(raw) == 0 || string(raw) == "null" {
		return nil, nil
	}
	var s string
	if json.Unmarshal(raw, &s) == nil {
		return []string{s}, nil
	}
	var blocks []struct {
		Type      string          `json:"type"`
		Text      string          `json:"text"`
		Thinking  string          `json:"thinking"`
		Signature string          `json:"signature"`
		ID        string          `json:"id"`
		Name      string          `json:"name"`
		Input     json.RawMessage `json:"input"`
		ToolUseID string          `json:"tool_use_id"`
		Content   json.RawMessage `json:"content"`
	}
	if json.Unmarshal(raw, &blocks) != nil {
		return nil, nil
	}
	var texts []string
	var parts []anContentPart
	for _, b := range blocks {
		switch b.Type {
		case "text":
			if b.Text != "" {
				texts = append(texts, b.Text)
			}
		case "thinking", "redacted_thinking":
			// 思考块不是可见文本
		case "tool_use":
			parts = append(parts, anContentPart{IsToolUse: true, ID: b.ID, Name: b.Name, Input: b.Input})
		case "tool_result":
			parts = append(parts, anContentPart{IsToolResult: true, ToolUseID: b.ToolUseID, ResultText: anContentText(b.Content)})
		}
	}
	return texts, parts
}

// openaiToAnthropic 非流式：OpenAI chat completion → Anthropic message。
func openaiToAnthropic(w http.ResponseWriter, src io.Reader, model string) error {
	msg, err := io.ReadAll(src)
	if err != nil {
		return err
	}
	var comp struct {
		ID      string `json:"id"`
		Choices []struct {
			Message struct {
				Content          string `json:"content"`
				ReasoningContent string `json:"reasoning_content"`
				ToolCalls        []struct {
					ID       string `json:"id"`
					Function struct {
						Name      string `json:"name"`
						Arguments string `json:"arguments"`
					} `json:"function"`
				} `json:"tool_calls"`
			} `json:"message"`
			FinishReason string `json:"finish_reason"`
		} `json:"choices"`
		Usage struct {
			PromptTokens     int `json:"prompt_tokens"`
			CompletionTokens int `json:"completion_tokens"`
		} `json:"usage"`
	}
	if err := json.Unmarshal(msg, &comp); err != nil {
		return err
	}
	if len(comp.Choices) == 0 {
		return fmt.Errorf("upstream: empty choices")
	}
	mid := "msg_" + comp.ID
	if comp.ID == "" {
		mid = "msg_" + randHex(24)
	}
	content := []map[string]interface{}{}
	if rc := comp.Choices[0].Message.ReasoningContent; rc != "" {
		content = append(content, map[string]interface{}{
			"type":      "thinking",
			"thinking":  rc,
			"signature": "sig_" + randHex(24),
		})
	}
	if text := comp.Choices[0].Message.Content; text != "" {
		content = append(content, map[string]interface{}{"type": "text", "text": text})
	}
	for _, tc := range comp.Choices[0].Message.ToolCalls {
		input := json.RawMessage(tc.Function.Arguments)
		if len(input) == 0 {
			input = json.RawMessage("{}")
		}
		content = append(content, map[string]interface{}{
			"type":  "tool_use",
			"id":    tc.ID,
			"name":  tc.Function.Name,
			"input": input,
		})
	}
	if len(content) == 0 {
		content = append(content, map[string]interface{}{"type": "text", "text": ""})
	}
	usage := map[string]interface{}{
		"input_tokens":  comp.Usage.PromptTokens,
		"output_tokens": comp.Usage.CompletionTokens,
	}
	out := map[string]interface{}{
		"id":            mid,
		"type":          "message",
		"role":          "assistant",
		"model":         model,
		"content":       content,
		"stop_reason":   mapFinish(comp.Choices[0].FinishReason),
		"stop_sequence": nil,
		"usage":         usage,
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(200)
	return json.NewEncoder(w).Encode(out)
}

// streamOpenAItoAnthropic 流式：OpenAI chunk SSE → Anthropic SSE。
func streamOpenAItoAnthropic(w http.ResponseWriter, src io.Reader, model string) error {
	w.Header().Set("Content-Type", "text/event-stream; charset=utf-8")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(200)
	fl, _ := w.(http.Flusher)
	flush := func() {
		if fl != nil {
			fl.Flush()
		}
	}
	sc := bufio.NewScanner(src)
	sc.Buffer(make([]byte, 64<<10), 1<<20)
	send := func(evt map[string]interface{}) error {
		b, err := json.Marshal(evt)
		if err != nil {
			return err
		}
		if _, err := fmt.Fprintf(w, "event: %s\ndata: %s\n\n", evt["type"], string(b)); err != nil {
			return err
		}
		flush()
		return nil
	}
	_ = send(map[string]interface{}{"type": "message_start", "message": map[string]interface{}{
		"id": "msg_" + randHex(24), "type": "message", "role": "assistant", "model": model,
		"content": []interface{}{}, "stop_reason": nil, "stop_sequence": nil, "usage": map[string]interface{}{"input_tokens": 0, "output_tokens": 0},
	}})
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if !strings.HasPrefix(line, "data:") {
			continue
		}
		data := strings.TrimSpace(strings.TrimPrefix(line, "data:"))
		if data == "[DONE]" {
			break
		}
		var chunk struct {
			Choices []struct {
				Delta struct {
					Content          string `json:"content"`
					ReasoningContent string `json:"reasoning_content"`
					ToolCalls        []struct {
						Index    int    `json:"index"`
						ID       string `json:"id"`
						Function struct {
							Name      string `json:"name"`
							Arguments string `json:"arguments"`
						} `json:"function"`
					} `json:"tool_calls"`
				} `json:"delta"`
				FinishReason string `json:"finish_reason"`
			} `json:"choices"`
		}
		if json.Unmarshal([]byte(data), &chunk) != nil {
			continue
		}
		if len(chunk.Choices) == 0 {
			continue
		}
		d := chunk.Choices[0].Delta
		if d.ReasoningContent != "" {
			_ = send(map[string]interface{}{"type": "content_block_start", "index": 0, "content_block": map[string]interface{}{"type": "thinking", "thinking": "", "signature": ""}})
			_ = send(map[string]interface{}{"type": "content_block_delta", "index": 0, "delta": map[string]interface{}{"type": "thinking_delta", "thinking": d.ReasoningContent}})
			_ = send(map[string]interface{}{"type": "content_block_stop", "index": 0})
		}
		if d.Content != "" {
			_ = send(map[string]interface{}{"type": "content_block_start", "index": 0, "content_block": map[string]interface{}{"type": "text", "text": ""}})
			_ = send(map[string]interface{}{"type": "content_block_delta", "index": 0, "delta": map[string]interface{}{"type": "text_delta", "text": d.Content}})
			_ = send(map[string]interface{}{"type": "content_block_stop", "index": 0})
		}
		if fr := chunk.Choices[0].FinishReason; fr != "" {
			_ = send(map[string]interface{}{"type": "message_delta", "delta": map[string]interface{}{"stop_reason": mapFinish(fr), "stop_sequence": nil}, "usage": map[string]interface{}{"output_tokens": 0}})
		}
	}
	_ = send(map[string]interface{}{"type": "message_stop"})
	return nil
}

// mapFinish OpenAI finish_reason → Anthropic stop_reason。
func mapFinish(fr string) string {
	switch fr {
	case "stop", "length", "tool_calls":
		return "end_turn"
	default:
		return "end_turn"
	}
}
func randHex(n int) string {
	b := make([]byte, (n+1)/2)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(b)[:n]
}

// handleMessagesStream Anthropic messages 流式路径：
// 内部统一走非流式工具闭环（若涉及工具）或上游转发，再把 OpenAI 响应转成 Anthropic SSE 事件。
// 简化策略：先完整拿最终 OpenAI 响应（含工具闭环），再以 message_start/delta/stop 事件流式输出。
func (p *Proxy) handleMessagesStream(w http.ResponseWriter, r *http.Request, m map[string]any, model string) {
	// 尝试工具闭环（GLM 会话；有 function 工具定义时）
	_, toolsPresent := m["tools"].([]any)
	convID, _ := m["conversation_id"].(string)

	var finalBody []byte
	if isGLMModel(model) || toolsPresent {
		// 先移除 stream 标记，走非流式会话工具通道（passthrough 客户端驱动 / local 闭环）
		m["stream"] = false
		b, _, status, err := p.chatWithToolsMode(r.Context(), convID, m, p.cfg.ToolMode == "local")
		if err != nil {
			httpx.WriteError(w, http.StatusBadGateway, "工具闭环失败: "+errText(err), "upstream_error")
			return
		}
		if status != 0 {
			p.writeUpstreamError(w, status, b)
			return
		}
		finalBody = b
	} else {
		// 非 GLM 非工具：直接转发上游，把 OpenAI SSE 转 Anthropic SSE
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
		if err := streamOpenAItoAnthropic(w, resp.Body, model); err != nil {
			return
		}
		return
	}

	// 输出 Anthropic SSE（基于完整响应，模拟流式事件）
	w.Header().Set("Content-Type", "text/event-stream; charset=utf-8")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(200)
	fl, _ := w.(http.Flusher)
	send := func(evt map[string]interface{}) {
		b, _ := json.Marshal(evt)
		fmt.Fprintf(w, "event: %s\ndata: %s\n\n", evt["type"], string(b))
		if fl != nil {
			fl.Flush()
		}
	}
	var comp struct {
		Choices []struct {
			Message struct {
				Content          string `json:"content"`
				ReasoningContent string `json:"reasoning_content"`
				ToolCalls        []struct {
					ID       string `json:"id"`
					Function struct {
						Name      string `json:"name"`
						Arguments string `json:"arguments"`
					} `json:"function"`
				} `json:"tool_calls"`
			} `json:"message"`
			FinishReason string `json:"finish_reason"`
		} `json:"choices"`
	}
	_ = json.Unmarshal(finalBody, &comp)
	text := ""
	reasoning := ""
	stopReason := "end_turn"
	var toolCalls []struct {
		ID       string `json:"id"`
		Function struct {
			Name      string `json:"name"`
			Arguments string `json:"arguments"`
		} `json:"function"`
	}
	if len(comp.Choices) > 0 {
		text = comp.Choices[0].Message.Content
		reasoning = comp.Choices[0].Message.ReasoningContent
		toolCalls = comp.Choices[0].Message.ToolCalls
		if comp.Choices[0].FinishReason == "tool_calls" {
			stopReason = "tool_use"
		}
	}
	send(map[string]interface{}{"type": "message_start", "message": map[string]interface{}{
		"id": "msg_" + randHex(24), "type": "message", "role": "assistant", "model": model,
		"content": []interface{}{}, "stop_reason": nil, "stop_sequence": nil,
		"usage": map[string]interface{}{"input_tokens": 0, "output_tokens": 0},
	}})
	blockIdx := 0
	if reasoning != "" {
		send(map[string]interface{}{"type": "content_block_start", "index": blockIdx, "content_block": map[string]interface{}{"type": "thinking", "thinking": ""}})
		send(map[string]interface{}{"type": "content_block_delta", "index": blockIdx, "delta": map[string]interface{}{"type": "thinking_delta", "thinking": reasoning}})
		send(map[string]interface{}{"type": "content_block_stop", "index": blockIdx})
		blockIdx++
	}
	if text != "" {
		send(map[string]interface{}{"type": "content_block_start", "index": blockIdx, "content_block": map[string]interface{}{"type": "text", "text": ""}})
		send(map[string]interface{}{"type": "content_block_delta", "index": blockIdx, "delta": map[string]interface{}{"type": "text_delta", "text": text}})
		send(map[string]interface{}{"type": "content_block_stop", "index": blockIdx})
		blockIdx++
	}
	for _, tc := range toolCalls {
		input := json.RawMessage(tc.Function.Arguments)
		if len(input) == 0 {
			input = json.RawMessage("{}")
		}
		send(map[string]interface{}{"type": "content_block_start", "index": blockIdx, "content_block": map[string]interface{}{"type": "tool_use", "id": tc.ID, "name": tc.Function.Name, "input": input}})
		send(map[string]interface{}{"type": "content_block_delta", "index": blockIdx, "delta": map[string]interface{}{"type": "input_json_delta", "partial_json": string(input)}})
		send(map[string]interface{}{"type": "content_block_stop", "index": blockIdx})
		blockIdx++
	}
	send(map[string]interface{}{"type": "message_delta", "delta": map[string]interface{}{"stop_reason": stopReason, "stop_sequence": nil}})
	send(map[string]interface{}{"type": "message_stop"})
}