package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

// Config 集中管理所有运行时配置，全部来自环境变量，带默认值。
type Config struct {
	Port                  string        // 本地服务监听端口
	Host                  string        // 监听地址，空 = 所有网卡（0.0.0.0）
	AdminPassword         string        // 管理界面登录密码，空 = 不启用密码保护
	UpstreamBase          string        // 上游 Mistral API 根地址
	UpstreamKeys          []string      // 环境变量注入的上游 key（会合并进 key 池）
	LocalKeys             []string      // 本地 API 鉴权 key（多 key）
	DataDir               string        // 持久化目录（keys.json 等）
	SystemPromptFile      string        // 可选：从文件覆盖默认系统提示词
	InjectPlaygroundTools bool          // 请求未带 tools 时注入 Playground 默认工具
	InjectSystemPrompt   bool          // 客户端未带 system/instructions 时注入默认系统提示词（设为 false 可避免 36KB 提示词拖慢 sub2api/Claude Code 场景）
	MaxRetries            int           // 上游失败时最多尝试的 key 数量
	HTTPTimeout           time.Duration // 上游响应头超时
	DefaultReasoningEffort string        // GLM 客户端未指定 reasoning_effort 时的默认值（none=最快 / high=深度思考）
	Models                []string      // 对外暴露的模型列表
	UpstreamProxy         string        // 全局统一代理 socks5://... 或 http://...，空=走代理池/直连
	ProxyFile             string        // 代理池持久化文件
	ProxyHealthInterval   time.Duration // 后台代理健康检查间隔
	ToolMode              string        // 工具模式：passthrough（客户端驱动，opencode/Claude Code）/ local（代理闭环，Playground）
}

func Load() *Config {
	cfg := &Config{
		Port:                  getEnv("PORT", "38467"),
		Host:                  getEnv("HOST", ""),
		AdminPassword:         getEnv("ADMIN_PASSWORD", "mistral@38467"),
		UpstreamBase:          strings.TrimRight(getEnv("UPSTREAM_BASE_URL", "https://api.mistral.ai/v1"), "/"),
		DataDir:               getEnv("DATA_DIR", "data"),
		SystemPromptFile:      os.Getenv("SYSTEM_PROMPT_FILE"),
		InjectPlaygroundTools: getBool("INJECT_PLAYGROUND_TOOLS", true),
		InjectSystemPrompt:   getBool("INJECT_SYSTEM_PROMPT", true),
		MaxRetries:            getInt("MAX_UPSTREAM_RETRIES", 4),
		HTTPTimeout:           time.Duration(getInt("HTTP_TIMEOUT_SECONDS", 120)) * time.Second,
		DefaultReasoningEffort: normalizeEffortEnv(getEnv("DEFAULT_REASONING_EFFORT", "none")),
		Models:                []string{"glm-5-2", "mistral-medium-latest", "mistral-large-latest"},
		UpstreamProxy:         strings.TrimSpace(os.Getenv("UPSTREAM_PROXY")),
		ProxyFile:             getEnv("PROXY_FILE", "data/proxies.json"),
		ProxyHealthInterval:   time.Duration(getInt("PROXY_HEALTH_INTERVAL_MIN", 5)) * time.Minute,
		ToolMode:              getEnv("TOOL_MODE", "passthrough"),
	}
	cfg.UpstreamKeys = splitKeys(os.Getenv("UPSTREAM_API_KEYS"))
	if k := strings.TrimSpace(os.Getenv("UPSTREAM_API_KEY")); k != "" {
		cfg.UpstreamKeys = append(cfg.UpstreamKeys, k)
	}
	cfg.LocalKeys = splitKeys(os.Getenv("LOCAL_API_KEYS"))
	return cfg
}

func getEnv(key, def string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return def
}

func getInt(key string, def int) int {
	v, err := strconv.Atoi(strings.TrimSpace(os.Getenv(key)))
	if err != nil {
		return def
	}
	return v
}

func getBool(key string, def bool) bool {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return def
	}
	b, err := strconv.ParseBool(v)
	if err != nil {
		return def
	}
	return b
}

// splitKeys 支持逗号 / 分号 / 换行分隔的多 key 列表。
func splitKeys(raw string) []string {
	var out []string
	for _, part := range strings.FieldsFunc(raw, func(r rune) bool {
		return r == ',' || r == ';' || r == '\n' || r == '\r'
	}) {
		if k := strings.TrimSpace(part); k != "" {
			out = append(out, k)
		}
	}
	return out
}

// normalizeEffortEnv 把 DEFAULT_REASONING_EFFORT 环境变量归一化为 GLM 合法值（none/high）。
func normalizeEffortEnv(v string) string {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "high", "on", "true", "1", "deep", "max":
		return "high"
	default:
		return "none"
	}
}
