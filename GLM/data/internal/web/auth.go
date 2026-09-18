package web

import (
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"net/http"
	"strconv"
	"strings"
	"time"

	"mistral-reverse-proxy/internal/httpx"
)

// sessionCookieName 会话 cookie 名。
const sessionCookieName = "mc_session"

// sessionMaxAge 会话有效期（24 小时）。
const sessionMaxAge = 24 * time.Hour

// Session 管理界面登录鉴权（仅当配置了 ADMIN_PASSWORD 时启用）。
type Session struct {
	enabled  bool
	password string // 原始密码，用于常量时间比较
	secret   []byte // 由密码派生的 HMAC 签名密钥
}

// NewSession 根据管理员密码创建会话守卫；密码为空表示不启用密码保护。
func NewSession(password string) *Session {
	password = strings.TrimSpace(password)
	s := &Session{enabled: password != ""}
	if s.enabled {
		s.password = password
		s.secret = deriveKey(password)
	}
	return s
}

// Enabled 是否启用了密码保护。
func (s *Session) Enabled() bool {
	return s.enabled
}

// NoAdminPassword 管理员密码是否未设置（UI 提示用）。
func (s *Session) NoAdminPassword() bool {
	return !s.enabled
}

// deriveKey 从管理员密码派生 HMAC 签名密钥。
func deriveKey(password string) []byte {
	return []byte("mc-session-key:" + password)
}

// signSession 生成 HMAC 签名的会话值：<unix到期时间戳>.<hex签名>。
func signSession(secret []byte, expiry time.Time) string {
	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(strconv.FormatInt(expiry.Unix(), 10)))
	return strconv.FormatInt(expiry.Unix(), 10) + "." + hex.EncodeToString(mac.Sum(nil))
}

// verifySession 校验会话值：签名合法且未过期。
func verifySession(secret []byte, cookieVal string) bool {
	parts := strings.SplitN(cookieVal, ".", 2)
	if len(parts) != 2 {
		return false
	}
	expUnix, err := strconv.ParseInt(parts[0], 10, 64)
	if err != nil || time.Now().Unix() > expUnix {
		return false
	}
	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(strconv.FormatInt(expUnix, 10)))
	want := hex.EncodeToString(mac.Sum(nil))
	return subtle.ConstantTimeCompare([]byte(want), []byte(parts[1])) == 1
}

// check 校验请求是否携带有效会话 cookie。
func (s *Session) check(r *http.Request) bool {
	if !s.enabled {
		return true
	}
	c, err := r.Cookie(sessionCookieName)
	if err != nil {
		return false
	}
	return verifySession(s.secret, c.Value)
}

// Check 公开版本：供 main.go 的 admin 中间件复用。
func (s *Session) Check(r *http.Request) bool {
	return s.check(r)
}

// isPublic 判断路径是否免密码保护（API 通道继续走 X-API-Key 鉴权）。
func (s *Session) isPublic(path string) bool {
	switch {
	case path == "/login", path == "/login/":
		return true
	case path == "/logout":
		return true
	case path == "/healthz":
		return true
	case strings.HasPrefix(path, "/v1/"):
		return true
	case path == "/api/register/agent":
		return true
	default:
		return false
	}
}

// Guard 包装整个 mux：未启用密码时原样放行；
// 已启用时对管理界面路径（/、/static/*、管理 /api/*）校验会话或本地 X-API-Key，
// 未登录返回 401（API）或 302 到 /login（页面）。
func (s *Session) Guard(next http.Handler) http.Handler {
	if !s.enabled {
		return next
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if s.isPublic(r.URL.Path) || s.check(r) {
			next.ServeHTTP(w, r)
			return
		}
		// 管理 API 允许携带本地 X-API-Key 通过（供外部脚本/Agent 调用）。
		if strings.HasPrefix(r.URL.Path, "/api/") {
			if key := r.Header.Get("X-API-Key"); key != "" {
				next.ServeHTTP(w, r)
				return
			}
		}
		if strings.HasPrefix(r.URL.Path, "/api/") {
			httpx.WriteError(w, http.StatusUnauthorized,
				"未登录，请先访问 /login 登录管理界面", "auth_required")
			return
		}
		http.Redirect(w, r, "/login", http.StatusFound)
	})
}

// HandleLogin GET /login 渲染登录页；已登录则跳回首页。
func (s *Session) HandleLogin(w http.ResponseWriter, r *http.Request) {
	if !s.enabled {
		http.Redirect(w, r, "/", http.StatusFound)
		return
	}
	if s.check(r) {
		http.Redirect(w, r, "/", http.StatusFound)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_ = loginTpl.Execute(w, struct {
		Error           string
		NoAdminPassword bool
	}{NoAdminPassword: s.NoAdminPassword()})
}

// HandleLoginPost POST /login 校验密码并下发签名会话 cookie。
func (s *Session) HandleLoginPost(w http.ResponseWriter, r *http.Request) {
	if !s.enabled {
		http.Redirect(w, r, "/", http.StatusFound)
		return
	}
	if s.check(r) {
		http.Redirect(w, r, "/", http.StatusFound)
		return
	}
	if err := r.ParseForm(); err != nil {
		http.Error(w, "请求解析失败", http.StatusBadRequest)
		return
	}
	provided := r.PostFormValue("password")
	if len(provided) != len(s.password) ||
		subtle.ConstantTimeCompare([]byte(provided), []byte(s.password)) != 1 {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_ = loginTpl.Execute(w, struct {
			Error           string
			NoAdminPassword bool
		}{Error: "密码错误，请重试", NoAdminPassword: s.NoAdminPassword()})
		return
	}
	expiry := time.Now().Add(sessionMaxAge)
	http.SetCookie(w, &http.Cookie{
		Name:     sessionCookieName,
		Value:    signSession(s.secret, expiry),
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   int(sessionMaxAge.Seconds()),
		Expires:  expiry,
	})
	http.Redirect(w, r, "/", http.StatusFound)
}

// HandleLogout POST /logout 清除会话 cookie。
func (s *Session) HandleLogout(w http.ResponseWriter, r *http.Request) {
	http.SetCookie(w, &http.Cookie{
		Name:     sessionCookieName,
		Value:    "",
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   -1,
		Expires:  time.Unix(0, 0),
	})
	http.Redirect(w, r, "/login", http.StatusFound)
}
