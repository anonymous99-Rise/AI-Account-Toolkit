package main

import (
	"bytes"
	"context"
	_ "embed"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"mistral-reverse-proxy/internal/accounts"
	"mistral-reverse-proxy/internal/config"
	"mistral-reverse-proxy/internal/httpx"
	"mistral-reverse-proxy/internal/keys"
	"mistral-reverse-proxy/internal/proxy"
	"mistral-reverse-proxy/internal/register"
	"mistral-reverse-proxy/internal/web"
)

//go:embed system_prompt.md
var embeddedSystemPrompt string

func main() {
	cfg := config.Load()

	pool := keys.NewPool(filepath.Join(cfg.DataDir, "keys.json"))
	for _, k := range cfg.UpstreamKeys {
		if err := pool.AddUpstream(k, "env"); err != nil {
			log.Printf("警告: 写入 key 池失败: %v", err)
		}
	}

	effectiveLocal := cfg.LocalKeys
	if len(effectiveLocal) == 0 {
		effectiveLocal = append(effectiveLocal, pool.EnsureLocalKey())
		log.Printf("未配置 LOCAL_API_KEYS，自动生成本地 key: %s（已持久化到 %s）", effectiveLocal[0], filepath.Join(cfg.DataDir, "keys.json"))
	}
	for _, k := range effectiveLocal {
		if err := pool.AddLocal(k); err != nil {
			log.Printf("警告: 写入本地 key 失败: %v", err)
		}
	}

	sysPrompt := embeddedSystemPrompt
	if cfg.SystemPromptFile != "" {
		if b, err := os.ReadFile(cfg.SystemPromptFile); err == nil && len(bytes.TrimSpace(b)) > 0 {
			sysPrompt = string(b)
			log.Printf("已从 %s 加载系统提示词（%d 字节）", cfg.SystemPromptFile, len(b))
		} else {
			log.Printf("警告: SYSTEM_PROMPT_FILE 读取失败 (%v)，使用内置默认提示词", err)
		}
	}
	// 若存在 data/system_prompt.txt（页面保存过的），优先用它覆盖默认提示词。
	if b, err := os.ReadFile(filepath.Join(cfg.DataDir, "system_prompt.txt")); err == nil && len(bytes.TrimSpace(b)) > 0 {
		sysPrompt = string(b)
		log.Printf("已从 %s 加载持久化系统提示词（%d 字节）", filepath.Join(cfg.DataDir, "system_prompt.txt"), len(b))
	}
	log.Printf("内置系统提示词 %d 字节，上游 key 池 %d 个", len(sysPrompt), pool.UpstreamCount())

	pp := proxy.NewPool(filepath.Join(cfg.DataDir, "proxies.json"))
	pp.StartHealthChecker(cfg.ProxyHealthInterval, "")
	log.Printf("代理池已加载（%d 个代理，健康检查 %s 间隔）", pp.Count(), cfg.ProxyHealthInterval)

	pr := proxy.New(cfg, pool, pp, sysPrompt)
	rg := register.New(pool)
	acc := accounts.NewManager(filepath.Join(cfg.DataDir, "accounts.json"), pr, pool)

	guard := web.NewSession(cfg.AdminPassword)

	mux := http.NewServeMux()
	mux.HandleFunc("POST /v1/chat/completions", auth(pool, pr.HandleChat))
	mux.HandleFunc("POST /v1/messages", auth(pool, pr.HandleMessages))
	mux.HandleFunc("POST /v1/responses", auth(pool, pr.HandleResponses))
	mux.HandleFunc("GET /v1/models", auth(pool, pr.HandleModels))
	mux.HandleFunc("GET /v1/conversations/{id}", auth(pool, pr.HandleConversation))
	mux.HandleFunc("POST /v1/conversations", auth(pool, pr.HandleConversationsRaw))
	mux.HandleFunc("POST /v1/conversations/{id}", auth(pool, pr.HandleConversationsRaw))
	mux.HandleFunc("GET /api/config", admin(pool, guard, pr.HandleConfig))
	mux.HandleFunc("PUT /api/config", admin(pool, guard, pr.HandleConfig))
	mux.HandleFunc("POST /api/register/agent", auth(pool, rg.HandleRegisterAgent))
	mux.HandleFunc("GET /api/keys", admin(pool, guard, rg.HandleKeys))
	mux.HandleFunc("GET /api/settings/keys", admin(pool, guard, acc.HandleKeys))
	mux.HandleFunc("POST /api/settings/keys", admin(pool, guard, acc.HandleKeys))
	mux.HandleFunc("DELETE /api/settings/keys", admin(pool, guard, acc.HandleKeys))
	mux.HandleFunc("GET /api/accounts", admin(pool, guard, acc.Handle))
	mux.HandleFunc("POST /api/accounts", admin(pool, guard, acc.Handle))
	mux.HandleFunc("POST /api/accounts/batch", admin(pool, guard, acc.Handle))
	mux.HandleFunc("PUT /api/accounts/{id}", admin(pool, guard, acc.Handle))
	mux.HandleFunc("DELETE /api/accounts/{id}", admin(pool, guard, acc.Handle))
	mux.HandleFunc("POST /api/accounts/{id}/chat", admin(pool, guard, acc.Handle))
	mux.HandleFunc("POST /api/accounts/{id}/greet", admin(pool, guard, acc.Handle))
	mux.HandleFunc("GET /api/accounts/{id}", admin(pool, guard, acc.Handle))
	mux.HandleFunc("GET /api/proxies", admin(pool, guard, pp.HandleProxies))
	mux.HandleFunc("POST /api/proxies", admin(pool, guard, pp.HandleProxies))
	mux.HandleFunc("POST /api/proxies/check", admin(pool, guard, pp.HandleProxies))
	mux.HandleFunc("POST /api/proxies/{id}/enable", admin(pool, guard, pp.HandleProxies))
	mux.HandleFunc("POST /api/proxies/{id}/disable", admin(pool, guard, pp.HandleProxies))
	mux.HandleFunc("DELETE /api/proxies", admin(pool, guard, pp.HandleProxies))
	mux.HandleFunc("GET /healthz", handleHealthz)
	mux.Handle("/static/", http.StripPrefix("/static/", web.Static()))
	mux.HandleFunc("/", web.Index(guard.Enabled()))

	if guard.Enabled() {
		mux.HandleFunc("GET /login", guard.HandleLogin)
		mux.HandleFunc("POST /login", guard.HandleLoginPost)
		mux.HandleFunc("POST /logout", guard.HandleLogout)
	}

	srv := &http.Server{
		Addr:              cfg.Host + ":" + cfg.Port,
		Handler:           logMiddleware(guard.Guard(mux)),
		ReadHeaderTimeout: 15 * time.Second,
		IdleTimeout:       120 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	listenHost := "0.0.0.0"
	if cfg.Host != "" {
		listenHost = cfg.Host
	}
	go func() {
		log.Printf("Mistral Console Proxy 已启动: http://%s:%s  |  本地 API Key: %s", listenHost, cfg.Port, effectiveLocal[0])
		if guard.Enabled() {
			log.Printf("管理界面密码保护已启用（默认密码 mistral@38467，可通过 ADMIN_PASSWORD 环境变量修改）")
		} else {
			log.Printf("警告: 管理界面无密码保护（监听 %s）。建议设置 ADMIN_PASSWORD 防止扫描器直接访问。", listenHost)
		}
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("服务启动失败: %v", err)
		}
	}()

	<-ctx.Done()
	log.Println("收到退出信号，正在优雅关闭…")
	shCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = srv.Shutdown(shCtx)
}

// auth 本地鉴权中间件：支持 X-API-Key / Authorization: Bearer / ?api_key=，并放行 CORS 预检。
func auth(pool *keys.Pool, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-API-Key, Authorization")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		key := r.Header.Get("X-API-Key")
		if key == "" {
			if a := r.Header.Get("Authorization"); strings.HasPrefix(a, "Bearer ") {
				key = strings.TrimPrefix(a, "Bearer ")
			}
		}
		if key == "" {
			key = r.URL.Query().Get("api_key")
		}
		if !pool.ValidLocal(key) {
			httpx.WriteError(w, http.StatusUnauthorized,
				"缺少或无效的本地 API Key（请设置 X-API-Key 或 Authorization: Bearer <key>）", "unauthorized")
			return
		}
		next(w, r)
	}
}

// admin 管理界面鉴权：有合法 session（密码登录）或合法 X-API-Key 任一通过。
// 这样管理界面 JS 走 session，外部脚本/Agent 可走 X-API-Key，互不冲突。
func admin(pool *keys.Pool, guard *web.Session, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if guard.Check(r) {
			next(w, r)
			return
		}
		key := r.Header.Get("X-API-Key")
		if key == "" {
			if a := r.Header.Get("Authorization"); strings.HasPrefix(a, "Bearer ") {
				key = strings.TrimPrefix(a, "Bearer ")
			}
		}
		if pool.ValidLocal(key) {
			next(w, r)
			return
		}
		httpx.WriteError(w, http.StatusUnauthorized,
			"需要登录管理界面（/login）或提供本地 API Key", "auth_required")
	}
}

func handleHealthz(w http.ResponseWriter, r *http.Request) {
	httpx.WriteJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"time":   time.Now().UTC().Format(time.RFC3339),
	})
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (s *statusRecorder) WriteHeader(code int) {
	s.status = code
	s.ResponseWriter.WriteHeader(code)
}

func (s *statusRecorder) Write(b []byte) (int, error) {
	if s.status == 0 {
		s.status = http.StatusOK
	}
	return s.ResponseWriter.Write(b)
}

func logMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w}
		next.ServeHTTP(rec, r)
		log.Printf("%s %s -> %d (%s)", r.Method, r.URL.Path, rec.status, time.Since(start).Round(time.Millisecond))
	})
}
