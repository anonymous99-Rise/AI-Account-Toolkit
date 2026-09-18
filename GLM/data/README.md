# Mistral Console Proxy

把 Mistral Console Playground 的完整能力（温度/采样参数、系统提示词、工具、SSE 流式、会话历史）暴露成本地 OpenAI 兼容 API 的 Go 反向代理。自带一个轻量 Playground 风格 Web UI，支持多上游 key 轮询/失败切换与本地 key 鉴权，可通过 Docker 一键部署。

## 特性

- `POST /v1/chat/completions`：OpenAI 兼容，非流式 + `stream=true` SSE 流式均支持
- 模型自动映射：`glm-5.2` / `glm_5_2` / `zai-glm-5-2` / `GLM-5-2` 等变体 → `glm-5-2`
- 默认值注入：未带 system 消息时自动注入导出的 Playground 系统提示词（36KB，内嵌进二进制），默认 `temperature=0.7`、`max_tokens=4096`、`reasoning_effort=high`
- 默认注入 Playground 工具：`code_interpreter` + `image_generation` + `web_search`（可用环境变量关闭）
- 参数全透传：`messages`（含 system role）、`tools`、`tool_choice`、`top_p`、`stop`、`seed`、`response_format` 等
- 本地鉴权：`X-API-Key` / `Authorization: Bearer` / `?api_key=` 三选一，多本地 key
- 上游 key 池：多 key 轮询 + 按失败状态码自动冷却切换（401/402 长冷却，429/5xx 短冷却），持久化到 `data/keys.json`
- 会话：每次请求返回 `conversation_id`（透传上游或本地生成），`GET /v1/conversations/{id}` 查询（本地缓存优先，否则透传上游）
- 错误映射：上游 401/402/429/503 映射为可读 JSON 并附上游 body；上游 `no healthy upstream` 返回 502 并提示稍后重试
- SSE 连接中断优雅处理（客户端断开即取消上游请求）

## 快速开始

### 本地运行

```powershell
cd E:\mistral-GLM5.2\reverse-proxy
$env:PORT = "8080"
$env:UPSTREAM_API_KEY = "nAzh61qAuaMSoCk97tSbGIIkp9RxgyrL"
$env:LOCAL_API_KEYS = "f7a1c2d3e4b5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0"
# 重要：本机网络被 DNS 劫持，Go 原生 net/http 需显式走系统代理才能连通上游
$env:HTTP_PROXY = "http://127.0.0.1:10818"
$env:HTTPS_PROXY = "http://127.0.0.1:10818"
go run .
```

启动日志会打印服务地址与生效的本地 key。浏览器打开 `http://127.0.0.1:8080` 即是 Playground UI。

> 若未设置 `LOCAL_API_KEYS`，服务会自动生成一个本地 key 并打印，同时持久化到 `data/keys.json`。

### 速度优化（reasoning_effort）

**GLM-5.2 的 reasoning_effort 合法值只有 `none` 和 `high`**（实测其他值 422：`Input should be 'none' or 'high'`）。

速度差异巨大：

| reasoning_effort | 实测耗时 |
| --- | --- |
| `none`（无思考） | **~2 秒** ✅ 推荐 |
| `high`（深度思考） | **~60 秒** |

本代理已处理：

- 默认 GLM 用 `none`（最快）；客户端显式传 `high` 才启用深度思考
- 非法值（`low`/`medium`/`max` 等）自动归一化为 `none`，避免 422
- 前端下拉：`none（最快）` / `high（深度思考，慢）`
- `/api/config` 返回 `reasoning_efforts: ["none","high"]`

> 注意：`high` 深度思考时 GLM 推理节点易触发 `no healthy upstream`（503），且非常慢；日常对话建议 `none`。

## Docker 部署

项目内置多阶段 `Dockerfile`（`golang:1.26` 构建 → `alpine:3.20` 运行），一键起服务：

```bash
cd E:\mistral-GLM5.2\reverse-proxy

# 1. 生成环境变量文件，填写 UPSTREAM_API_KEY / ADMIN_PASSWORD / LOCAL_API_KEYS
cp .env.example .env

# 2. 构建并启动
docker compose up -d --build

# 3. 查看日志 / 停止
docker compose logs -f
docker compose down
```

要点：

- 默认映射宿主 **38467** 端口，浏览器访问 `http://<host>:38467` 即 Playground UI（用 `ADMIN_PASSWORD` 登录；未设置则无密码）
- 挂载 `./data:/data` 卷，`DATA_DIR=/data` 固定：key 池（`keys.json`）、账号（`accounts.json`）、代理池（`proxies.json`）、页面保存的系统提示词（`system_prompt.txt`）全部持久化，重启不丢
- 内置健康检查（`/healthz`），镜像只含一个静态二进制（静态资源与默认系统提示词已 `//go:embed` 进二进制）
- 除 `DATA_DIR` 外全部配置走 `.env`（见 `.env.example`）；`PORT` 改值后宿主端口映射自动跟随

> 容器内访问 `https://api.mistral.ai` 需要出网。若服务器存在 DNS 劫持/被墙，在 `.env` 中设置全局出口代理（优先级最高）：
> `UPSTREAM_PROXY=socks5://127.0.0.1:10818`（支持 `socks5://` / `socks5h://` / `http://` / `https://`），或在 `docker-compose.yml` 中取消该行注释。

#### 对接 sub2api（把本代理作为一条 OpenAI channel）

在 sub2api 中添加 channel：

| 配置项 | 值 |
| --- | --- |
| 类型 | OpenAI |
| Base URL | `http://<host>:38467/v1` |
| API Key | `LOCAL_API_KEYS` 里设置的本地 key（未设置则首次启动自动生成并打印在启动日志；也可用 `ADMIN_PASSWORD` 登录 UI 在「系统设置」查看） |
| 模型 | `glm-5-2`、`mistral-medium-latest`、`mistral-large-latest` 等（`GET /v1/models` 可查） |

对接要点：

- sub2api 请求不带 system 消息时，本代理自动注入页面设置/持久化的默认系统提示词（`data/system_prompt.txt` 或内嵌内置提示词），所以 sub2api 直接就能拿到「页面配置好的完整对话」能力——温度/工具/提示词全部走请求参数生效，无需在 sub2api 侧额外配置
- 请求显式带 system 消息时用请求里的，不注入默认提示词
- 流式（`stream=true` SSE）与非流式均兼容

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `8080` | 本地监听端口 |
| `UPSTREAM_BASE_URL` | `https://api.mistral.ai/v1` | 上游地址 |
| `UPSTREAM_API_KEY` | 空 | 单个上游 key |
| `UPSTREAM_API_KEYS` | 空 | 多个上游 key，逗号/分号/换行分隔 |
| `LOCAL_API_KEYS` | 空 | 本地鉴权 key（多 key 逗号分隔）；不设则自动生成 |
| `DATA_DIR` | `data` | 持久化目录（`keys.json`） |
| `SYSTEM_PROMPT_FILE` | 空 | 覆盖默认系统提示词的文件路径 |
| `INJECT_PLAYGROUND_TOOLS` | `true` | 请求未带 tools 时注入 Playground 三件套 |
| `MAX_UPSTREAM_RETRIES` | `4` | 上游失败时最多尝试的 key 数 |
| `HTTP_TIMEOUT_SECONDS` | `120` | 上游响应头超时 |
| `HTTP_PROXY` / `HTTPS_PROXY` | 空 | 走代理访问上游（本机有 DNS 劫持时必须设置，见下文「网络注意事项」） |
| `UPSTREAM_PROXY` | 空 | 全局统一代理（`socks5://...` 或 `http://...`），优先级最高 |
| `PROXY_FILE` | `data/proxies.json` | 代理池持久化文件 |
| `PROXY_HEALTH_INTERVAL_MIN` | `5` | 后台代理健康检查间隔（分钟） |

上游 key 的来源优先级：`data/keys.json` 持久化池（含 Agent B 注册的 key）+ 环境变量，两者合并去重。

## API

### POST /v1/chat/completions（非流式）

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$body = @{
  model = "glm-5-2"
  messages = @(@{ role = "user"; content = "用一句话介绍你自己" })
  temperature = 0.7
  top_p = 1.0
  max_tokens = 4096
  reasoning_effort = "high"
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/chat/completions" `
  -Method Post `
  -Headers @{ "X-API-Key" = "f7a1c2d3e4b5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0" } `
  -ContentType "application/json" -Body ($body | ConvertTo-Json -Depth 8)
```

响应是 OpenAI 格式，附 `conversation_id` 字段与 `X-Conversation-ID` 响应头。

> Windows 提示：`curl.exe` 对上游 Cloudflare 有 TLS 问题，测试请用 `Invoke-RestMethod` 或 `[System.Net.Http.HttpClient]`。Linux/macOS 用 curl 无此问题。

### POST /v1/chat/completions（流式）

```bash
curl -N http://127.0.0.1:8080/v1/chat/completions \
  -H "Authorization: Bearer f7a1c2d3e4b5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0" \
  -H "Content-Type: application/json" \
  -d '{"model":"mistral-medium-latest","messages":[{"role":"user","content":"写一段 50 字的产品简介"}],"stream":true}'
```

### 带 tools / system 消息

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H "X-API-Key: f7a1c2d3e4b5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5-2",
    "messages": [
      {"role": "system", "content": "你是一个文件管理助手"},
      {"role": "user", "content": "列出当前目录文件"}
    ],
    "tools": [
      {"type": "function", "function": {"name": "list_files", "description": "列出目录", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}
    ],
    "tool_choice": "auto"
  }'
```

显式提供 system 消息时，代理不会再注入默认系统提示词。

### 其它接口

```powershell
# 健康检查
Invoke-RestMethod "http://127.0.0.1:8080/healthz"

# 模型列表
Invoke-RestMethod "http://127.0.0.1:8080/v1/models" -Headers @{ "X-API-Key" = $localKey }

# 查询会话历史（本地缓存优先）
Invoke-RestMethod "http://127.0.0.1:8080/v1/conversations/conv_xxx" -Headers @{ "X-API-Key" = $localKey }

# key 池状态
Invoke-RestMethod "http://127.0.0.1:8080/api/keys" -Headers @{ "X-API-Key" = $localKey }
```

## 本地 key 生成方式

- 手动指定：设置 `LOCAL_API_KEYS="key1,key2"`，逗号分隔支持多个
- 自动生成：不设置该变量，首次启动自动生成 32 字节 hex key，打印在启动日志并写入 `data/keys.json`，重启后保持稳定
- 任意 OpenAI 兼容客户端（如 ChatBox、NextChat、OpenWebUI）配置：`Base URL=http://127.0.0.1:8080/v1`，`API Key=本地 key`，模型填 `glm-5-2` 等

## Agent B 注册对接

本地服务暴露 `POST /api/register/agent`，供自动注册流程（Agent B + cloakBrowser）在完成邮箱/账号注册后回调，把新获取的上游 key 加入池并持久化：

```bash
curl -X POST http://127.0.0.1:8080/api/register/agent \
  -H "X-API-Key: <本地 key>" \
  -H "Content-Type: application/json" \
  -d '{"email": "user_xxx@example.com", "api_key": "<新注册拿到的上游 key>"}'
```

- 需要带本地 key 鉴权（`X-API-Key` / `Authorization: Bearer` / `?api_key=`）
- `api_key` 必填；`email` 用于标注来源，会显示在 `GET /api/keys` 的 source 列
- 成功后返回 `{"status":"ok","added":true,"pool":{...}}`，key 立即进入轮询池，并写入 `data/keys.json`（重启不丢）
- Agent B 流程：cloakBrowser 自动注册 → 拿到新 key → POST 本接口 → 后续请求自动轮询/失败切换使用新 key

## 错误处理

| 上游状态 | 本地返回 | 说明 |
| --- | --- | --- |
| 401 | 401 | 上游 key 无效，进入 30 分钟冷却 |
| 402 | 402 | 上游额度耗尽，进入 30 分钟冷却 |
| 429 | 429 | 上游限流，进入 60 秒冷却 |
| 503（no healthy upstream） | 502 | 提示「上游服务暂不可用，请稍后重试」 |
| 其它 5xx | 502 | 重试其它 key 后仍失败 |

错误响应均为 `{"error":{"message","type","code","upstream_status","upstream_body"}}`。

## 代理池（模仿 flex.ai go_backend 实现）

内置上游出口代理池，解决 DNS 劫持 / 直连被墙导致上游不可达的问题：

- 支持 `http` / `https` / `socks5` / `socks5h` / `direct` 五种类型
- 出口优先级：`UPSTREAM_PROXY` 全局代理 > 代理池中延迟最低的健康代理 > 直连（`http.ProxyFromEnvironment`，可被 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量接管）
- 健康检查：`GET` 探测 `https://api.mistral.ai/v1/models`，记录延迟；连续失败 3 次自动禁用（保留记录，可手动启用）
- 后台定时健康检查（`PROXY_HEALTH_INTERVAL_MIN`），持久化到 `PROXY_FILE`

### 代理池 API

```powershell
# 列表（含延迟/状态）
Invoke-RestMethod "http://127.0.0.1:8080/api/proxies" -Headers @{ "X-API-Key" = $localKey }

# 添加代理
Invoke-RestMethod "http://127.0.0.1:8080/api/proxies" -Method Post `
  -Headers @{ "X-API-Key" = $localKey } -ContentType "application/json" `
  -Body '{"addr":"127.0.0.1:10818","type":"http"}'

# 触发一次全池健康检查
Invoke-RestMethod "http://127.0.0.1:8080/api/proxies/check" -Method Post -Headers @{ "X-API-Key" = $localKey }

# 手动启用/停用
Invoke-RestMethod "http://127.0.0.1:8080/api/proxies/{id}/disable" -Method Post -Headers @{ "X-API-Key" = $localKey }
Invoke-RestMethod "http://127.0.0.1:8080/api/proxies/{id}/enable" -Method Post -Headers @{ "X-API-Key" = $localKey }

# 删除
Invoke-RestMethod "http://127.0.0.1:8080/api/proxies" -Method Delete `
  -Headers @{ "X-API-Key" = $localKey } -ContentType "application/json" -Body '{"id":"..."}'
```

## 网络注意事项

本机（Windows）存在 **DNS 劫持 + 系统代理** 环境：

- `api.mistral.ai` 被解析到错误 IP（如 `199.59.149.206`），Go / Node 原生直连会超时或被重置
- 系统代理 `127.0.0.1:10818`（`Internet Settings` 里 `ProxyEnable=1`）是唯一可用通道，但 Go 默认不读系统代理
- 必须显式设置 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量，代理才会生效（代码已用 `http.ProxyFromEnvironment`）
- PowerShell `Invoke-RestMethod` / `HttpClient` 会自己读系统代理，所以 PowerShell 能通、Go 不通，就是这个原因

Linux / Docker 无此问题（无 DNS 劫持时直连即可）；如服务器需要代理，同样通过环境变量传入。

## GLM-5.2 限流说明与 Conversations 通道

**已实测确认：GLM-5.2 走 `/v1/conversations` 完全可用（200），`/v1/chat/completions` 被限流（429，配额 0）。**

本代理已内置自动路由：

- 模型为 `glm-5-2` / `zai-glm-5-2` → 自动走 `POST /v1/conversations`（请求自动转换：messages→inputs、system→instructions、completion_args、裸类型 tools）
- 其余模型 → 走 `/v1/chat/completions`
- GLM 响应自动转换回 OpenAI 兼容格式（`choices[].message.content`），并透传 `conversation_id`

实测（本地代理 + glm-5-2）：

```powershell
$body = '{"model":"glm-5-2","messages":[{"role":"user","content":"你好"}],"max_tokens":300}'
Invoke-RestMethod "http://127.0.0.1:8080/v1/chat/completions" -Method Post `
  -Headers @{ "X-API-Key" = $localKey } -ContentType "application/json" -Body $body
# → 200, choices[0].message.content = GLM 回复, conversation_id = conv_...
```

> 注意：GLM 推理节点偶发 `no healthy upstream`（503），属 Mistral 服务端问题，稍后自动恢复。期间可切 `mistral-medium-latest` 兜底。

## 验证记录

- `go mod tidy`：通过（零第三方依赖）
- `go build ./...`：通过
- `go vet ./...`：通过
- 实测（`go run .` 于本机，走 `HTTP_PROXY=127.0.0.1:10818`）：
  - `GET /healthz` → 200 `{"status":"ok"}`
  - `GET /v1/models` → 200，返回 `glm-5-2` / `mistral-medium-latest` / `mistral-large-latest`
  - `GET /api/keys` → 200，key 池状态正确
  - 错误 key 鉴权 → 401（拒绝路径正确）
  - `POST /api/register/agent` → 200，新 key 入池并持久化，source 标注 `registered:<email>`
  - `POST /v1/chat/completions`（默认配置，模型 `mistral-medium-latest`）→ **200**，返回带 thinking 的 reasoning 回复，系统提示词注入生效
  - 修复记录：默认注入 Playground 工具时曾因裸工具格式导致上游 400，已改为 function 格式（见 `playgroundTools`），修复后默认配置 200

> 环境依赖：本机到上游必须走 `127.0.0.1:10818` 代理（DNS 劫持），未设置代理时上游请求会 502（dial timeout）。这不是代码问题，是网络环境；Linux/Docker 无此限制。
## 多账号管理 + Tab 界面

Web 界面已改为 **3 个 Tab**：

1. **对话 Playground**：模型/温度/top_p/max_tokens/reasoning_effort + 工具开关（含本地文件工具）+ 系统提示词 + SSE 流式
2. **账号管理**：多账号对话。每个账号是独立 GLM 会话（conversation_id），可独立设置温度/max_tokens/reasoning_effort/系统提示词，多轮自动延续（已验证记忆）
3. **系统设置**：上游 key 池增删（轮询+失败冷却）、本地 key、代理池管理（健康检查/启停）

### 账号管理 API

```powershell
# 新建账号
POST /api/accounts  {"name":"主号","model":"glm-5-2"}
# 账号列表
GET /api/accounts
# 更新账号参数（温度/提示词等）
PUT /api/accounts/{id}  {"temperature":0.7,"system_prompt":"..."}
# 账号对话（多轮延续）
POST /api/accounts/{id}/chat  {"message":"你好"}
# 删除账号
DELETE /api/accounts/{id}
```

### 系统设置 API

```powershell
# key 池
GET  /api/settings/keys
POST /api/settings/keys  {"key":"sk-...","source":"manual"}
DELETE /api/settings/keys  {"key":"..."}
```

## 本地工具调用（已并入主代码）

`internal/proxy/tools.go` 实现完整 function calling 闭环，参考 `tool-calling/本地工具调用实现文档.md`：

- 内置 4 个本地文件工具：`list_directory` / `read_file` / `write_file` / `append_file`
- 协议：模型返回 `function.call` → 本地执行 → `function.result` 回传（`POST /conversations/{id}`，**注意 append 不接受 model 字段**）→ 模型基于结果生成最终回复
- 实测：GLM 通过代理真实写入本地文件成功
