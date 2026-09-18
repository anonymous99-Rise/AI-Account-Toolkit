package proxy

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

// ============================================================================
// 本地工具调用（Function Calling）闭环
// 参照 tool-calling/本地工具调用实现文档.md 的 RunContext + register_func 机制。
// 协议：模型返回 function.call → 本地执行注册工具 → append function.result 回传 → 模型生成最终回复。
// ============================================================================

// ToolFunc 本地工具函数：入参 JSON map，返回结果字符串。
type ToolFunc func(args map[string]any) (string, error)

// tools 内置工具注册表。
var tools = map[string]ToolFunc{
	"list_directory": toolListDirectory,
	"read_file":      toolReadFile,
	"write_file":     toolWriteFile,
	"append_file":    toolAppendFile,
}

// toolSchema OpenAI function schema（供注入 tools）。
var localToolSchemas = []any{
	map[string]any{"type": "function", "function": map[string]any{
		"name":        "list_directory",
		"description": "列出指定目录下的所有文件和子目录",
		"parameters": map[string]any{
			"type":     "object",
			"properties": map[string]any{"path": map[string]any{"type": "string"}},
			"required": []string{"path"},
		},
	}},
	map[string]any{"type": "function", "function": map[string]any{
		"name":        "read_file",
		"description": "读取本地文件的完整内容",
		"parameters": map[string]any{
			"type":     "object",
			"properties": map[string]any{"path": map[string]any{"type": "string"}},
			"required": []string{"path"},
		},
	}},
	map[string]any{"type": "function", "function": map[string]any{
		"name":        "write_file",
		"description": "写入内容到本地文件（覆盖）",
		"parameters": map[string]any{
			"type":     "object",
			"properties": map[string]any{
				"path":    map[string]any{"type": "string"},
				"content": map[string]any{"type": "string"},
			},
			"required": []string{"path", "content"},
		},
	}},
	map[string]any{"type": "function", "function": map[string]any{
		"name":        "append_file",
		"description": "追加内容到本地文件末尾",
		"parameters": map[string]any{
			"type":     "object",
			"properties": map[string]any{
				"path":    map[string]any{"type": "string"},
				"content": map[string]any{"type": "string"},
			},
			"required": []string{"path", "content"},
		},
	}},
}

func toolListDirectory(args map[string]any) (string, error) {
	path, _ := args["path"].(string)
	if path == "" {
		return "", fmt.Errorf("缺少 path 参数")
	}
	entries, err := os.ReadDir(path)
	if err != nil {
		return fmt.Sprintf("目录不存在或无法读取: %s", path), nil
	}
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("目录 %s 内容:\n", path))
	for _, e := range entries {
		info, ierr := e.Info()
		size := "-"
		if ierr == nil {
			size = fmt.Sprintf("%d", info.Size())
		}
		kind := "FILE"
		if e.IsDir() {
			kind = "DIR "
		}
		sb.WriteString(fmt.Sprintf("%s %s %s\n", kind, size, e.Name()))
	}
	return strings.TrimRight(sb.String(), "\n"), nil
}

func toolReadFile(args map[string]any) (string, error) {
	path, _ := args["path"].(string)
	if path == "" {
		return "", fmt.Errorf("缺少 path 参数")
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return fmt.Sprintf("文件不存在: %s", path), nil
	}
	return fmt.Sprintf("文件 %s 内容 (%d 字符):\n%s", path, len(b), string(b)), nil
}

func toolWriteFile(args map[string]any) (string, error) {
	path, _ := args["path"].(string)
	content, _ := args["content"].(string)
	if path == "" {
		return "", fmt.Errorf("缺少 path 参数")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return "", err
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		return "", err
	}
	return fmt.Sprintf("已写入文件 %s (%d 字符)", path, len(content)), nil
}

func toolAppendFile(args map[string]any) (string, error) {
	path, _ := args["path"].(string)
	content, _ := args["content"].(string)
	if path == "" {
		return "", fmt.Errorf("缺少 path 参数")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return "", err
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return "", err
	}
	defer f.Close()
	if _, err := f.WriteString("\n" + content); err != nil {
		return "", err
	}
	return fmt.Sprintf("已追加内容到 %s", path), nil
}

// runTools 执行 function.call 条目，返回 function.result 列表。
// conversations 响应的 outputs 里 type=function.call 的条目携带 tool_call_id/name/arguments。
func runTools(outputs []any) []any {
	var results []any
	for _, o := range outputs {
		om, ok := o.(map[string]any)
		if !ok {
			continue
		}
		if t, _ := om["type"].(string); t != "function.call" {
			continue
		}
		toolCallID, _ := om["tool_call_id"].(string)
		name, _ := om["name"].(string)
		argsRaw, _ := om["arguments"].(string)
		var args map[string]any
		_ = json.Unmarshal([]byte(argsRaw), &args)
		if args == nil {
			args = map[string]any{}
		}
		result := "tool not found"
		if fn, ok := tools[name]; ok {
			res, err := fn(args)
			if err != nil {
				result = "tool error: " + err.Error()
			} else {
				result = res
			}
		}
		results = append(results, map[string]any{
			"object":       "entry",
			"type":         "function.result",
			"tool_call_id": toolCallID,
			"result":       result,
		})
	}
	return results
}

// conversationIDFromOutputs 从 conversations 响应里取 conversation_id。
func conversationIDFromOutputs(body []byte) string {
	var r struct {
		ConversationID string `json:"conversation_id"`
	}
	_ = json.Unmarshal(body, &r)
	return r.ConversationID
}

// hasFunctionCalls 检查 conversations 响应是否包含 function.call 条目。
func hasFunctionCalls(body []byte) bool {
	var r struct {
		Outputs []struct {
			Type string `json:"type"`
		} `json:"outputs"`
	}
	if json.Unmarshal(body, &r) != nil {
		return false
	}
	for _, o := range r.Outputs {
		if o.Type == "function.call" {
			return true
		}
	}
	return false
}

// appendToolResults 把 function.result 列表 append 到现有会话，返回上游响应。
func (p *Proxy) appendToolResults(ctx context.Context, convID string, results []any) ([]byte, int, error) {
	entry := p.pool.PickUpstream()
	if entry == nil {
		return nil, 0, fmt.Errorf("上游 key 池为空")
	}
	body := map[string]any{"inputs": results}
	raw, _ := json.Marshal(body)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		p.cfg.UpstreamBase+"/conversations/"+convID, strings.NewReader(string(raw)))
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+entry.Key)
	req.Header.Set("Accept", "application/json")
	resp, err := p.client.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	b, err := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	if resp.StatusCode != 200 {
		return b, resp.StatusCode, fmt.Errorf("append 失败: %d", resp.StatusCode)
	}
	return b, 0, nil
}

// chatWithTools 走 Conversations 工具调用闭环：
// 创建/追加会话，循环处理 function.call → 本地执行 → function.result，直到模型给出最终文本。
// passthrough=true 时（客户端驱动工具，如 opencode/Claude Code）：遇到 function.call 立即转换返回，
// 由客户端本机执行后回传 tool results（透传，不本地执行）。
// 返回最终 OpenAI 兼容响应字节 + conversation_id。
func (p *Proxy) chatWithTools(ctx context.Context, convID string, body map[string]any) ([]byte, string, int, error) {
	return p.chatWithToolsMode(ctx, convID, body, p.cfg.ToolMode == "local")
}

// chatWithToolsMode 透传/闭环共用的会话工具循环。
// local=true 走本地执行闭环（Playground），local=false 走客户端透传（opencode/Claude Code）。
func (p *Proxy) chatWithToolsMode(ctx context.Context, convID string, body map[string]any, local bool) ([]byte, string, int, error) {
	model, _ := body["model"].(string)
	payload := buildConversationsReq(body)
	// 本地闭环模式：注入本地工具 schema；透传模式只透传客户端自己的 tools。
	if local {
		// 注入本地工具 schema + 客户端工具（裸类型 tools 转 function 后合并）。
		// conversations 工具格式：本地文件工具用 function schema，上游沙盒工具（code_interpreter 等）用裸类型。
		localTools := append([]any(nil), localToolSchemas...)
		var bareTools []any
		if tools, ok := payload["tools"]; ok {
			if arr, ok := tools.([]any); ok {
				for _, t := range arr {
					if om, ok := t.(map[string]any); ok {
						if tp, _ := om["type"].(string); tp != "" && tp != "function" {
							bareTools = append(bareTools, om)
						}
					}
				}
			}
		}
		payload["tools"] = append(localTools, bareTools...)
	}

	curConvID := convID
	for round := 0; round < 8; round++ {
		var raw []byte
		var ep string
		if curConvID == "" {
			// 新建会话：带 model + inputs + tools + completion_args
			raw, _ = json.Marshal(payload)
			ep = "/conversations"
		} else {
			// 追加会话：POST /conversations/{id}，不接受 model 字段，只带 inputs
			appendBody := map[string]any{"inputs": payload["inputs"]}
			if args, ok := payload["completion_args"]; ok {
				appendBody["completion_args"] = args
			}
			raw, _ = json.Marshal(appendBody)
			ep = "/conversations/" + curConvID
		}
		entry := p.pool.PickUpstream()
		if entry == nil {
			return nil, "", 0, fmt.Errorf("上游 key 池为空")
		}
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, p.cfg.UpstreamBase+ep, strings.NewReader(string(raw)))
		if err != nil {
			return nil, "", 0, err
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", "Bearer "+entry.Key)
		req.Header.Set("Accept", "application/json")
		resp, err := p.client.Do(req)
		if err != nil {
			return nil, "", 0, err
		}
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
		_ = resp.Body.Close()
		if resp.StatusCode != 200 {
			return b, "", resp.StatusCode, fmt.Errorf("upstream %d", resp.StatusCode)
		}
		if curConvID == "" {
			curConvID = conversationIDFromOutputs(b)
		}
		if hasFunctionCalls(b) {
			if !local {
				// 透传模式：把 function.call 直接转 OpenAI tool_calls 返回，由客户端执行。
				// 客户端下次请求带完整历史（assistant tool_calls + tool 消息），buildConversationsReq 会重建。
				return convertConversationsToOpenAI(b), curConvID, 0, nil
			}
			// 本地闭环：执行工具 → 追加 → 继续下一轮
			results := runTools(extractOutputs(b))
			if len(results) == 0 {
				break
			}
			payload = map[string]any{"model": model, "inputs": results}
			continue
		}
		// 无工具调用：转 OpenAI 兼容响应返回
		return convertConversationsToOpenAI(b), curConvID, 0, nil
	}
	return nil, "", 0, fmt.Errorf("工具调用循环超限")
}

// extractOutputs 返回 conversations 响应的 outputs 数组。
func extractOutputs(body []byte) []any {
	var r struct {
		Outputs []any `json:"outputs"`
	}
	_ = json.Unmarshal(body, &r)
	return r.Outputs
}