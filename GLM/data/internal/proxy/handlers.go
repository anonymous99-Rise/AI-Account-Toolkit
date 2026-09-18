package proxy

import (
	"encoding/json"
	"io"
	"net/http"
	"strings"

	"mistral-reverse-proxy/internal/httpx"
)

// HandleProxies 代理池管理 API：
//
//	GET  /api/proxies            → 代理列表（含延迟/健康状态）
//	POST /api/proxies            → 添加代理 {addr,type,username,password}
//	POST /api/proxies/check      → 触发一次全池健康检查
//	POST /api/proxies/{id}/enable|disable → 手动启用/停用
//	DELETE /api/proxies          → 删除 {id}
func (p *Pool) HandleProxies(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/api/proxies")
	path = strings.Trim(path, "/")

	// 子路由: {id}/enable | {id}/disable
	if parts := strings.Split(path, "/"); len(parts) == 2 && parts[0] != "" && parts[0] != "check" {
		id := parts[0]
		switch parts[1] {
		case "enable":
			if err := p.SetEnabled(id, true); err != nil {
				httpx.WriteError(w, http.StatusNotFound, err.Error(), "not_found")
				return
			}
			httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true, "id": id, "enabled": true})
			return
		case "disable":
			if err := p.SetEnabled(id, false); err != nil {
				httpx.WriteError(w, http.StatusNotFound, err.Error(), "not_found")
				return
			}
			httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true, "id": id, "enabled": false})
			return
		}
		httpx.WriteError(w, http.StatusNotFound, "未知操作: "+parts[1], "not_found")
		return
	}

	switch r.Method {
	case http.MethodGet:
		httpx.WriteJSON(w, http.StatusOK, map[string]any{
			"ok":      true,
			"proxies": p.List(),
			"count":   p.Count(),
		})
	case http.MethodPost:
		if path == "check" {
			probeURL := strings.TrimSpace(r.URL.Query().Get("url"))
			if probeURL == "" {
				probeURL = "https://api.mistral.ai/v1/models"
			}
			results := p.CheckAll(probeURL)
			httpx.WriteJSON(w, http.StatusOK, map[string]any{
				"ok":      true,
				"probe":   probeURL,
				"results": results,
			})
			return
		}
		var it Item
		if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&it); err != nil {
			httpx.WriteError(w, http.StatusBadRequest, "请求体不是合法 JSON: "+errText(err), "bad_request")
			return
		}
		if err := p.Add(it); err != nil {
			httpx.WriteError(w, http.StatusBadRequest, err.Error(), "bad_request")
			return
		}
		httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true})
	case http.MethodDelete:
		var req struct {
			ID string `json:"id"`
		}
		if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
			httpx.WriteError(w, http.StatusBadRequest, "请求体不是合法 JSON: "+errText(err), "bad_request")
			return
		}
		if err := p.Delete(req.ID); err != nil {
			httpx.WriteError(w, http.StatusNotFound, err.Error(), "not_found")
			return
		}
		httpx.WriteJSON(w, http.StatusOK, map[string]any{"ok": true})
	default:
		httpx.WriteError(w, http.StatusMethodNotAllowed, "method not allowed", "method_not_allowed")
	}
}

func errText(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}