# 📜 Changelog

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.13.1] - 2026-09-18

### ✨ Added
- **GPT5.6-5.5** (`packages/破限工具/GPT5.6-5.5`): 新增子模块（上游 `https://github.com/zxr-roro/GPT5.6-5.5-`）—— zzy 系列 GPT-5.6 / 5.5 Codex 破限与逆向 skill 合集。
  - `zzy-codex5.6/game-hacking-techniques-SKILL.md`：游戏逆向与内存修改技能包
  - `zzy-codex5.6/zzy-Codex-5.6/`：Codex 5.6 破限配置
  - `zzy-codex5.6/zzy-reverse-skill/`：逆向分析 skill 包
  - 子模块路径去掉了上游仓库名的结尾连字符（`GPT5.6-5.5-` → `GPT5.6-5.5`）

### 📝 Documentation
- README:「破限工具」表新增 GPT5.6-5.5 条目，子模块计数 48 → 49，版本升至 v2.13.1。
- `docs/dir-mappings.json`: 新增 `GPT5.6-5.5` 的目录树描述。

---

## [2.13.0] - 2026-09-18

### ✨ Added
- **aipocket** (`packages/general/aipocket`): 新增子模块 —— AI 基础设施暴露面与泄露凭证发现平台（Rust 2024 workspace + Axum + React 19 + PostgreSQL 16 / Redis 7，Docker 一键部署）。
  - FOFA / Shodan / GitHub Artifact Hunter 多源发现，多 key 轮询
  - 风险门控 + 并发验证（`VALIDATE_CONCURRENCY`）、余额查询、AI CVE 同步（Tavily）
  - Web UI + JWT 鉴权 + SSE 实时扫描管理；高价值 key 跨 run 累积去重，PostgreSQL 为持久化真源
- **omni-flow 羊** (`packages/破限工具/omni-flow 羊`): 全域安全研究 skill 路由器（`SKILL.md` + 20 个 references + 3 个脚本），按任务匹配最贴切的已装技能。
- **grok4.6-小码酱.md** (`packages/破限工具`): Grok 4.6 破限指令（小码酱 persona 版）。
- **富江codex全破 GPT6全破.zip** (`packages/破限工具`): Codex / GPT-6 破限合集（多语言变体 + PowerShell 一键安装脚本）。
- **Web与AI安全测试skill.zip** (`packages/破限工具`): Web 与 AI 安全测试 skill 包（secknowledge-skill）。
- **教学文档.zip** (`packages/破限工具`): 逆向教学 10 步流程文档。

### 📝 Documentation
- README:「逆向与通用工具」表新增 aipocket，「破限工具」表新增 5 个条目，子模块计数 47 → 48，版本升至 v2.13.0。
- `docs/dir-mappings.json`: 新增 `omni-flow 羊` 的目录树描述。

---

## [2.12.2] - 2026-09-18

### ✨ Added
- **Zcode2Api** (`packages/Zcode/Zcode2Api`): 新增 `Zcode` 分类子模块 —— Z.AI（ZCode Start Plan）反向代理（Go 单文件）。
  - OpenAI（`/v1/chat/completions`）与 Anthropic（`/v1/messages`）双协议兼容
  - JWT 号池轮换 + 配额耗尽自动故障切换（429 / 3012 / 3007 / 3009 / 3010 / 529），代理 sticky / rotate 与失败自动暂停
  - 内置 Node.js 验证码求解器（阿里云验证码）、SQLite 存储、实时配额仪表盘
  - 模型目录随账号账单同步（当前 GLM-5.3 / GLM-5.3-Flash），可直接对接 Cursor / Claude Code / OpenCode

### 📝 Documentation
- README 新增「🧩 Zcode 模块」导航小节与子模块列表条目，目录树渲染顺序接入 `Zcode`（`docs/dir-mappings.json` + `readme-structure.yml`），子模块计数 38 → 47，版本升至 v2.12.2。
- `readme-structure.yml`：`packages/*` 分类的目录树注释改为读取 `dir-mappings.json` 的 `packages` 描述（原先硬编码为「核心注册与 API 兼容层」），各分类说明现在正确显示。

---

## [2.12.1] - 2026-09-18

### ✨ Added
- **GLM** (`GLM/data`): Mistral Console 反向代理（Go 实现）。
  - `POST /v1/chat/completions` OpenAI 兼容，支持非流式与 `stream=true` SSE
  - 模型名自动映射（`glm-5.2` / `zai-glm-5-2` 等变体 → `glm-5-2`），默认注入 Playground 系统提示词与工具（`code_interpreter` / `image_generation` / `web_search`）
  - 多上游 key 轮询 + 失败状态码冷却切换（401/402 长冷却、429/5xx 短冷却），持久化到 `data/keys.json`
  - 本地鉴权（`X-API-Key` / `Authorization: Bearer` / `?api_key=` 三选一）、Playground 风格 Web UI、会话查询
  - 提供 `Dockerfile` / `docker-compose.yml` / `.env.example`，支持 Docker 一键部署

### 📝 Documentation
- README 根目录工具树与导航表补充 GLM 条目，版本升至 v2.12.1。
- 更新 `docs/dir-mappings.json`：补充 GLM 根目录映射，以及破限工具新增子目录（NERV-BREAK-5.6 / ctf-sandbox / MD / dsh / gpt-5.6-instruct / open-reverselab / ReiPenFlow）的中文描述。
- `readme-structure.yml`：自动目录树的根目录渲染顺序加入 `GLM`，避免下次自动生成时条目被丢弃。

---

## [2.12.0] - 2026-09-18

### ✨ Added
- **NERV-BREAK-5.6** (`packages/破限工具/5.6-JAILBREAK-NERV-codex-instruct-5.6-main`): 基于上下文结构工程的 GPT-5.6 / codex-instruct-5.6 破限框架。
  - 三层纵深防御：上下文重构（`bridge.md`）、MCP Server（`mcp_server.py`）、代理中继（`proxy_relay.py`）
  - 内置 28 个技能包（`skills/`：full-pentest、full-reverse、crack-keygen、anti-debug、evasion 等）
  - 一键部署：`deploy.py` / `direct_setup.py` / `verify.py`，附 Windows、Kali 部署脚本
- **ctf-sandbox / 小刘破甲** (`packages/破限工具/ctf-sandbox`): 针对 gpt-5.6-sol / gpt-5.5 的 Codex CLI 破限提示词与一键部署工具。
  - `deploy.py` 一键下发（自动发现 `~/.codex`、自动备份、字段级配置不破坏原有 provider）、`ask.py` API 直连绕过客户端过滤、`check.py` 部署诊断
  - 提示词源文件 `ctf-sandbox.md`，附带 `Leila-Codex-5.6.exe`（Git LFS）
- **MD/CLAUDE.md** (`packages/破限工具/MD`): Claude 端破限指令模板（云技能 `$l-*` 按需换取的加载机制 + W-License 破解/绕过激活流程）。
- **小钻风破甲.7z** (`packages/破限工具/小钻风破甲.7z`): 穿甲破限合集归档。

### 🔧 Fixed
- **大文件改用 Git LFS**: 181 MB 的 `小钻风破甲.7z` 与 85 MB 的 `Leila-Codex-5.6.exe` 纳入 LFS 跟踪，避免超过 GitHub 单文件 100 MB 限制。

### 📝 Documentation
- 更新主 README：破限工具树形结构修正为 `packages/` 同级节点，补充 4 个新增工具条目与 LFS 使用说明。
- 同步 8 个子模块指针（general/reg-factory、general/all-in-one-register、grok/grok2api-egress-enhancements、破限工具/Claude code、破限工具/codex、破限工具/grok、破限工具/dsh/dsh-pentest、破限工具/dsh/dsh-purge）。

---

## [2.11.10] - 2026-08-20

### ✨ Added

### 🔧 Fixed


## [2.11.9] - 2026-08-20

### ✨ Added

### 🔧 Fixed


## [2.11.8] - 2026-08-20

### ✨ Added

### 🔧 Fixed


## [2.11.7] - 2026-08-20

### ✨ Added

### 🔧 Fixed


## [2.11.6] - 2026-08-20

### ✨ Added

### 🔧 Fixed


## [2.11.5] - 2026-08-19

### ✨ Added

### 🔧 Fixed


## [2.11.4] - 2026-08-19

### ✨ Added

### 🔧 Fixed


## [2.11.3] - 2026-08-19

### ✨ Added

### 🔧 Fixed


## [2.11.2] - 2026-08-19

### ✨ Added

### 🔧 Fixed


## [2.11.1] - 2026-08-17

### ✨ Added

### 🔧 Fixed


## [2.11.0] - 2026-08-17

### ✨ Added

### 🔧 Fixed


## [2.10.1] - 2026-08-17

### ✨ Added

### 🔧 Fixed


## [2.10.0] - 2026-08-17

### ✨ Added

### 🔧 Fixed


## [2.9.0] - 2026-08-17

### ✨ Added

### 🔧 Fixed


## [2.8.7] - 2026-08-17

### ✨ Added

### 🔧 Fixed


## [2.8.6] - 2026-07-28

### ✨ Added

### 🔧 Fixed


## [2.8.5] - 2026-07-28

### ✨ Added

### 🔧 Fixed


## [2.8.4] - 2026-07-28

### ✨ Added

### 🔧 Fixed


## [2.8.3] - 2026-07-28

### ✨ Added

### 🔧 Fixed


## [2.8.2] - 2026-07-28

### ✨ Added

### 🔧 Fixed


## [2.8.1] - 2026-07-28

### ✨ Added

### 🔧 Fixed


## [2.8.0] - 2026-07-28

### ✨ Added

### 🔧 Fixed


## [2.7.0] - 2026-07-28

### ✨ Added

### 🔧 Fixed


## [2.6.1] - 2026-07-22

### ✨ Added

### 🔧 Fixed


## [2.6.0] - 2026-07-22

### ✨ Added
- **gpt-outlook-register**: 基于 Outlook 的 ChatGPT 账号自动注册工具
  - 绕过验证码的 GPT Free 注册流程
  - 用法: `cd gpt-outlook-register && pip install -r requirements.txt && python start_webui.py`
- **nvidia-register** (`packages/nvidia/nvidia-register`): NVIDIA 账号半自动注册工具
  - 自动注册 NVIDIA BUILD 账号
  - 自动创建 AI_PLAYGROUNDS_KEY
- **grokcli-2api** (`packages/grok/grokcli-2api`): Grok CLI 转 API 工具
- 子模块总数从 33 个增加到 34 个

### 🔧 Fixed


## [2.5.1] - 2026-07-20

### ✨ Added

### 🔧 Fixed


## [2.6.0] - 2026-06-09

### ✨ Added
- **team/**: ChatGPT Team 纯协议注册机，支持 Token 续签、批量注册与动态代理。
  - 支持 `--check-tokens` 命令进行 Token 自动续签
  - 支持多线程批量注册，防止 Cloudflare 拦截
  - 导出 CPA 格式 Token，可转换为 sub2api 格式
- **CPA-Manager-Plus** (`packages/codex/CPA-Manager-Plus`): Codex Plus Account 管理工具，支持 Token 批量管理与格式转换。
- **CPA2sub2API** (`packages/codex/CPA2sub2API`): CPA 格式 Token 转 sub2api 格式工具。
- **cockpit-tools** (`packages/general/cockpit-tools`): OpenAI Cockpit 管理工具集。
- **gpt-trahatel** (`packages/openai/gpt-trahatel`): GPT 相关工具集。
- **oai-Team-SSO-OIDC** (`packages/openai/oai-Team-SSO-OIDC`): OpenAI Team SSO OIDC 协议实现，支持企业级注册流程。

### 📝 Documentation
- 为 `team/` 目录添加完整 README 文档
- 更新主 README，新增 Codex 模块分类
- 子模块总数从 27 个增加到 32 个

---

## [2.5.0] - 2026-05-13

### ✨ Added
- **all-in-one-register** (`packages/general/all-in-one-register`): OpenAI, Grok, Tavily 注册机。
- **chatgpt-auto-register** (`packages/openai/chatgpt-auto-register`): 基于 Selenium 的全自动注册（高成功率）。
- **openai-auto-register** (`packages/openai/openai-auto-register`): 自动化注册流水线（强化反检测）。
- **gpt4free** (`packages/general/gpt4free`): 行业领先的多源逆向 API 聚合。
- **open-proxy-ai** (`packages/general/open-proxy-ai`): GPT-4o 免费逆向代理。
- **free-unofficial-openai-api** (`packages/openai/free-unofficial-openai-api`): 支持最新音频预览模型的免费接口。

### 💄 UI/UX
- **README 重构**: 全面美化文档结构，采用 Unicode 树形图，优化分类导航与快速入门指南。
- **文档美化**: 统一所有核心文档的视觉风格与格式。

---

## [2.4.2] - 2026-05-13

### 🔧 Fixed
- **子模块扁平化**: 将已 404 的 `outlook-auto-register` 转换为常规目录，确保核心代码永不丢失。
- **工作流增强**: 优化 `submodule-sync.yml`，增加 URL 存活性检查与可视化同步报告。

---

## [2.4.1] - 2026-05-13

### 🐛 Fixed
- 修复失效的子模块 URL (gemini-balance-do, exa-free, real-random-taxfree-address)。
- 移除已冗余的子模块引用。

---

## [2.4.0] - 2026-05-13

### ✨ Added
- **gopay-plus-auto** 子模块 (`packages/general/gopay-plus-auto`)。
- **Submodule Sync Workflow**: 自动化维护子模块状态。

---

## [2.3.0] - 2026-04-10

### ✨ Added
- Codex OAuth 批量自动化 Chrome 扩展。
- Codex 远程注册机 V2 (Browserbase + DDG)。
- 浏览器扩展插件集 (含 2925 自动化)。

---

## [2.2.0] - 2026-04-01

### ✨ Added
- **grok2api** 子模块。
- **real-random-taxfree-address** 工具。

---

## [2.1.0] - 2026-03-27

### ✨ Added
- **tempmail** 子模块。
- MIT LICENSE 文件与贡献指南。

### 🔧 Fixed
- 解决 9 个子模块 `not our ref` 克隆失败问题。

---

## [2.0.0] - 2026-03-25

### 🚀 Major Changes
- 首次大规模整合 OpenAI, Claude, Gemini, Codex 生态工具。
- 引入 `packages/` 模块化管理体系。
