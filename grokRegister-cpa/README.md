<div align="center">

[![Grok Register — 注册即入库 CLIProxyAPI](assets/banner.png)](https://github.com/Git-creat7/grokRegister-cpa)

批量注册 Grok 账号，注册成功后自动把 OAuth 凭证写入 [CLIProxyAPI (CPA)](https://github.com/router-for-me/CLIProxyAPI)：支持本地 auth 目录热加载，也支持 Management API 远程上传。

<p>
  <a href="https://github.com/Git-creat7/grokRegister-cpa/stargazers"><img src="https://img.shields.io/github/stars/Git-creat7/grokRegister-cpa?style=flat&logo=github" alt="GitHub stars"></a>
  <a href="https://github.com/Git-creat7/grokRegister-cpa/network/members"><img src="https://img.shields.io/github/forks/Git-creat7/grokRegister-cpa?style=flat&logo=github" alt="GitHub forks"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/Interface-GUI%20%2B%20CLI-success.svg" alt="GUI + CLI">
  <img src="https://img.shields.io/badge/Output-CLIProxyAPI-orange.svg" alt="CLIProxyAPI">
</p>

</div>

---

> 仅用于自动化流程研究、测试环境验证和个人学习。请遵守目标网站服务条款、当地法律法规与第三方服务限制。

## 核心流程

```text
打开注册页 → 创建临时邮箱 → 收验证码 → 原生事件填写资料 / Turnstile
   → 拿到 SSO cookie
   → Device Flow（优先复用注册浏览器点「继续/允许」，失败再协议 approve / 授权码）
   → 本地写入 cpa_auth_dir / grok2api_auth_dir  和/或  POST 远程 CPA Management API
   → CPA / Grok2API 热加载，立即可用
```

## 功能

- 注册成功后自动入库 CPA（本地目录 / 远程 Management API，可同时开）
- GUI + CLI 两种运行方式（CLI 仍会打开浏览器完成注册页）
- Camoufox C++ 引擎层指纹伪装（从编译层修改 Gecko，JS 完全不可检测）
- DuckMail / YYDS / Cloudflare / MailNest（Outlook）/ CloudMail 临时邮箱
- 注册后可选开启 NSFW
- 页面卡住重试、验证码失败换邮箱、浏览器重启与内存清理
- CLI：一次 `Ctrl+C` 安全停止，清理阶段不刷 traceback；再按一次强制中断

## 环境要求

- Python 3.10+（推荐 3.13）
- [Camoufox](https://camoufox.com/) 反检测浏览器（本机自动下载，无需安装 Chrome）
- 可用的 [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)
- 能访问注册页、临时邮箱 API、`auth.x.ai` 的网络（Device Flow / 授权码换 token 需要）

## 安装

```bash
git clone https://github.com/Git-creat7/grokRegister-cpa.git
cd grokRegister-cpa
pip install -r requirements.txt
camoufox fetch
cp config.example.json config.json
```

> **必须执行 `camoufox fetch`** 下载浏览器引擎。`pip install` 只安装 Python 库，浏览器引擎需要额外下载（约 300MB）。
> 详细安装步骤见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 配置

| 配置项 | 说明 |
| --- | --- |
| `cpa_auto_add` | 是否注册后 SSO→OAuth auth（关则只保存 SSO） |
| `cpa_auth_dir` | 本地 CPA auth 目录；写入 `xai-<email>.json`，可留空 |
| `cpa_remote_url` | 远程 CPA 地址，如 `http://你的CPA地址:8317` |
| `cpa_management_key` | 远程 CPA 管理密钥（`remote-management.secret-key` 明文） |
| `grok2api_auth_dir` | Grok2API / `~/.grok` 风格 auth 目录；写入 `g2a-<email>.json` |
| `register_workers` | 并发浏览器数，默认 1，最大 8 |
| `debug_mode` | 调试模式：强制单账号、结束后不关闭浏览器 |
| `log_level` | `info`（默认，隐藏 `[Debug]`）/ `debug`（全量日志） |

### 并发 / 调试 / 连通性

**并发 `register_workers`**
- 每个 worker 独立 Chrome 用户目录，降低资料目录冲突
- 实际并发不超过注册数量；worker 启动错开约 2 秒
- 浏览器连续启动失败时日志会提示降低并发

**调试模式 `debug_mode`**
- 强制数量=1、并发=1
- 任务结束后**不关闭**浏览器，方便你检查页面
- 中途换邮箱仍会 `restart_browser`（强制重启）

**连通性检查**
- GUI「连通性检查」或开始注册前自动跑
- 检查项：代理 TCP/出站、xAI 注册页、邮箱 API、CPA 本地目录/远程 Management API
- xAI 注册页使用 Chrome 指纹预检；出现真实 Cloudflare/HTTP 失败时停止建号，其它失败项只警告。代理不是必需项，只有当前出口被拦截时才需要配置

**NSFW**
- 自动开启失败**不阻塞**账号保存与 CPA 入库
- 可网页手动开启；批量时可关掉「注册后开启 NSFW」提速
| `email_provider` | `duckmail` / `yyds` / `cloudflare` / `mailnest` / `cloudmail` |
| `duckmail_api_base` | DuckMail/Mail.tm API 根地址，默认 `https://api.duckmail.sbs`；Mail.tm 填 `https://api.mail.tm` |
| `duckmail_api_key` | DuckMail API Key（`dk_...`）；Mail.tm 公共接口可不填 |
| `mailnest_api_key` | MailNest（迈巢 Outlook）API Key |
| `mailnest_project_code` | MailNest 项目代码，默认 `x-ai001` |
| `yyds_default_domain` | YYDS 固定收信域名；留空则自动选择已验证域名 |
| `cloudmail_url` | CloudMail 站点根地址，不要附加 `/api` |
| `cloudmail_admin_email` | CloudMail 管理员邮箱；也可用环境变量 `CLOUDMAIL_ADMIN_EMAIL` |
| `cloudmail_password` | CloudMail 管理员密码；也可用环境变量 `CLOUDMAIL_PASSWORD` |
| `register_count` | 目标注册数量 |
| `proxy` | 代理；换 token 的 OAuth 请求也走此代理 |
| `enable_nsfw` | 注册后是否尝试开启 NSFW |
| `cloudflare_api_base` | Cloudflare 临时邮箱 API 根地址 |
| `cloudflare_api_key` | 默认匿名模式留空；admin 模式填 `ADMIN_PASSWORD` |
| `cloudflare_auth_mode` | `none` / `bearer` / `x-api-key` / `x-admin-auth` / `query-key` |
| `cloudflare_custom_auth` | Worker 全局密码（`PASSWORDS`），注入 `x-custom-auth` |
| `cloudflare_path_*` | domains / accounts / token / messages 路径 |
| `defaultDomains` | Cloudflare / CloudMail 默认收信域名，多个用逗号分隔 |

### Cloudflare 邮箱（默认匿名）

```json
{
  "email_provider": "cloudflare",
  "cloudflare_api_base": "https://你的-worker-api-域名",
  "cloudflare_api_key": "",
  "cloudflare_auth_mode": "none",
  "cloudflare_path_domains": "/api/domains",
  "cloudflare_path_accounts": "/api/new_address",
  "cloudflare_path_token": "/api/token",
  "cloudflare_path_messages": "/api/mails",
  "defaultDomains": "你的收信域名.com"
}
```

匿名创建失败（例如 Turnstile）时可改 admin 创建：

```json
{
  "cloudflare_api_key": "你的 ADMIN_PASSWORD",
  "cloudflare_auth_mode": "x-admin-auth",
  "cloudflare_path_accounts": "/admin/new_address"
}
```

调试创建接口（使用 curl）：

```bash
curl -X POST "https://你的-worker-api-域名/admin/new_address" \
  -H "x-admin-auth: 你的 ADMIN_PASSWORD" \
  -H "Content-Type: application/json" \
  -d '{"name":"你的收信域名.com"}'
```

Worker 若配置了全局 `PASSWORDS`，再加：

```json
{ "cloudflare_custom_auth": "你的全局访问密码" }
```

### MailNest（Outlook 临时邮箱）

[迈巢 MailNest](https://mailnest.top/) 采用项目制。配置 API Key 与项目代码（默认 `x-ai001`）：

```json
{
  "email_provider": "mailnest",
  "mailnest_api_key": "你的 API Key",
  "mailnest_project_code": "x-ai001"
}
```

- API Key：https://mailnest.top/account  
- 项目代码：https://mailnest.top/buy-email（默认可直接用 `x-ai001`）

### YYDS 邮箱固定域名

默认自动选择已验证域名。若要固定收信域名：

```json
{
  "email_provider": "yyds",
  "yyds_default_domain": "你的收信域名.com"
}
```

GUI「YYDS 收信域名」可填；留空则自动选择。

### CloudMail 邮箱

支持自建 [maillab/cloud-mail](https://github.com/maillab/cloud-mail)。程序用管理员接口创建随机地址，公开接口收信，结束后删除地址：

```json
{
  "email_provider": "cloudmail",
  "cloudmail_url": "https://mail.example.com",
  "cloudmail_admin_email": "admin@example.com",
  "cloudmail_password": "你的管理员密码",
  "defaultDomains": "example.com"
}
```

`cloudmail_url` 填站点根地址，不要附加 `/api`。也可用环境变量 `CLOUDMAIL_URL` / `CLOUDMAIL_ADMIN_EMAIL` / `CLOUDMAIL_PASSWORD`（优先于 config）。

## CPA 自动入库

SSO 不是 CPA 凭据。程序会：

1. 用 SSO 先走 Device Flow，失败再走 Authorization Code（`referrer=grok-build`）向 `auth.x.ai` 换 `access_token` / `refresh_token`
2. 组装 `type=xai` 扁平 auth（`cli-chat-proxy.grok.com`）
3. 本地：`cpa_auth_dir` → `xai-<email>.json`（CPA 热加载）
4. 远程：`POST {cpa_remote_url}/v0/management/auth-files?name=...`（需管理密钥）

### 本地目录

```json
{
  "cpa_auto_add": true,
  "cpa_auth_dir": "你的CPA auth目录"
}
```

`cpa_auth_dir` 填 CPA 实际监听的 auth 目录路径即可。

### 远程 Management API

```json
{
  "cpa_auto_add": true,
  "cpa_auth_dir": "",
  "cpa_remote_url": "http://你的CPA地址:8317",
  "cpa_management_key": "你的管理密钥明文"
}
```

要求 CPA：`remote-management.allow-remote` 按访问方式配置；密钥为配置里的明文（启动后配置文件可能被写成 bcrypt，上传仍用明文）。

本地与远程可同时开启。日志前缀：`[CPA]`。

### 独立转换

已有 SSO 时可脱离注册流程：

```bash
# 写本地目录
python sso_to_auth_json.py --sso sso_list.txt --cpa-auth-dir /path/to/auths

# 上传远程 CPA
python sso_to_auth_json.py --sso sso_list.txt \
  --cpa-remote-url http://你的CPA地址:8317 \
  --cpa-management-key '你的管理密钥'

# 单个 cookie + 代理
python sso_to_auth_json.py --sso-cookie 'eyJ...' \
  --cpa-auth-dir ./auths \
  --proxy http://127.0.0.1:7890
```

`sso_list.txt`：一行一个 SSO，或 `邮箱----密码----sso`。

### 为什么必须用授权码流程

这是本项目区别于普通 SSO→token 脚本的关键，踩过坑后固化下来：

- **SSO 不能直接喂给 CPA。** CPA 走 OAuth，需要 `access_token` / `refresh_token`，SSO cookie 只是换 token 的入场券。
- **必须带 `referrer=grok-build`。** xAI 后端要求 access_token 携带 `referrer=grok-build` claim，否则 grok build 通道（`cli-chat-proxy.grok.com`）拒绝，调用 chat 时报 `permission-denied / Access to the chat endpoint is denied`。早期用 device flow 换的 token **不带**这个 claim，会全部失效。
- **解法：授权码流程（Authorization Code + PKCE）。** 在 `/oauth2/authorize` 和 consent 提交两处注入 `referrer=grok-build`，换出的 token 才带此 claim。程序换完会自动校验，日志显示 `access_token 已带 referrer=grok-build`。
- **base_url 必须是 `cli-chat-proxy.grok.com/v1`。** 写入的 auth 记录 `base_url` 指向 grok build 免费通道；若为空，CPA 会回退到计费通道 `api.x.ai/v1`，同样触发 `permission-denied`。

如果 CPA 里已有旧的失效号（`base_url=api.x.ai/v1` 或 `referrer=None`），用本节的独立转换脚本以相同邮箱重新生成一遍覆盖即可（文件名按 `xai-<email>.json` 命名，会原地覆盖）。

## 运行

### CLI

```bash
python grok_register_ttk.py cli
```

提示后输入 `start`。  
`Ctrl+C` 一次：当前账号收尾后停止；清理浏览器时不会因二次中断刷 traceback。再按一次强制退出。

### GUI

```bash
python grok_register_ttk.py
```

可在界面里改：邮箱服务商、代理、Cloudflare（API Base / 鉴权 / 收信域名 / 全局密码）、CPA 开关、auth 目录、远程地址与管理密钥。点击「开始注册」时会写回 `config.json`。

## 输出文件

均写在 `accounts/` 目录下（自动创建），避免堆在项目根目录：

| 文件 | 内容 |
| --- | --- |
| `accounts/accounts_*.txt` | 邮箱、密码、SSO |
| `accounts/mail_credentials.txt` | 临时邮箱凭证 |
| `accounts/sso_pending.txt` | CPA 失败时待重转的 SSO |
| `accounts/sso_risk_rejected.txt` | `policy=deny,event=$registration` 的注册风控账号，不再重试 OAuth |

均含敏感信息，已在 `.gitignore` 中忽略。`config.json` 也不提交，请用 `config.example.json` 复制。

## 稳定性

- 每账号结束后重启浏览器
- 每成功 5 个账号做一次内存清理
- 邮箱提交后确认页面前进，避免空等验证码
- 未收到验证码时换邮箱重试
- 最终页卡住时重试当前账号

## 常见问题

**CPA 没出现新账号**  
检查 `cpa_auto_add`、`cpa_auth_dir` 或 `cpa_remote_url` + `cpa_management_key`；看 `[CPA]` 日志是否换 token / 上传成功；本机/服务器能否访问 `auth.x.ai`。

**日志出现 `invalid_grant Access denied`**
先看注册前的 `xAI注册页` 检查。代理不是必需项：当前检查已使用 Chrome 指纹，能返回 HTTP 200 就可直连；只有该检查仍为 Cloudflare/HTTP 失败时才更换 `proxy`。若账号页面状态为 `policy=deny,event=$registration`，账号已被服务端标记，程序会跳过三条 OAuth 路径并写入 `accounts/sso_risk_rejected.txt`，不要继续重转该 SSO。

**远程上传失败**  
确认 CPA 管理 API 已启用、密钥明文正确；远程访问需 `allow-remote: true`。可用：

```bash
curl -H "Authorization: Bearer <管理密钥>" \
  http://你的CPA地址:8317/v0/management/auth-files
```

`cpa_remote_url` 填 CPA 实例根地址，不要附带 OpenAI 兼容接口的 `/v1`。程序会自动追加 `/v0/management/auth-files`。

**创建 Cloudflare 邮箱时 curl 超时**

如果当前网络需要代理访问 `workers.dev`，请在 GUI 的“代理”字段或 `config.json` 的 `proxy` 中显式填写代理地址。不要只依赖终端的 `HTTP_PROXY` / `HTTPS_PROXY`，从桌面启动 GUI 时可能不会继承这些环境变量。

**开启 NSFW 时返回 403**

设置出生日期可能被 `grok.com` 的 Cloudflare 防护拦截。该步骤失败不会影响账号保存和 CPA 入库；不需要敏感内容时可关闭“注册后开启 NSFW”。

**CLI 为什么还开浏览器**  
CLI 只是不启动 Tk；注册页、Turnstile、SSO 仍依赖真实浏览器。

**NSFW 失败**  
常见为 Cloudflare 拦截。账号仍会保存并入库 CPA。

**国内服务器调模型超时**  
入库成功只说明凭证到了 CPA；调用上游 `cli-chat-proxy.grok.com` 还需服务器出网可达（或配置 CPA `proxy-url`）。

**CPA 返回 `503 auth_unavailable: no auth available`**  
不是网络超时，而是 CPA 当前没有可用的 xAI auth。检查：auth 是否写入并被热加载、token 是否带 `referrer=grok-build`、账号是否 403 权限拒绝或 429 免费额度耗尽。free 号走 `cli-chat-proxy` 的 build 通道，额度与权限由上游控制，可能抖动。

**chat 报 `permission-denied` / Access to the chat endpoint is denied**  
token 缺 `referrer=grok-build`，或 `base_url` 误指向 `api.x.ai`。用本仓库授权码流程重转覆盖对应 `xai-<email>.json`。

## 目录结构

```text
.
├── grok_register_ttk.py      # 主程序（GUI / CLI + CPA 入库）
├── browser_session.py        # Camoufox 浏览器启停 / 会话管理
├── camoufox_adapter.py       # DrissionPage → Playwright 适配层
├── register_flow.py          # 注册页填表 / 验证码 / SSO / Turnstile
├── connectivity.py           # 启动前连通性检查
├── email_providers/
│   ├── common.py             # 验证码提取等共用工具
│   ├── duckmail.py           # DuckMail / Mail.tm
│   ├── cloudflare.py         # Cloudflare 临时邮箱
│   ├── yyds.py               # YYDS
│   ├── mailnest.py           # MailNest Outlook
│   └── cloudmail.py          # CloudMail
├── sso_to_auth_json.py       # SSO → CPA 转换（可独立运行）
├── config.example.json
├── requirements.txt
├── start-gui.cmd             # Windows 启动 GUI
├── start-cli.cmd             # Windows 启动 CLI
├── DEPLOYMENT.md             # 本机 / Windows 部署
├── tests/
└── assets/banner.png
```

## Star History

<a href="https://www.star-history.com/?type=date&repos=Git-creat7%2FgrokRegister-cpa">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=Git-creat7/grokRegister-cpa&type=date&theme=dark&legend=top-left&sealed_token=nLCws8QCmosQswlx1hTjASUcz8r72ZEKXOP1C8WmTFqosF65NL66q77qlMIbBZ6Kqic0cOqA5VisinVcERXNFlwMZqx0ET8872ALY3-k8rvCyvNqa-RxzMLV_oOrrAV54D0E6Pfv4WWTmaA6WYQBr2U5dizobLbasNLXpKTnZZJI7-uRL0zomGISzIGq" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=Git-creat7/grokRegister-cpa&type=date&legend=top-left&sealed_token=nLCws8QCmosQswlx1hTjASUcz8r72ZEKXOP1C8WmTFqosF65NL66q77qlMIbBZ6Kqic0cOqA5VisinVcERXNFlwMZqx0ET8872ALY3-k8rvCyvNqa-RxzMLV_oOrrAV54D0E6Pfv4WWTmaA6WYQBr2U5dizobLbasNLXpKTnZZJI7-uRL0zomGISzIGq" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=Git-creat7/grokRegister-cpa&type=date&legend=top-left&sealed_token=nLCws8QCmosQswlx1hTjASUcz8r72ZEKXOP1C8WmTFqosF65NL66q77qlMIbBZ6Kqic0cOqA5VisinVcERXNFlwMZqx0ET8872ALY3-k8rvCyvNqa-RxzMLV_oOrrAV54D0E6Pfv4WWTmaA6WYQBr2U5dizobLbasNLXpKTnZZJI7-uRL0zomGISzIGq" />
 </picture>
</a>

## License

[MIT](LICENSE)

## Acknowledgments

Thanks to [linux.do](https://linux.do) and [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI).
