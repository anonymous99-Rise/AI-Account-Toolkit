package register

import (
	"encoding/json"
	"io"
	"net/http"
	"strings"

	"mistral-reverse-proxy/internal/httpx"
	"mistral-reverse-proxy/internal/keys"
)

// RegisterRequest Agent B 完成自动注册后回调的载荷。
type RegisterRequest struct {
	Email  string `json:"email"`
	APIKey string `json:"api_key"`
}

type Register struct {
	pool *keys.Pool
}

func New(pool *keys.Pool) *Register {
	return &Register{pool: pool}
}

// HandleRegisterAgent POST /api/register/agent：把新上游 key 加入池并持久化。
func (rg *Register) HandleRegisterAgent(w http.ResponseWriter, r *http.Request) {
	var req RegisterRequest
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
		httpx.WriteError(w, http.StatusBadRequest, "请求体不是合法 JSON: "+errText(err), "bad_request")
		return
	}
	req.APIKey = strings.TrimSpace(req.APIKey)
	req.Email = strings.TrimSpace(req.Email)
	if req.APIKey == "" {
		httpx.WriteError(w, http.StatusBadRequest, "缺少必填字段 api_key", "bad_request")
		return
	}
	source := "registered"
	if req.Email != "" {
		source = "registered:" + req.Email
	}
	if err := rg.pool.AddUpstream(req.APIKey, source); err != nil {
		httpx.WriteError(w, http.StatusInternalServerError, "写入 key 池失败: "+errText(err), "persist_error")
		return
	}
	httpx.WriteJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"email":  req.Email,
		"added":  true,
		"pool":   rg.pool.Snapshot(),
	})
}

// HandleKeys GET /api/keys：返回本地 key 与上游 key 池状态。
func (rg *Register) HandleKeys(w http.ResponseWriter, r *http.Request) {
	httpx.WriteJSON(w, http.StatusOK, map[string]any{
		"pool": rg.pool.Snapshot(),
	})
}

func errText(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}