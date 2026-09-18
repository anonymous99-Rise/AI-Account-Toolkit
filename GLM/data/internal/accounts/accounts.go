// Package accounts 管理多账号对话：每个账号是一个独立的 Conversations 会话
// （conversation_id），有独立的模型/采样参数/系统提示词/对话历史，可切换对话。
package accounts

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"mistral-reverse-proxy/internal/httpx"
	"mistral-reverse-proxy/internal/keys"
	"mistral-reverse-proxy/internal/proxy"
)

// Account 一个对话账号。
type Account struct {
	ID             string    `json:"id"`
	Name           string    `json:"name"`
	Model          string    `json:"model"`
	ConversationID string    `json:"conversation_id,omitempty"`
	SystemPrompt   string    `json:"system_prompt,omitempty"`
	Temperature    float64   `json:"temperature"`
	TopP           float64   `json:"top_p"`
	MaxTokens      int       `json:"max_tokens"`
	Reasoning      string    `json:"reasoning_effort"`
	Tools          []string  `json:"tools,omitempty"`
	History        []Message `json:"history,omitempty"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}

// Message 单条对话记录。
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
	Time    string `json:"time"`
}

// Manager 账号管理：持久化到 data/accounts.json。
type Manager struct {
	mu       sync.Mutex
	filePath string
	accounts []*Account
	proxy    *proxy.Proxy
	pool     *keys.Pool
}

func NewManager(filePath string, pr *proxy.Proxy, pool *keys.Pool) *Manager {
	m := &Manager{filePath: filePath, proxy: pr, pool: pool}
	if b, err := os.ReadFile(filePath); err == nil {
		_ = json.Unmarshal(b, &m.accounts)
	}
	if m.accounts == nil {
		m.accounts = []*Account{}
	}
	return m
}

func (m *Manager) save() error {
	if m.filePath == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(m.filePath), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(m.accounts, "", "  ")
	if err != nil {
		return err
	}
	tmp := m.filePath + ".tmp"
	if err := os.WriteFile(tmp, b, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, m.filePath)
}

// Create 新建账号并持久化。
func (m *Manager) Create(name, model string) (*Account, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	a := &Account{
		ID:          fmt.Sprintf("acc_%d", time.Now().UnixNano()),
		Name:        name,
		Model:       model,
		Temperature: 0.7,
		TopP:        1.0,
		MaxTokens:   4096,
		Reasoning:   "none",
		Tools:       []string{"code_interpreter", "image_generation", "web_search"},
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}
	m.accounts = append(m.accounts, a)
	return a, m.save()
}

// List 返回账号列表副本。
func (m *Manager) List() []*Account {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make([]*Account, len(m.accounts))
	for i, a := range m.accounts {
		cp := *a
		cp.History = append([]Message(nil), a.History...)
		out[i] = &cp
	}
	return out
}

// Get 按 ID 取账号。
func (m *Manager) Get(id string) *Account {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, a := range m.accounts {
		if a.ID == id {
			cp := *a
			cp.History = append([]Message(nil), a.History...)
			return &cp
		}
	}
	return nil
}

// Delete 删除账号。
func (m *Manager) Delete(id string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	for i, a := range m.accounts {
		if a.ID == id {
			m.accounts = append(m.accounts[:i], m.accounts[i+1:]...)
			return m.save()
		}
	}
	return fmt.Errorf("账号不存在: %s", id)
}

// Update 更新账号字段。
func (m *Manager) Update(id string, upd map[string]any) (*Account, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, a := range m.accounts {
		if a.ID != id {
			continue
		}
		if v, ok := upd["name"].(string); ok && v != "" {
			a.Name = v
		}
		if v, ok := upd["model"].(string); ok && v != "" {
			a.Model = v
		}
		if v, ok := upd["system_prompt"].(string); ok {
			a.SystemPrompt = v
		}
		if v, ok := upd["temperature"].(float64); ok {
			a.Temperature = v
		}
		if v, ok := upd["top_p"].(float64); ok {
			a.TopP = v
		}
		if v, ok := upd["max_tokens"].(float64); ok {
			a.MaxTokens = int(v)
		}
		if v, ok := upd["reasoning_effort"].(string); ok && v != "" {
			a.Reasoning = v
		}
		if v, ok := upd["conversation_id"].(string); ok {
			a.ConversationID = v
		}
		if v, ok := upd["tools"].([]any); ok {
			var ts []string
			for _, x := range v {
				if s, ok := x.(string); ok {
					ts = append(ts, s)
				}
			}
			a.Tools = ts
		}
		a.UpdatedAt = time.Now()
		return a, m.save()
	}
	return nil, fmt.Errorf("账号不存在: %s", id)
}

// Chat 对账号发起一轮对话（复用 conversation_id 做多轮），返回模型回复。
func (m *Manager) Chat(ctx context.Context, id, userMsg string) (string, string, error) {
	m.mu.Lock()
	var a *Account
	for _, x := range m.accounts {
		if x.ID == id {
			a = x
			break
		}
	}
	if a == nil {
		m.mu.Unlock()
		return "", "", fmt.Errorf("账号不存在: %s", id)
	}
	convID := a.ConversationID
	model := a.Model
	sp := a.SystemPrompt
	temp := a.Temperature
	topP := a.TopP
	maxTok := a.MaxTokens
	reasoning := a.Reasoning
	tools := append([]string(nil), a.Tools...)
	m.mu.Unlock()

	// 组装 OpenAI 兼容请求体
	body := map[string]any{
		"model":            model,
		"temperature":      temp,
		"top_p":            topP,
		"max_tokens":       maxTok,
		"reasoning_effort": reasoning,
	}
	msgs := []any{map[string]any{"role": "user", "content": userMsg}}
	if sp != "" {
		msgs = append([]any{map[string]any{"role": "system", "content": sp}}, msgs...)
	}
	body["messages"] = msgs
	if len(tools) > 0 {
		var ts []any
		for _, t := range tools {
			ts = append(ts, map[string]any{"type": t})
		}
		body["tools"] = ts
	}

	// 走代理的工具闭环（GLM conversations 通道）或普通转发
	respBody, newConvID, status, err := m.proxy.ChatRaw(ctx, convID, body)
	if err != nil {
		return "", "", fmt.Errorf("对话失败: %v", err)
	}
	if status != 0 {
		return "", "", fmt.Errorf("上游错误 %d: %s", status, string(respBody))
	}
	var out struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	_ = json.Unmarshal(respBody, &out)
	reply := ""
	if len(out.Choices) > 0 {
		reply = out.Choices[0].Message.Content
	}

	// 更新会话记录
	m.mu.Lock()
	for _, x := range m.accounts {
		if x.ID == id {
			if newConvID != "" {
				x.ConversationID = newConvID
			}
			x.History = append(x.History,
				Message{Role: "user", Content: userMsg, Time: time.Now().Format("15:04:05")},
				Message{Role: "assistant", Content: reply, Time: time.Now().Format("15:04:05")},
			)
			if len(x.History) > 200 {
				x.History = x.History[len(x.History)-200:]
			}
			x.UpdatedAt = time.Now()
			_ = m.save()
			break
		}
	}
	m.mu.Unlock()
	return reply, newConvID, nil
}

// defaultGreeting 建立会话时使用的默认问候语。
const defaultGreeting = "你好，请简单介绍一下你自己。"

// BatchCreate 批量创建账号：count 个，名字前缀 prefix，模型 model。
// greet 为 true 时每个账号创建后立即发一条问候建立会话（并发上限 3）。
// 返回成功创建的账号列表与错误信息列表（顺序对应 count 序号）。
func (m *Manager) BatchCreate(ctx context.Context, count int, model, prefix string, greet bool) ([]*Account, []string) {
	if count < 1 {
		count = 1
	}
	if count > 100 {
		count = 100
	}
	if model == "" {
		model = "glm-5-2"
	}
	if prefix == "" {
		prefix = "批量号"
	}
	created := make([]*Account, count)
	errStrs := make([]string, count)
	sem := make(chan struct{}, 3)
	var wg sync.WaitGroup
	for i := 0; i < count; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			a, err := m.Create(fmt.Sprintf("%s%d", prefix, i+1), model)
			if err != nil {
				errStrs[i] = fmt.Sprintf("创建第 %d 个失败: %v", i+1, err)
				return
			}
			if greet {
				if _, _, gerr := m.Chat(ctx, a.ID, defaultGreeting); gerr != nil {
					errStrs[i] = fmt.Sprintf("账号 %s 打招呼失败: %v", a.Name, gerr)
				}
			}
			created[i] = a
		}(i)
	}
	wg.Wait()
	out := make([]*Account, 0, count)
	errs := make([]string, 0, count)
	for i, a := range created {
		if a != nil {
			out = append(out, a)
		}
		if errStrs[i] != "" {
			errs = append(errs, errStrs[i])
		}
	}
	return out, errs
}

// Greet 对账号发一条默认问候，建立 conversation_id。
func (m *Manager) Greet(ctx context.Context, id string) (string, string, error) {
	return m.Chat(ctx, id, defaultGreeting)
}

// ResetConversation 清空账号的会话状态（conversation_id + 历史），下次对话为全新会话。
func (m *Manager) ResetConversation(id string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, a := range m.accounts {
		if a.ID == id {
			a.ConversationID = ""
			a.History = nil
			a.UpdatedAt = time.Now()
			return m.save()
		}
	}
	return fmt.Errorf("账号不存在: %s", id)
}

// handleBatch POST /api/accounts/batch：批量注册账号。
func (m *Manager) handleBatch(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Count  int    `json:"count"`
		Model  string `json:"model"`
		Prefix string `json:"prefix"`
		Greet  bool   `json:"greet"`
	}
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "请求体错误: "+errText(err), "bad_request")
		return
	}
	if req.Count < 1 || req.Count > 100 {
		httpx.WriteError(w, http.StatusBadRequest, "count 需在 1~100 之间", "bad_request")
		return
	}
	created, errs := m.BatchCreate(r.Context(), req.Count, req.Model, req.Prefix, req.Greet)
	type createdItem struct {
		ID             string `json:"id"`
		Name           string `json:"name"`
		ConversationID string `json:"conversation_id,omitempty"`
	}
	items := make([]createdItem, 0, len(created))
	for _, a := range created {
		items = append(items, createdItem{ID: a.ID, Name: a.Name, ConversationID: a.ConversationID})
	}
	if errs == nil {
		errs = []string{}
	}
	httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true, "created": items, "errors": errs})
}

// handleGreet POST /api/accounts/{id}/greet：对账号发一条默认问候建立会话。
func (m *Manager) handleGreet(w http.ResponseWriter, r *http.Request, id string) {
	reply, convID, err := m.Greet(r.Context(), id)
	if err != nil {
		httpx.WriteError(w, http.StatusBadGateway, errText(err), "upstream_error")
		return
	}
	httpx.WriteJSON(w, http.StatusOK, map[string]any{
		"ok": true, "reply": reply, "conversation_id": convID,
	})
}

// Handle 账号管理 API 路由：
//
//	GET    /api/accounts                  → 列表
//	POST   /api/accounts                  → 新建 {name, model}
//	POST   /api/accounts/batch            → 批量注册 {count, model, prefix, greet}
//	POST   /api/accounts/{id}/greet       → 打招呼建立会话
//	PUT    /api/accounts/{id}             → 更新
//	DELETE /api/accounts/{id}             → 删除
//	POST   /api/accounts/{id}/chat        → 对话 {message}
//	GET    /api/accounts/{id}             → 详情
func (m *Manager) Handle(w http.ResponseWriter, r *http.Request) {
	// 提取 id
	id := ""
	path := r.URL.Path
	for _, prefix := range []string{"/api/accounts/"} {
		if len(path) > len(prefix) && path[:len(prefix)] == prefix {
			rest := path[len(prefix):]
			if i := len(rest); i > 0 {
				if rest[len(rest)-1] == '/' {
					rest = rest[:len(rest)-1]
				}
			}
			// 可能是 {id} 或 {id}/chat
			parts := splitPath(rest)
			if len(parts) > 0 && parts[0] == "batch" {
				if r.Method == http.MethodPost {
					m.handleBatch(w, r)
					return
				}
				httpx.WriteError(w, http.StatusMethodNotAllowed, "method not allowed", "method_not_allowed")
				return
			}
			if len(parts) > 0 {
				id = parts[0]
			}
			if len(parts) > 1 && parts[1] == "chat" && r.Method == http.MethodPost {
				m.handleChat(w, r, id)
				return
			}
			if len(parts) > 1 && parts[1] == "greet" && r.Method == http.MethodPost {
				m.handleGreet(w, r, id)
				return
			}
			if len(parts) > 1 && parts[1] == "reset" && r.Method == http.MethodPost {
				if err := m.ResetConversation(id); err != nil {
					httpx.WriteError(w, http.StatusNotFound, errText(err), "not_found")
					return
				}
				httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true})
				return
			}
			if len(parts) > 1 {
				httpx.WriteError(w, http.StatusNotFound, "未知路径", "not_found")
				return
			}
		}
	}

	switch r.Method {
	case http.MethodGet:
		if id != "" {
			a := m.Get(id)
			if a == nil {
				httpx.WriteError(w, http.StatusNotFound, "账号不存在", "not_found")
				return
			}
			httpx.WriteJSON(w, http.StatusOK, a)
			return
		}
		httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true, "accounts": m.List()})
	case http.MethodPost:
		var req struct {
			Name  string `json:"name"`
			Model string `json:"model"`
		}
		if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
			httpx.WriteError(w, http.StatusBadRequest, "请求体错误: "+errText(err), "bad_request")
			return
		}
		if req.Name == "" {
			req.Name = fmt.Sprintf("账号 %d", len(m.List())+1)
		}
		if req.Model == "" {
			req.Model = "glm-5-2"
		}
		a, err := m.Create(req.Name, req.Model)
		if err != nil {
			httpx.WriteError(w, http.StatusInternalServerError, errText(err), "internal")
			return
		}
		httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true, "account": a})
	case http.MethodPut:
		var upd map[string]any
		if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&upd); err != nil {
			httpx.WriteError(w, http.StatusBadRequest, "请求体错误: "+errText(err), "bad_request")
			return
		}
		a, err := m.Update(id, upd)
		if err != nil {
			httpx.WriteError(w, http.StatusNotFound, errText(err), "not_found")
			return
		}
		httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true, "account": a})
	case http.MethodDelete:
		if err := m.Delete(id); err != nil {
			httpx.WriteError(w, http.StatusNotFound, errText(err), "not_found")
			return
		}
		httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true})
	default:
		httpx.WriteError(w, http.StatusMethodNotAllowed, "method not allowed", "method_not_allowed")
	}
}

func (m *Manager) handleChat(w http.ResponseWriter, r *http.Request, id string) {
	var req struct {
		Message string `json:"message"`
	}
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "请求体错误: "+errText(err), "bad_request")
		return
	}
	if req.Message == "" {
		httpx.WriteError(w, http.StatusBadRequest, "缺少 message", "bad_request")
		return
	}
	reply, convID, err := m.Chat(r.Context(), id, req.Message)
	if err != nil {
		httpx.WriteError(w, http.StatusBadGateway, errText(err), "upstream_error")
		return
	}
	httpx.WriteJSON(w, http.StatusOK, map[string]any{
		"ok": true, "reply": reply, "conversation_id": convID,
	})
}

func splitPath(p string) []string {
	var out []string
	cur := ""
	for _, c := range p {
		if c == '/' {
			if cur != "" {
				out = append(out, cur)
				cur = ""
			}
		} else {
			cur += string(c)
		}
	}
	if cur != "" {
		out = append(out, cur)
	}
	return out
}

func errText(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}

// HandleKeys 系统设置 tab：管理上游 key 池 / 本地 key。
//
//	GET    /api/settings/keys               → key 池状态
//	POST   /api/settings/keys               → 添加上游 {key, source?} 或本地 {key, type:"local"}
//	DELETE /api/settings/keys               → 删除 {key, type?}
func (m *Manager) HandleKeys(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true, "snapshot": m.pool.Snapshot()})
	case http.MethodPost:
		var req struct {
			Key    string `json:"key"`
			Source string `json:"source"`
			Type   string `json:"type"`
		}
		if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
			httpx.WriteError(w, http.StatusBadRequest, "请求体错误: "+errText(err), "bad_request")
			return
		}
		key := strings.TrimSpace(req.Key)
		if key == "" {
			httpx.WriteError(w, http.StatusBadRequest, "缺少 key", "bad_request")
			return
		}
		if strings.EqualFold(req.Type, "local") {
			if err := m.pool.AddLocal(key); err != nil {
				httpx.WriteError(w, http.StatusInternalServerError, errText(err), "internal")
				return
			}
		} else {
			source := strings.TrimSpace(req.Source)
			if source == "" {
				source = "manual"
			}
			if err := m.pool.AddUpstream(key, source); err != nil {
				httpx.WriteError(w, http.StatusInternalServerError, errText(err), "internal")
				return
			}
		}
		httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true, "snapshot": m.pool.Snapshot()})
	case http.MethodDelete:
		var req struct {
			Key  string `json:"key"`
			Type string `json:"type"`
		}
		if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
			httpx.WriteError(w, http.StatusBadRequest, "请求体错误: "+errText(err), "bad_request")
			return
		}
		var err error
		if strings.EqualFold(req.Type, "local") {
			err = m.pool.RemoveLocal(req.Key)
		} else {
			err = m.pool.RemoveUpstream(req.Key)
		}
		if err != nil {
			httpx.WriteError(w, http.StatusNotFound, errText(err), "not_found")
			return
		}
		httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true, "snapshot": m.pool.Snapshot()})
	default:
		httpx.WriteError(w, http.StatusMethodNotAllowed, "method not allowed", "method_not_allowed")
	}
}
