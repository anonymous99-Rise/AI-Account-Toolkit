package proxy

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"mistral-reverse-proxy/internal/httpx"
)

// ============================================================================
// OpenAI Responses API (/v1/responses) ↔ OpenAI chat/completions 协议转换
// 参照 flex go_backend/internal/gateway/responses.go 移植。
// Codex 等客户端默认走 Responses API：入口把 Responses 请求转成 chat/completions，
// 再走本项目统一出口（GLM 工具闭环 / doUpstream），最后把响应转回 Responses 格式
// （非流式 + 流式 SSE），保证工具调用在请求→响应往返中不丢失。
// ============================================================================

// respInputLine Responses API input 中的一条条目。
// 可能是普通消息 {role,content}，也可能是 function_call / function_call_output。
type respInputLine struct {
	Role      string          `json:"role"`
	Type      string          `json:"type"`
	Content   json.RawMessage `json:"content"`
	CallID    string          `json:"call_id"`
	Name      string          `json:"name"`
	Arguments string          `json:"arguments"`
	Output    json.RawMessage `json:"output"`
}

type respTool struct {
	Type        string          `json:"type"`
	Name        string          `json:"name"`
	Description string          `json:"description"`
	Parameters  json.RawMessage `json:"parameters"`
}

// responsesToOpenAIChat 将 Responses API 请求体转为 OpenAI chat/completions 请求体。
// input 数组 → messages；function_call → assistant tool_calls；function_call_output → tool 消息；
// tools → function tools（本地工具 schema 由 chatWithTools 在闭环里注入）。
// 返回 (chatBody, stream, model, err)。
func responsesToOpenAIChat(body []byte) ([]byte, bool, string, error) {
	var req struct {
		Model             string          `json:"model"`
		Instructions      string          `json:"instructions"`
		Input             json.RawMessage `json:"input"`
		Tools             []respTool      `json:"tools"`
		ToolChoice        json.RawMessage `json:"tool_choice"`
		ParallelToolCalls *bool           `json:"parallel_tool_calls"`
		Stream            bool            `json:"stream"`
		MaxOutputTokens   int             `json:"max_output_tokens"`
		Temperature       *float64        `json:"temperature"`
		TopP              *float64        `json:"top_p"`
		Stop              json.RawMessage `json:"stop"`
		Reasoning         json.RawMessage `json:"reasoning"`
	}
	if err := json.Unmarshal(body, &req); err != nil {
		return nil, false, "", err
	}
	if req.Model == "" {
		return nil, false, "", fmt.Errorf("missing model")
	}
	model := normalizeModel(req.Model)

	chat := map[string]interface{}{"model": model, "stream": req.Stream}
	msgs := []map[string]interface{}{}
	if instr := strings.TrimSpace(req.Instructions); instr != "" {
		msgs = append(msgs, map[string]interface{}{"role": "system", "content": instr})
	}

	// input 既可以是字符串（OpenAI Responses API 规范允许），也可以是消息数组。
	var lines []respInputLine
	if len(req.Input) > 0 {
		switch req.Input[0] {
		case '"':
			var s string
			if json.Unmarshal(req.Input, &s) == nil && strings.TrimSpace(s) != "" {
				msgs = append(msgs, map[string]interface{}{"role": "user", "content": s})
			}
		case '[':
			if err := json.Unmarshal(req.Input, &lines); err != nil {
				return nil, false, "", fmt.Errorf("convert responses input: %w", err)
			}
		default:
			// 对象形式的单条消息 {role,content} 也兼容
			var one respInputLine
			if err := json.Unmarshal(req.Input, &one); err == nil && one.Role != "" {
				lines = []respInputLine{one}
			}
		}
	}

	for _, it := range lines {
		switch it.Type {
		case "function_call":
			// 上游是 assistant message；相邻的连续 function_call 归到同一条 assistant
			fc := map[string]interface{}{
				"id":   it.CallID,
				"type": "function",
				"function": map[string]interface{}{
					"name":      it.Name,
					"arguments": respArgString(it.Arguments),
				},
			}
			if n := len(msgs); n > 0 {
				if last, ok := msgs[n-1]["role"].(string); ok && last == "assistant" {
					tcs, _ := msgs[n-1]["tool_calls"].([]map[string]interface{})
					msgs[n-1]["tool_calls"] = append(tcs, fc)
					continue
				}
			}
			msgs = append(msgs, map[string]interface{}{
				"role": "assistant", "content": nil, "tool_calls": []map[string]interface{}{fc},
			})
		case "function_call_output":
			msgs = append(msgs, map[string]interface{}{
				"role": "tool", "tool_call_id": it.CallID, "content": respContentText(it.Output),
			})
		default:
			switch it.Role {
			case "user":
				msgs = append(msgs, map[string]interface{}{"role": "user", "content": respContentText(it.Content)})
			case "assistant":
				msgs = append(msgs, map[string]interface{}{"role": "assistant", "content": respContentText(it.Content)})
			case "system", "developer":
				msgs = append(msgs, map[string]interface{}{"role": "system", "content": respContentText(it.Content)})
			}
		}
	}
	chat["messages"] = msgs

	// tools: Responses 顶层 function 工具 → chat function tools（非 function 类型忽略，
	// 本地文件工具 schema 由 chatWithTools 自动注入）。
	if len(req.Tools) > 0 {
		tools := []map[string]interface{}{}
		for _, t := range req.Tools {
			if t.Type != "" && t.Type != "function" {
				continue
			}
			fn := map[string]interface{}{"name": t.Name}
			if t.Description != "" {
				fn["description"] = t.Description
			}
			if len(t.Parameters) > 0 && string(t.Parameters) != "null" {
				fn["parameters"] = json.RawMessage(t.Parameters)
			}
			tools = append(tools, map[string]interface{}{"type": "function", "function": fn})
		}
		if len(tools) > 0 {
			chat["tools"] = tools
		}
	}

	// tool_choice: "auto"|"none"|"required"|{type:function,name}
	if len(req.ToolChoice) > 0 && string(req.ToolChoice) != "null" {
		var s string
		if json.Unmarshal(req.ToolChoice, &s) == nil {
			if s == "none" || s == "required" || s == "auto" {
				chat["tool_choice"] = s
			}
		} else {
			var tc struct {
				Type string `json:"type"`
				Name string `json:"name"`
			}
			if json.Unmarshal(req.ToolChoice, &tc) == nil && tc.Type == "function" && tc.Name != "" {
				chat["tool_choice"] = map[string]interface{}{
					"type": "function", "function": map[string]interface{}{"name": tc.Name},
				}
			}
		}
	}
	if req.ParallelToolCalls != nil {
		chat["parallel_tool_calls"] = *req.ParallelToolCalls
	}

	if req.MaxOutputTokens > 0 {
		chat["max_tokens"] = req.MaxOutputTokens
	}
	if req.Temperature != nil {
		chat["temperature"] = *req.Temperature
	}
	if req.TopP != nil {
		chat["top_p"] = *req.TopP
	}
	if len(req.Stop) > 0 && string(req.Stop) != "null" {
		chat["stop"] = json.RawMessage(req.Stop)
	}
	// reasoning.effort → reasoning_effort（GLM 只接受 none/high；medium/low/max 等非 none 值 → high）
	if len(req.Reasoning) > 0 && string(req.Reasoning) != "null" {
		var rs struct {
			Effort string `json:"effort"`
		}
		if json.Unmarshal(req.Reasoning, &rs) == nil && rs.Effort != "" {
			switch strings.ToLower(strings.TrimSpace(rs.Effort)) {
			case "none", "off", "disabled", "0":
				chat["reasoning_effort"] = "none"
			default:
				chat["reasoning_effort"] = "high"
			}
		}
	}

	out, err := json.Marshal(chat)
	return out, req.Stream, model, err
}

// respContentText 提取 content 文本：字符串，或 [{type,text}...] 数组。
func respContentText(raw json.RawMessage) string {
	if len(raw) == 0 || string(raw) == "null" {
		return ""
	}
	var s string
	if json.Unmarshal(raw, &s) == nil {
		return s
	}
	var blocks []struct {
		Type string `json:"type"`
		Text string `json:"text"`
	}
	if json.Unmarshal(raw, &blocks) != nil {
		return ""
	}
	var parts []string
	for _, b := range blocks {
		if (b.Type == "input_text" || b.Type == "output_text" || b.Type == "text") && b.Text != "" {
			parts = append(parts, b.Text)
		}
	}
	return strings.Join(parts, "\n")
}

// respArgString 规整 function_call.arguments：确保输出的是 JSON 字符串（chat 要求的格式）。
func respArgString(s string) string {
	if s == "" {
		return "{}"
	}
	if json.Valid([]byte(s)) {
		return s
	}
	if b, err := json.Marshal(s); err == nil {
		return string(b)
	}
	return "{}"
}

// ── Responses 非流式响应 ──

// openAIChatToResponses 非流式：chat/completions completion → Responses response。
func openAIChatToResponses(w http.ResponseWriter, src io.Reader, model string) error {
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
			TotalTokens      int `json:"total_tokens"`
			PromptTokensDetails struct {
				CachedTokens int `json:"cached_tokens"`
			} `json:"prompt_tokens_details"`
			CompletionTokensDetails struct {
				ReasoningTokens int `json:"reasoning_tokens"`
			} `json:"completion_tokens_details"`
		} `json:"usage"`
	}
	if err := json.Unmarshal(msg, &comp); err != nil {
		return err
	}
	if len(comp.Choices) == 0 {
		return fmt.Errorf("upstream: empty choices")
	}

	status := "completed"
	switch comp.Choices[0].FinishReason {
	case "length", "content_filter":
		status = "incomplete"
	}

	output := []map[string]interface{}{}
	// 思考完整透传：reasoning_content → Responses reasoning item
	if rc := comp.Choices[0].Message.ReasoningContent; rc != "" {
		output = append(output, map[string]interface{}{
			"type":   "reasoning",
			"id":     "rs_" + randHex(24),
			"status": "completed",
			"summary": []map[string]interface{}{
				{"type": "summary_text", "text": rc},
			},
		})
	}
	if text := comp.Choices[0].Message.Content; text != "" {
		output = append(output, map[string]interface{}{
			"type":   "message",
			"id":     "msg_" + randHex(24),
			"role":   "assistant",
			"status": "completed",
			"content": []map[string]interface{}{
				{"type": "output_text", "text": text, "annotations": []interface{}{}},
			},
		})
	}
	for _, tc := range comp.Choices[0].Message.ToolCalls {
		output = append(output, map[string]interface{}{
			"type":      "function_call",
			"id":        "fc_" + randHex(24),
			"call_id":   tc.ID,
			"name":      tc.Function.Name,
			"arguments": respArgString(tc.Function.Arguments),
			"status":    "completed",
		})
	}

	usage := map[string]interface{}{
		"input_tokens":          comp.Usage.PromptTokens,
		"output_tokens":         comp.Usage.CompletionTokens,
		"total_tokens":          comp.Usage.TotalTokens,
		"input_tokens_details":  map[string]interface{}{"cached_tokens": comp.Usage.PromptTokensDetails.CachedTokens},
		"output_tokens_details": map[string]interface{}{"reasoning_tokens": comp.Usage.CompletionTokensDetails.ReasoningTokens},
	}
	if usageInt(comp.Usage.TotalTokens) == 0 {
		usage["total_tokens"] = usageInt(comp.Usage.PromptTokens) + usageInt(comp.Usage.CompletionTokens)
	}

	respOut := map[string]interface{}{
		"id":         "resp_" + randHex(24),
		"object":     "response",
		"created_at": time.Now().Unix(),
		"status":     status,
		"model":      model,
		"output":     output,
		"usage":      usage,
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(200)
	return json.NewEncoder(w).Encode(respOut)
}

func usageInt(n int) int {
	if n < 0 {
		return 0
	}
	return n
}

// ── Responses 流式响应 (SSE) ──

// respSSE 流式状态。
type respSSE struct {
	w            http.ResponseWriter
	model        string
	respID       string
	outputIndex  int
	reasoningIdx int // 思考 item 的 output_index（-1 未打开）
	usage        map[string]interface{}
	fl           http.Flusher
}

// emit 发送一条 SSE 事件。
func (s *respSSE) emit(event string, data map[string]interface{}) {
	b, _ := json.Marshal(data)
	fmt.Fprintf(s.w, "event: %s\ndata: %s\n\n", event, b)
	if s.fl != nil {
		s.fl.Flush()
	}
}

// skeleton 返回一个嵌入各事件的 response 骨架（含 header + status）。
func (s *respSSE) skeleton(status string) map[string]interface{} {
	return map[string]interface{}{
		"id":         s.respID,
		"object":     "response",
		"created_at": time.Now().Unix(),
		"status":     status,
		"model":      s.model,
		"output":     []interface{}{},
	}
}

// streamOpenAIChatToResponses 流式：chat completion chunk SSE → Responses SSE。
func streamOpenAIChatToResponses(w http.ResponseWriter, src io.Reader, model string) error {
	w.Header().Set("Content-Type", "text/event-stream; charset=utf-8")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(200)

	fl, _ := w.(http.Flusher)
	s := &respSSE{w: w, model: model, respID: "resp_" + randHex(24), reasoningIdx: -1, fl: fl}

	// 文本 item 状态（独立于工具 item：上游交错输出时二者可共存）
	var textOpen bool
	var textItemID string
	var textContent strings.Builder
	// 思考 item 状态：id 与全文在 added/done 间保持一致
	var reasoningItemID string
	var reasoningText strings.Builder

	// funcCallState 单个并行工具调用的完整状态（按上游 tool_calls index 区分）。
	type funcCallState struct {
		outputIdx int
		itemID    string // 输出 fc_xxx id（added/done 一致）
		callID    string // 上游 tool call id
		name      string
		args      strings.Builder
	}
	var openFuncs = map[int]*funcCallState{}
	var funcOrder []int // 打开顺序，关闭时按序补 done 事件

	closeAllItems := func() {
		if textOpen {
			s.emit("response.output_text.done", map[string]interface{}{
				"type": "response.output_text.done", "output_index": s.outputIndex - 1,
				"content_index": 0, "text": textContent.String(),
			})
			s.emit("response.content_part.done", map[string]interface{}{
				"type": "response.content_part.done", "output_index": s.outputIndex - 1, "content_index": 0,
				"part": map[string]interface{}{"type": "output_text", "text": textContent.String(), "annotations": []interface{}{}},
			})
			s.emit("response.output_item.done", map[string]interface{}{
				"type": "response.output_item.done", "output_index": s.outputIndex - 1,
				"item": map[string]interface{}{
					"type": "message", "id": textItemID, "role": "assistant", "status": "completed",
					"content": []map[string]interface{}{{"type": "output_text", "text": textContent.String(), "annotations": []interface{}{}}},
				},
			})
			textOpen = false
		}
		for _, idx := range funcOrder {
			st := openFuncs[idx]
			s.emit("response.function_call_arguments.done", map[string]interface{}{
				"type": "response.function_call_arguments.done", "output_index": st.outputIdx,
				"item_id": st.itemID, "arguments": respArgString(st.args.String()),
			})
			s.emit("response.output_item.done", map[string]interface{}{
				"type": "response.output_item.done", "output_index": st.outputIdx,
				"item": map[string]interface{}{
					"type": "function_call", "id": st.itemID, "call_id": st.callID,
					"name": st.name, "arguments": respArgString(st.args.String()), "status": "completed",
				},
			})
			delete(openFuncs, idx)
		}
		funcOrder = nil
	}

	s.emit("response.created", map[string]interface{}{"type": "response.created", "response": s.skeleton("in_progress")})
	s.emit("response.in_progress", map[string]interface{}{"type": "response.in_progress", "response": s.skeleton("in_progress")})

	finish := func(status string) {
		closeAllItems()
		// 思考 item 若未随文本关闭，兜底关闭（id 与全文保持一致）
		if s.reasoningIdx >= 0 {
			summary := []map[string]interface{}{}
			if reasoningText.Len() > 0 {
				summary = append(summary, map[string]interface{}{"type": "summary_text", "text": reasoningText.String()})
			}
			s.emit("response.reasoning_summary_text.done", map[string]interface{}{
				"type": "response.reasoning_summary_text.done", "output_index": s.reasoningIdx,
				"summary_index": 0, "text": reasoningText.String(),
			})
			s.emit("response.reasoning_summary_part.done", map[string]interface{}{
				"type": "response.reasoning_summary_part.done", "output_index": s.reasoningIdx,
				"summary_index": 0, "part": map[string]interface{}{"type": "summary_text", "text": reasoningText.String()},
			})
			s.emit("response.output_item.done", map[string]interface{}{
				"type": "response.output_item.done", "output_index": s.reasoningIdx,
				"item": map[string]interface{}{
					"type": "reasoning", "id": reasoningItemID, "summary": summary,
					"status": "completed",
				},
			})
			s.reasoningIdx = -1
		}
		resp := s.skeleton(status)
		if s.usage != nil {
			resp["usage"] = s.usage
		}
		s.emit("response.completed", map[string]interface{}{"type": "response.completed", "response": resp})
		s.emit("response.done", map[string]interface{}{"type": "response.done", "response": resp})
	}

	sc := streamLines(src)
	timer := time.NewTimer(keepaliveInterval)
	defer timer.Stop()
	// finish 到达后不立即收尾：上游 usage 在 finish 之后的独立 chunk 里，
	// 等拿到 usage（或流结束）再发 response.completed，否则用量恒为 0
	var pendingFinish string
	statusFor := func(f string) string {
		if f == "length" {
			return "incomplete"
		}
		return "completed"
	}
	for {
		select {
		case res, ok := <-sc:
			if !ok {
				// 上游正常 EOF（可能已含 [DONE]）
				if pendingFinish != "" {
					finish(statusFor(pendingFinish))
				} else {
					finish("incomplete")
				}
				return nil
			}
			if res.err != nil {
				// 上游读错误/中断：按已收集内容优雅收尾
				if pendingFinish != "" {
					finish(statusFor(pendingFinish))
				} else {
					finish("incomplete")
				}
				return nil
			}
			line := res.line
			if !strings.HasPrefix(line, "data:") {
				timer.Reset(keepaliveInterval)
				continue
			}
			data := strings.TrimSpace(strings.TrimPrefix(line, "data:"))
			if data == "[DONE]" {
				if pendingFinish != "" {
					finish(statusFor(pendingFinish))
				} else {
					finish("incomplete")
				}
				return nil
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
					FinishReason *string `json:"finish_reason"`
				} `json:"choices"`
				Usage *struct {
					PromptTokens     int `json:"prompt_tokens"`
					CompletionTokens int `json:"completion_tokens"`
					TotalTokens      int `json:"total_tokens"`
					PromptTokensDetails struct {
						CachedTokens int `json:"cached_tokens"`
					} `json:"prompt_tokens_details"`
					CompletionTokensDetails struct {
						ReasoningTokens int `json:"reasoning_tokens"`
					} `json:"completion_tokens_details"`
				} `json:"usage"`
			}
			if json.Unmarshal([]byte(data), &chunk) != nil {
				timer.Reset(keepaliveInterval)
				continue
			}
			if chunk.Usage != nil {
				// 每次更新（上游可能中途/末尾各发一次，以最后一次为准）
				tt := chunk.Usage.TotalTokens
				if tt == 0 {
					tt = chunk.Usage.PromptTokens + chunk.Usage.CompletionTokens
				}
				s.usage = map[string]interface{}{
					"input_tokens":          chunk.Usage.PromptTokens,
					"output_tokens":         chunk.Usage.CompletionTokens,
					"total_tokens":          tt,
					"input_tokens_details":  map[string]interface{}{"cached_tokens": chunk.Usage.PromptTokensDetails.CachedTokens},
					"output_tokens_details": map[string]interface{}{"reasoning_tokens": chunk.Usage.CompletionTokensDetails.ReasoningTokens},
				}
				// 收尾中的 usage 已到位：立即完成
				if pendingFinish != "" {
					finish(statusFor(pendingFinish))
					return nil
				}
			}
			if len(chunk.Choices) == 0 {
				timer.Reset(keepaliveInterval)
				continue
			}
			c := chunk.Choices[0]

			// 思考增量：上游 reasoning_content → Responses reasoning item
			if c.Delta.ReasoningContent != "" {
				if s.reasoningIdx < 0 {
					s.reasoningIdx = s.outputIndex
					s.outputIndex++
					reasoningItemID = "rs_" + randHex(24)
					reasoningText.Reset()
					s.emit("response.output_item.added", map[string]interface{}{
						"type": "response.output_item.added", "output_index": s.reasoningIdx,
						"item": map[string]interface{}{
							"type": "reasoning", "id": reasoningItemID,
							"summary": []interface{}{}, "status": "in_progress",
						},
					})
					s.emit("response.reasoning_summary_part.added", map[string]interface{}{
						"type": "response.reasoning_summary_part.added", "output_index": s.reasoningIdx,
						"summary_index": 0, "part": map[string]interface{}{"type": "summary_text", "text": ""},
					})
				}
				reasoningText.WriteString(c.Delta.ReasoningContent)
				s.emit("response.reasoning_summary_text.delta", map[string]interface{}{
					"type":         "response.reasoning_summary_text.delta",
					"output_index": s.reasoningIdx,
					"delta":        c.Delta.ReasoningContent,
				})
			}

			// 文本增量：先关闭思考 item（带全文与一致 id）
			if c.Delta.Content != "" && s.reasoningIdx >= 0 {
				summary := []map[string]interface{}{}
				if reasoningText.Len() > 0 {
					summary = append(summary, map[string]interface{}{"type": "summary_text", "text": reasoningText.String()})
				}
				s.emit("response.reasoning_summary_text.done", map[string]interface{}{
					"type": "response.reasoning_summary_text.done", "output_index": s.reasoningIdx,
					"summary_index": 0, "text": reasoningText.String(),
				})
				s.emit("response.reasoning_summary_part.done", map[string]interface{}{
					"type": "response.reasoning_summary_part.done", "output_index": s.reasoningIdx,
					"summary_index": 0, "part": map[string]interface{}{"type": "summary_text", "text": reasoningText.String()},
				})
				s.emit("response.output_item.done", map[string]interface{}{
					"type": "response.output_item.done", "output_index": s.reasoningIdx,
					"item": map[string]interface{}{
						"type": "reasoning", "id": reasoningItemID, "summary": summary,
						"status": "completed",
					},
				})
				s.reasoningIdx = -1
			}

			// 文本增量（id 与 done 一致）
			if c.Delta.Content != "" {
				if !textOpen {
					textOpen = true
					textItemID = "msg_" + randHex(24)
					textContent.Reset()
					idx := s.outputIndex
					s.outputIndex++
					s.emit("response.output_item.added", map[string]interface{}{
						"type": "response.output_item.added", "output_index": idx,
						"item": map[string]interface{}{
							"type": "message", "id": textItemID, "role": "assistant",
							"status": "in_progress", "content": []interface{}{},
						},
					})
					s.emit("response.content_part.added", map[string]interface{}{
						"type": "response.content_part.added", "output_index": idx, "content_index": 0,
						"part": map[string]interface{}{"type": "output_text", "text": "", "annotations": []interface{}{}},
					})
				}
				textContent.WriteString(c.Delta.Content)
				s.emit("response.output_text.delta", map[string]interface{}{
					"type": "response.output_text.delta", "output_index": s.outputIndex - 1,
					"content_index": 0, "delta": c.Delta.Content,
				})
			}

			// 工具调用增量：按上游 index 独立跟踪，支持并行多个工具调用
			for _, tc := range c.Delta.ToolCalls {
				if tc.Index < 0 {
					tc.Index = 0
				}
				st, ok := openFuncs[tc.Index]
				if !ok {
					st = &funcCallState{
						outputIdx: s.outputIndex,
						itemID:    "fc_" + randHex(24),
						callID:    tc.ID,
						name:      tc.Function.Name,
					}
					s.outputIndex++
					openFuncs[tc.Index] = st
					funcOrder = append(funcOrder, tc.Index)
					s.emit("response.output_item.added", map[string]interface{}{
						"type": "response.output_item.added", "output_index": st.outputIdx,
						"item": map[string]interface{}{
							"type": "function_call", "id": st.itemID, "call_id": st.callID,
							"name": st.name, "arguments": "", "status": "in_progress",
						},
					})
				}
				if tc.ID != "" {
					st.callID = tc.ID
				}
				if tc.Function.Name != "" {
					st.name = tc.Function.Name
				}
				if tc.Function.Arguments != "" {
					st.args.WriteString(tc.Function.Arguments)
					s.emit("response.function_call_arguments.delta", map[string]interface{}{
						"type": "response.function_call_arguments.delta", "output_index": st.outputIdx,
						"item_id": st.itemID, "delta": tc.Function.Arguments,
					})
				}
			}

			// 结束：标记 pending，等待 usage chunk（或流结束）后收尾
			if c.FinishReason != nil && *c.FinishReason != "" && pendingFinish == "" {
				pendingFinish = *c.FinishReason
				if chunk.Usage != nil {
					finish(statusFor(pendingFinish))
					return nil
				}
			}
			timer.Reset(keepaliveInterval)
		case <-timer.C:
			// 上游长时间无输出（长思考）：发 Responses 标准 ping 事件保活
			s.emit("response.in_progress", map[string]interface{}{"type": "response.in_progress", "response": s.skeleton("in_progress")})
		}
	}
}

// ── 流式辅助 ──

// streamLine 单行读取结果。
type streamLine struct {
	line string
	err  error
}

// streamLines 在后台 goroutine 逐行读 src，通过 channel 返回；
// 主循环可对 channel select，实现"超时无数据时发 ping 保活"。
func streamLines(src io.Reader) <-chan streamLine {
	ch := make(chan streamLine, 4)
	go func() {
		sc := bufio.NewScanner(src)
		sc.Buffer(make([]byte, 1024*1024), 1024*1024)
		for sc.Scan() {
			ch <- streamLine{line: sc.Text()}
		}
		if err := sc.Err(); err != nil {
			ch <- streamLine{err: err}
			return
		}
		close(ch)
	}()
	return ch
}

// keepaliveInterval 流式无数据保活间隔。
const keepaliveInterval = 15 * time.Second

// ── /v1/responses handler ──

// HandleResponses POST /v1/responses（OpenAI Responses 协议统一出口）：
// Responses 请求 → 转 chat/completions → GLM+工具走本地工具调用闭环 / 其余 doUpstream →
// 响应转回 Responses（非流式 + 流式 SSE）。工具调用在请求→响应往返中不丢失。
func (p *Proxy) HandleResponses(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, maxBodySize))
	if err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "读取请求体失败: "+err.Error(), "bad_request")
		return
	}
	chatBody, streaming, model, err := responsesToOpenAIChat(body)
	if err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "convert responses: "+err.Error(), "bad_request")
		return
	}
	var m map[string]any
	if err := json.Unmarshal(chatBody, &m); err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "内部转换失败: "+err.Error(), "bad_request")
		return
	}
	if err := p.prepareRequest(m); err != nil {
		httpx.WriteError(w, http.StatusBadRequest, err.Error(), "bad_request")
		return
	}
	model = normalizeModel(model)

	// GLM + 有工具 → 会话工具通道（passthrough 客户端驱动 / local 代理闭环）。
	_, hasTools := m["tools"].([]any)
	if isGLMModel(model) && hasTools {
		m["stream"] = false
		b, convID, status, err := p.chatWithToolsMode(r.Context(), "", m, p.cfg.ToolMode == "local")
		if err != nil {
			if status != 0 {
				p.writeUpstreamError(w, status, b)
			} else {
				httpx.WriteError(w, http.StatusBadGateway, "工具闭环失败: "+errText(err), "upstream_error")
			}
			return
		}
		if streaming {
			p.writeSimulatedResponsesStream(w, b, model, convID)
		} else {
			if convID != "" {
				w.Header().Set("X-Conversation-ID", convID)
			}
			if err := openAIChatToResponses(w, bytes.NewReader(b), model); err != nil {
				httpx.WriteError(w, http.StatusBadGateway, "转换响应失败: "+errText(err), "upstream_error")
			}
		}
		return
	}

	// 其余：普通转发上游
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

	// 非 GLM + 流式：上游返回 chat SSE，直接转 Responses SSE。
	if streaming && !isGLMModel(model) {
		br := bufio.NewReader(resp.Body)
		peek, _ := br.Peek(2)
		if len(peek) > 0 && peek[0] == '{' {
			// 上游偶发对 stream=true 返回完整 JSON（非 SSE），嗅探后走非流式转换
			if err := openAIChatToResponses(w, br, model); err != nil {
				httpx.WriteError(w, http.StatusBadGateway, "转换响应失败: "+errText(err), "upstream_error")
			}
			return
		}
		if err := streamOpenAIChatToResponses(w, br, model); err != nil {
			httpx.WriteError(w, http.StatusBadGateway, "转换响应失败: "+errText(err), "upstream_error")
		}
		return
	}

	// 非流式 / GLM（conversations 恒非流式）：读完整响应统一转换。
	all, _ := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	var openaiBody []byte
	convID := ""
	if isGLMModel(model) {
		openaiBody = convertConversationsToOpenAI(all)
		convID = conversationIDFromOutputs(all)
		if convID == "" {
			convID = p.extractConversationID(resp.Header, all)
		}
	} else {
		openaiBody = all
	}
	if streaming {
		p.writeSimulatedResponsesStream(w, openaiBody, model, convID)
		return
	}
	if convID != "" {
		w.Header().Set("X-Conversation-ID", convID)
	}
	if err := openAIChatToResponses(w, bytes.NewReader(openaiBody), model); err != nil {
		httpx.WriteError(w, http.StatusBadGateway, "转换响应失败: "+errText(err), "upstream_error")
	}
}

// writeSimulatedResponsesStream 用完整 OpenAI 响应模拟 Responses SSE 流式输出
// （GLM 工具闭环/会话为非流式，先拿完整响应再按 output_item/delta/done 事件流式回放）。
func (p *Proxy) writeSimulatedResponsesStream(w http.ResponseWriter, b []byte, model, convID string) {
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
		} `json:"choices"`
		Usage struct {
			PromptTokens     int `json:"prompt_tokens"`
			CompletionTokens int `json:"completion_tokens"`
			TotalTokens      int `json:"total_tokens"`
		} `json:"usage"`
	}
	_ = json.Unmarshal(b, &comp)

	h := w.Header()
	h.Set("Content-Type", "text/event-stream; charset=utf-8")
	h.Set("Cache-Control", "no-cache")
	h.Set("Connection", "keep-alive")
	h.Set("X-Accel-Buffering", "no")
	if convID != "" {
		h.Set("X-Conversation-ID", convID)
	}
	w.WriteHeader(http.StatusOK)
	fl, _ := w.(http.Flusher)
	emit := func(evt map[string]any) {
		bb, _ := json.Marshal(evt)
		fmt.Fprintf(w, "event: %s\ndata: %s\n\n", evt["type"], string(bb))
		if fl != nil {
			fl.Flush()
		}
	}
	respID := "resp_" + randHex(24)
	skeleton := func(status string) map[string]any {
		return map[string]any{
			"id": respID, "object": "response", "created_at": time.Now().Unix(),
			"status": status, "model": model, "output": []any{},
		}
	}
	emit(map[string]any{"type": "response.created", "response": skeleton("in_progress")})
	emit(map[string]any{"type": "response.in_progress", "response": skeleton("in_progress")})

	outputIdx := 0
	if len(comp.Choices) > 0 {
		msg := comp.Choices[0].Message
		if rc := msg.ReasoningContent; rc != "" {
			rid := "rs_" + randHex(24)
			idx := outputIdx
			outputIdx++
			emit(map[string]any{"type": "response.output_item.added", "output_index": idx,
				"item": map[string]any{"type": "reasoning", "id": rid, "summary": []any{}, "status": "in_progress"}})
			emit(map[string]any{"type": "response.reasoning_summary_part.added", "output_index": idx,
				"summary_index": 0, "part": map[string]any{"type": "summary_text", "text": ""}})
			for _, ch := range runeChunks(rc, 20) {
				emit(map[string]any{"type": "response.reasoning_summary_text.delta", "output_index": idx,
					"delta": ch})
			}
			emit(map[string]any{"type": "response.reasoning_summary_text.done", "output_index": idx,
				"summary_index": 0, "text": rc})
			emit(map[string]any{"type": "response.reasoning_summary_part.done", "output_index": idx,
				"summary_index": 0, "part": map[string]any{"type": "summary_text", "text": rc}})
			emit(map[string]any{"type": "response.output_item.done", "output_index": idx,
				"item": map[string]any{"type": "reasoning", "id": rid, "summary": []map[string]any{{"type": "summary_text", "text": rc}}, "status": "completed"}})
		}
		if text := msg.Content; text != "" {
			tid := "msg_" + randHex(24)
			idx := outputIdx
			outputIdx++
			emit(map[string]any{"type": "response.output_item.added", "output_index": idx,
				"item": map[string]any{"type": "message", "id": tid, "role": "assistant", "status": "in_progress", "content": []any{}}})
			emit(map[string]any{"type": "response.content_part.added", "output_index": idx, "content_index": 0,
				"part": map[string]any{"type": "output_text", "text": "", "annotations": []any{}}})
			for _, ch := range runeChunks(text, 20) {
				emit(map[string]any{"type": "response.output_text.delta", "output_index": idx,
					"content_index": 0, "delta": ch})
			}
			emit(map[string]any{"type": "response.output_text.done", "output_index": idx,
				"content_index": 0, "text": text})
			emit(map[string]any{"type": "response.content_part.done", "output_index": idx, "content_index": 0,
				"part": map[string]any{"type": "output_text", "text": text, "annotations": []any{}}})
			emit(map[string]any{"type": "response.output_item.done", "output_index": idx,
				"item": map[string]any{"type": "message", "id": tid, "role": "assistant", "status": "completed",
					"content": []map[string]any{{"type": "output_text", "text": text, "annotations": []any{}}}}})
		}
		for _, tc := range msg.ToolCalls {
			fid := "fc_" + randHex(24)
			args := respArgString(tc.Function.Arguments)
			idx := outputIdx
			outputIdx++
			emit(map[string]any{"type": "response.output_item.added", "output_index": idx,
				"item": map[string]any{"type": "function_call", "id": fid, "call_id": tc.ID,
					"name": tc.Function.Name, "arguments": "", "status": "in_progress"}})
			for _, ch := range runeChunks(args, 20) {
				emit(map[string]any{"type": "response.function_call_arguments.delta", "output_index": idx,
					"item_id": fid, "delta": ch})
			}
			emit(map[string]any{"type": "response.function_call_arguments.done", "output_index": idx,
				"item_id": fid, "arguments": args})
			emit(map[string]any{"type": "response.output_item.done", "output_index": idx,
				"item": map[string]any{"type": "function_call", "id": fid, "call_id": tc.ID,
					"name": tc.Function.Name, "arguments": args, "status": "completed"}})
		}
	}

	usage := map[string]any{
		"input_tokens":  comp.Usage.PromptTokens,
		"output_tokens": comp.Usage.CompletionTokens,
		"total_tokens":  comp.Usage.TotalTokens,
	}
	if usageInt(comp.Usage.TotalTokens) == 0 {
		usage["total_tokens"] = usageInt(comp.Usage.PromptTokens) + usageInt(comp.Usage.CompletionTokens)
	}
	resp := skeleton("completed")
	resp["usage"] = usage
	emit(map[string]any{"type": "response.completed", "response": resp})
	emit(map[string]any{"type": "response.done", "response": resp})
}