# 部署指南

本文以 Linux 无头服务器为主，Python 3.10+ 可用；Web 面板同时支持 macOS，
Windows 浏览器批处理链路仍为实验性。发布版本在 Python 3.14 环境完成验证。

## 1. 安装

```bash
git clone https://github.com/lij768423-svg/grok-register-panel.git
cd grok-register-panel

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m camoufox fetch
```

`requirements.txt` 固定直接依赖版本；`requirements.lock.txt` 是发布环境的完整依赖快照。
`psutil` 是面板进程发现与安全停止的直接依赖，不应从安装列表中删去。

验证：

```bash
.venv/bin/python -m pip check
.venv/bin/python -m camoufox version
```

### 平台运行规则

- Linux 无 `DISPLAY` / `WAYLAND_DISPLAY` 时，面板和编排器自动使用 `xvfb-run`。
- Linux 有显示会话以及 macOS 直接启动 Camoufox，不调用 Xvfb。
- `GROK_USE_XVFB=1` 可在 Linux 强制使用 Xvfb，`GROK_USE_XVFB=0` 可明确直启；默认 `auto`。
- 任务解释器优先使用项目 `.venv`，缺失时复用启动面板的 Python；外部共享虚拟环境可用 `GROK_PYTHON_BIN` 显式固定。
- Linux 容器必须挂载 procfs 到 `/proc`。缺失时面板会拒绝启停任务并给出明确错误，避免在无法确认进程状态时重复启动。
- Windows 已兼容 `.venv\\Scripts\\python.exe` 与面板进程管理，但浏览器批处理仍需在目标环境单独验证。

## 2. 配置

```bash
cp config.example.json config.json
chmod 600 config.json
```

至少配置邮箱服务。需要自动写入 CPA 时，设置：

- `cpa_auto_add`
- `cpa_auth_dir`
- `grok2api_auth_dir`
- 可选的 `cpa_remote_url` 与 `cpa_management_key`

也可以在面板顶部打开“邮箱服务”，选择实际 provider 后填写、保存并测试连接。
面板只返回密钥是否已配置，不会回显 API Key、JWT 或密码；密钥输入留空会保留
原值，只有显式点“清除”并保存才会删除。连接测试使用当前表单内容但不会落盘。
配置仍写入 `config.json`，原子更新并保持 `0600`，其它已有配置项不会被覆盖。

代理池与 sticky 文件均属于凭据材料。运行权限脚本会将 `proxies*.txt`、
`stickies*.txt`、缓存文件及 `.env.monitor` 收紧为 `0600`。

面板“代理池”会把真实代理 URL 写入 `log/proxy_pool.json`，文件权限为 `0600`。
导入后先完成探活；有面板池条目时 worker 只使用健康且启用的代理，全部异常或
冷却时会停止对应任务。一个账号开始后，注册、SSO 与 OAuth 全程固定同一出口。

面板“邮箱服务”里的“域名轮换 · 高级设置”会把域名、provider、拒绝计数和轮换规则写入
`log/email_domain_pool.json`，文件权限为 `0600`。只有 xAI 明确拒绝邮箱域名时
才累计并按阈值拉黑；邮箱 API、验证码或网络异常不会处罚域名。对应 provider
池耗尽时 worker 会停止该任务，不会回退到已被停用或拉黑的旧域名配置。

## 3. 发布前检查

```bash
PYTHON_BIN=.venv/bin/python scripts/run_tests.sh
.venv/bin/python scripts/harden_runtime_permissions.py .
```

如果旧版本曾把自动 ASN 黑名单写入 `browser_session.py`，覆盖代码前先迁移：

```bash
.venv/bin/python scripts/migrate_legacy_blacklist.py \
  --source browser_session.py \
  --state log/blacklist_state.json
```

## 4. 临时启动面板

```bash
export MONITOR_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export MONITOR_HOST=127.0.0.1
export MONITOR_PORT=8787
export PANEL_INCLUDE_TAIL=0
export CPA_AUTH_DIR="$PWD/cpa_auth"
# 可选：服务使用项目外虚拟环境时显式指定
# export GROK_PYTHON_BIN=/opt/grok-runtime/bin/python
# 可选：auto / 1 / 0；默认 auto
# export GROK_USE_XVFB=auto
# 可选：覆盖代理池状态位置与冷却时间
# export PROXY_POOL_STATE_FILE="$PWD/log/proxy_pool.json"
# export PROXY_NETWORK_COOLDOWN_SECONDS=90
# export PROXY_RISK_COOLDOWN_SECONDS=1800
# 可选：覆盖邮箱域名池状态位置
# export EMAIL_DOMAIN_POOL_STATE_FILE="$PWD/log/email_domain_pool.json"

.venv/bin/python -u webui/monitor.py
```

局域网或 Tailscale 部署时，将 `MONITOR_HOST` 设置为目标网卡的具体 IP；不要使用 `0.0.0.0`。浏览器打开面板后，在“访问令牌”输入与环境变量相同的值。

## 5. systemd 持久运行

复制并按实际用户和目录修改：

```bash
sudo cp deploy/grok-register-panel.service.example /etc/systemd/system/grok-register-panel.service
sudo cp deploy/monitor.env.example /etc/grok-register-panel.env
sudo chmod 600 /etc/grok-register-panel.env
sudo systemctl daemon-reload
sudo systemctl enable --now grok-register-panel.service
```

服务必须满足：

- `UMask=0077`
- `PANEL_INCLUDE_TAIL=0`
- 绑定具体 loopback、LAN 或 Tailscale IP
- `MONITOR_TOKEN` 使用至少 32 字节随机值
- `Restart=on-failure`

验证：

```bash
systemctl status grok-register-panel.service --no-pager
curl http://目标地址:8787/api/health
curl -o /dev/null -w '%{http_code}\n' http://目标地址:8787/api/status
curl -H "Authorization: Bearer $MONITOR_TOKEN" http://目标地址:8787/api/status
```

第二条状态接口在未带 Token 时应返回 `401`。

## 6. 运行任务

从面板启动时会按上述平台规则自动选择 Xvfb。直接执行单批时：

```bash
# Linux 无头
xvfb-run -a .venv/bin/python -u run_batch_headless.py 20 3

# Linux 有显示 / macOS
.venv/bin/python -u run_batch_headless.py 20 3
```

以下辅助脚本仅用于 Linux/Xvfb：

```bash
scripts/run_xvfb_smoke.sh 1
scripts/run_xvfb_batch.sh 10
```

持续编排建议从面板启动；停止操作只会结束当前项目目录下的编排和批处理进程。

## 7. 账号补录

面板的“账号补录”支持：

- `sso_pending.txt` 补录，成功后立即出队
- 扫描全部 `accounts/*.txt`
- 跳过本地 CPA 已存在邮箱
- 停止正在运行的补录进程

命令行：

```bash
.venv/bin/python sso_to_auth_json.py \
  --sso accounts/sso_pending.txt \
  --from-config config.json \
  --consume-success \
  --report-json log/recovery_report.json
```

## 8. 安全边界

- `/api/health` 和静态页面可匿名访问；运行数据 API 在配置 Token 后要求鉴权。
- 不要通过公网裸露内置 HTTP 服务。公网访问应放在有 TLS 和额外身份认证的反向代理后。
- 生产环境不要启用原始日志尾部。
- 不要把 Token 写入 URL、命令行参数、仓库或 issue。
- 代理池 API 不返回账号密码，但 `log/proxy_pool.json` 本身含真实凭据，备份与迁移时按密钥材料处理。
- 邮箱域名池不保存邮箱账号密码，但 `log/email_domain_pool.json` 仍属于运行状态，迁移时保留 `0600` 权限。
- 面板使用内置 HTTP 服务，适合单机、LAN 或 tailnet 运维，不替代互联网边界网关。
