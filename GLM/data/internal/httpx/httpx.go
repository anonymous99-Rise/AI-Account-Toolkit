package httpx

import (
	"encoding/json"
	"net/http"
)

// WriteJSON 统一输出 JSON 响应。
func WriteJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

// WriteError 输出 OpenAI 风格错误结构。
func WriteError(w http.ResponseWriter, code int, msg, typ string) {
	WriteJSON(w, code, map[string]any{
		"error": map[string]any{
			"message": msg,
			"type":    typ,
			"code":    code,
		},
	})
}