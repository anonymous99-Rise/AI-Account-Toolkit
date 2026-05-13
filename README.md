# AI-Account-Toolkit

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/adminlove520/AI-Account-Toolkit)](https://github.com/adminlove520/AI-Account-Toolkit/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/adminlove520/AI-Account-Toolkit)](https://github.com/adminlove520/AI-Account-Toolkit/network)
[![GitHub last commit](https://img.shields.io/github/last-commit/adminlove520/AI-Account-Toolkit)](https://github.com/adminlove520/AI-Account-Toolkit/commits/main)

**AI 账号注册与管理一站式工具集** — 涵盖 ChatGPT、Claude、Gemini、Codex、Cursor、Grok 批量注册、Token 管理、临时邮箱服务等 30+ 工具。

> _A curated collection of 30+ tools for AI account registration & management — covering ChatGPT, Claude, Gemini, Codex, Cursor, Grok batch registration, token management, and temporary email services._

---

## 目录

- [项目结构](#项目结构)
- [项目导航](#项目导航)
  - [根目录项目](#根目录项目)
  - [OpenAI 相关 (packages/openai)](#openai-相关-packagesopenai)
  - [Claude 相关 (packages/claude)](#claude-相关-packagesclaude)
  - [Gemini 相关 (packages/gemini)](#gemini-相关-packagesgemini)
  - [Codex 相关 (packages/codex)](#codex-相关-packagescodex)
  - [Cursor 相关 (packages/cursor)](#cursor-相关-packagescursor)
  - [Grok 相关 (packages/grok)](#grok-相关-packagesgrok)
  - [邮箱服务 (packages/email)](#邮箱服务-packagesemail)
  - [通用工具 (packages/general)](#通用工具-packagesgeneral)
- [快速开始](#快速开始)
- [注意事项](#注意事项)
- [故障排除](#故障排除)
- [贡献指南](#贡献指南)
- [Star History](#star-history)
- [免责声明](#免责声明)

---

## 项目结构

```
AI-Account-Toolkit/
├── CPAtools/                # Codex 账号管理工具
├── GPT-team/                # GPT 团队全自动注册工具
├── chatgpt_register_duckmail/ # DuckMail 注册工具
├── GPT_register+duckmail+CPA+autouploadsub2api/ # DuckMail + OAuth + Sub2Api 注册工具
├── team_all-in-one/         # ChatGPT Team 一键注册工具
├── codex/                   # Codex 相关工具
├── codex-oauth-automation-extension/ # Codex OAuth 批量自动化 Chrome 扩展
├── codex-register-V2/       # Codex 远程注册机 V2 (Browserbase + DDG)
├── Extensions/              # 浏览器扩展插件集 (含 2925 自动化)
├── FreeSMS/                 # 免费在线接码平台资料
├── mailhub/                 # 邮箱分享资料
├── grok/                    # SuperGrok 相关资料
├── freemail/                # 临时邮箱服务
├── merge-mailtm-share/      # MailTM 邮箱合并工具
├── ob12api/                 # OB12 API 服务
├── openai_pool_orchestrator_v5/ # OpenAI 账号池管理工具
├── openai_pool_orchestrator-V6/ # OpenAI 账号池编排器（新版本）
├── ClashVerge_/             # ClashVerge 非港轮询脚本
├── openai_register/         # OpenAI 注册脚本
├── Register_GPT_v0/         # GPT 注册工具
├── Code-Patch/              # 代码补丁工具
└── packages/                # 分类子模块目录
    ├── openai/              # OpenAI 相关子模块
    │   ├── ab-card/         # ChatGPT Business/Plus 自动开通工具
    │   ├── chatgpt-creator/ # ChatGPT 账号创建工具
    │   └── openai-oauth/    # OpenAI OAuth 认证工具
    ├── claude/              # Claude 相关子模块
    │   └── claude-key-switch/ # Claude 密钥切换工具
    ├── gemini/              # Gemini 相关子模块
    │   └── gemini-balance-do/ # Gemini 余额查询工具
    ├── codex/               # Codex 相关子模块
    │   ├── codex-lb/        # Codex 负载均衡工具
    │   ├── codex-register/  # Codex 注册脚本
    │   └── codex-register-fix/ # Codex 注册修复版本
    ├── cursor/              # Cursor 相关子模块
    │   └── cursor-auto-register/ # Cursor 自动注册工具
    ├── grok/                # Grok 相关子模块
    │   ├── grok-register/   # x.ai 注册批处理工具
    │   └── grok2api/        # Grok API 转换服务
    ├── email/               # 邮箱相关子模块
    │   ├── cloudflare-temp-email/ # Cloudflare 临时邮箱服务
    │   ├── tempmail/        # 自托管临时邮箱服务
    │   ├── ms-oauth2-api/   # 微软 OAuth2 邮件取件 API
    │   ├── hotmail-outlook-auto-register/ # Hotmail 自动创建
    │   └── outlook-auto-register/ # Outlook 邮箱注册工具集
    └── general/             # 通用工具子模块
        ├── any-auto-register/ # 多平台账号自动注册工具
        ├── api-key-scraper/ # 多平台 API 密钥抓取工具
        ├── mregister/       # ChatGPT 注册机 Web UI
        ├── exa-free/        # Exa 免费使用工具
        ├── real-random-taxfree-address/ # 真实随机免税地址生成
        └── gopay-plus-auto/ # Gopay+ 自动化工具
```

---

## 项目导航

### 根目录项目

#### 1. CPAtools - Codex 账号管理工具

**功能**：批量检查和清理失效的 Codex 账号，通过 HTTP 请求验证账号状态，自动删除 401 失效账号。

**主要文件**：`manager.py` · `README.md`

**使用指南**：[CPAtools/README.md](CPAtools/README.md)

#### 2. GPT-team - 全自动协议注册工具（CF 临时邮箱版）

**功能**：纯 HTTP 协议注册子号，母号自动登录获取 Token，自动拉 Team 邀请，自动 Codex OAuth 授权上传 CPA。

**主要文件**：`get_tokens.py` · `gpt-team-new.py` · `config.yaml` · `accounts.txt`

**使用指南**：[GPT-team/README.md](GPT-team/README.md)

#### 3. chatgpt_register_duckmail

**功能**：使用 DuckMail 进行 ChatGPT 账号注册的工具。

**使用指南**：[chatgpt_register_duckmail/README.md](chatgpt_register_duckmail/README.md)

#### 4. GPT_register+duckmail+CPA+autouploadsub2api

**功能**：使用 DuckMail 临时邮箱进行 ChatGPT 批量并发注册，支持 OAuth 自动登录获取 Token，可选自动上传 Token 到 Sub2Api 平台。

**使用指南**：[GPT_register+duckmail+CPA+autouploadsub2api/README.md](GPT_register+duckmail+CPA+autouploadsub2api/README.md)

#### 5. team_all-in-one - ChatGPT Team 一键注册工具

**功能**：功能完整的 Web 管理界面，用于批量注册 ChatGPT Team 账号。支持多种临时邮箱服务、代理配置、OAuth 自动授权，以及 Token 导出功能。

**使用指南**：[team_all-in-one/README.md](team_all-in-one/README.md)

#### 6. codex - Codex 相关工具

**功能**：Codex 相关工具，包含协议密钥生成等功能。

**使用指南**：[codex/README.md](codex/README.md)

#### 7. freemail - 临时邮箱服务

**功能**：基于 Cloudflare Worker 的临时邮箱服务，支持邮箱管理、邮件转发等功能。

**使用指南**：[freemail/README.md](freemail/README.md)

#### 8. merge-mailtm-share - MailTM 邮箱合并工具

**功能**：合并和管理 MailTM 临时邮箱，支持批量操作和状态管理。

**使用指南**：[merge-mailtm-share/README.md](merge-mailtm-share/README.md)

#### 9. ob12api - OB12 API 服务

**功能**：提供 OB12 相关的 API 服务，支持账号注册和管理。

**使用指南**：[ob12api/README.md](ob12api/README.md)

#### 10. openai_pool_orchestrator_v5 - OpenAI 账号池管理工具

**功能**：管理 OpenAI 账号池，支持自动注册、维护和使用。

**使用指南**：[openai_pool_orchestrator_v5/README.md](openai_pool_orchestrator_v5/README.md)

#### 11. openai_pool_orchestrator-V6 - OpenAI 账号池编排器（新版本）

**功能**：OpenAI 账号池编排器，支持自动化注册、Token 管理与多平台账号池维护。

**使用指南**：[openai_pool_orchestrator-V6/README.md](openai_pool_orchestrator-V6/README.md)

#### 12. ClashVerge_ - ClashVerge 非港轮询脚本

**功能**：为 ClashVerge 设计的全局扩写脚本，创建非香港节点的负载均衡组，用于注册机等场景。

**使用指南**：[ClashVerge_/README.md](ClashVerge_/README.md)

#### 13. codex-oauth-automation-extension - Codex OAuth 批量自动化 Chrome 扩展

**功能**：批量跑通 ChatGPT OAuth 注册/登录流程。支持单步/整套自动执行、DDG 邮箱别名生成、验证码自动获取等功能。

**使用指南**：[codex-oauth-automation-extension/README.md](codex-oauth-automation-extension/README.md)

#### 14. codex-register-V2 - Codex 远程注册机 V2

**功能**：基于 Browserbase 远程浏览器和 DDG 邮箱别名的 Codex Token 自动注册工具，分两阶段完成注册和 OAuth 授权。

**使用指南**：[codex-register-V2/eefdb42dd6dfcbb5acee9fa2efeb03d775a509df/README.md](codex-register-V2/eefdb42dd6dfcbb5acee9fa2efeb03d775a509df/README.md)

#### 15. Extensions - 浏览器扩展插件集

**功能**：包含用于自动注册的浏览器插件，如 `autoRegisterPlugins` 针对 2925 邮箱实现的无限别名自动化注册流程。

**使用指南**：[Extensions/autoRegisterPlugins/README.md](Extensions/autoRegisterPlugins/README.md)

#### 16. FreeSMS - 免费在线接码平台资料

**功能**：收集整理全球多个主流免费接码平台资料，用于注册辅助。

#### 17. mailhub - 邮箱分享资料

**功能**：邮箱账号分享及相关资源汇集。

#### 18. grok - Grok 相关资料

**功能**：包含 SuperGrok 等 Grok 平台的相关研究资料。

#### 19. openai_register - OpenAI 注册脚本

**功能**：用于 OpenAI 账号注册的自动化 Python 脚本。

---

### OpenAI 相关 (packages/openai)

#### 20. ab-card - ChatGPT Business/Plus 自动开通工具

**功能**：全自动注册 ChatGPT 账号 + 开通 Business 或 Plus 套餐（首月免费），支持 Web UI 操作。

**主要文件**：`ui.py` · `auth_flow.py` · `browser_payment.py` · `admin_cli.py` · `config.example.json`

**使用指南**：[packages/openai/ab-card/README.md](packages/openai/ab-card/README.md)

#### 21. chatgpt-creator - ChatGPT 账号创建工具

**功能**：ChatGPT 账号自动创建工具，支持批量注册和自动化流程。

**使用指南**：[packages/openai/chatgpt-creator/README.md](packages/openai/chatgpt-creator/README.md)

#### 22. openai-oauth - OpenAI OAuth 认证工具

**功能**：OpenAI OAuth 认证工具，提供 OAuth 自动化认证和 Token 获取功能。

**使用指南**：[packages/openai/openai-oauth/README.md](packages/openai/openai-oauth/README.md)

---

### Claude 相关 (packages/claude)

#### 23. claude-key-switch - Claude 密钥切换工具

**功能**：Claude API 密钥管理 and 切换工具，支持多密钥轮换和负载均衡。

**使用指南**：[packages/claude/claude-key-switch/README.md](packages/claude/claude-key-switch/README.md)

---

### Gemini 相关 (packages/gemini)

#### 24. gemini-balance-do - Gemini 余额查询工具

**功能**：Gemini API 余额查询和管理工具。

**使用指南**：[packages/gemini/gemini-balance-do/README.md](packages/gemini/gemini-balance-do/README.md)

---

### Codex 相关 (packages/codex)

#### 25. codex-lb - Codex 负载均衡工具

**功能**：Codex API 负载均衡工具，支持多实例分发和健康检查。

**使用指南**：[packages/codex/codex-lb/README.md](packages/codex/codex-lb/README.md)

#### 26. codex-register - Codex 注册脚本

**功能**：基于 Python 的 HTTP 自动化脚本，通过接口执行账号注册/登录相关步骤，并通过 MailAPI 轮询邮箱验证码，注册完成后自动上传到 CPA。

**使用指南**：[packages/codex/codex-register/README.md](packages/codex/codex-register/README.md)

#### 27. codex-register-fix - Codex 注册修复版本

**功能**：基于 codex-manager 二次开发，修复了原项目因 OpenAI 授权流程变更导致的注册失败问题。

**使用指南**：[packages/codex/codex-register-fix/README.md](packages/codex/codex-register-fix/README.md)

---

### Cursor 相关 (packages/cursor)

#### 28. cursor-auto-register - Cursor 自动注册工具

**功能**：Cursor 编辑器账号自动注册和管理工具。

**使用指南**：[packages/cursor/cursor-auto-register/README.md](packages/cursor/cursor-auto-register/README.md)

---

### Grok 相关 (packages/grok)

#### 29. grok-register - x.ai 注册批处理工具

**功能**：面向 x.ai 注册批处理的一体化项目，提供控制台、注册执行器、WARP 网络出口、grok2api token 落池和运行时环境。

**主要文件**：`DrissionPage_example.py` · `email_register.py` · `apps/` · `deploy/`

**使用指南**：[packages/grok/grok-register/README.md](packages/grok/grok-register/README.md)

#### 30. grok2api - Grok API 转换服务

**功能**：将 Grok 服务的接口转换为标准 API 格式，支持多账号管理和 Token 池化。

**使用指南**：[packages/grok/grok2api/README.md](packages/grok/grok2api/README.md)

---

### 邮箱服务 (packages/email)

#### 31. cloudflare-temp-email - Cloudflare 临时邮箱服务

**功能**：基于 Cloudflare 免费服务构建的临时邮箱服务，支持邮件收发、附件处理等功能。

**使用指南**：[packages/email/cloudflare-temp-email/README.md](packages/email/cloudflare-temp-email/README.md)

#### 32. tempmail - 自托管临时邮箱服务

**功能**：自托管临时邮件服务平台，支持多域名池、用户自助提交域名、MX 自动验证与自动禁用、API Key 鉴权及 Web 管理后台。基于 Docker 部署，包含 PostgreSQL、PgBouncer、Redis、Postfix 等完整组件。

**主要文件**：`docker-compose.yml` · `api/` · `frontend/` · `sql/` · `.env.example`

**使用指南**：[packages/email/tempmail/README.md](packages/email/tempmail/README.md)

#### 33. ms-oauth2-api - 微软 OAuth2 邮件取件 API

**功能**：将微软 OAuth2 认证取件流程封装成一个简单的 API，部署在 Vercel 无服务器平台上。

**使用指南**：[packages/email/ms-oauth2-api/README.md](packages/email/ms-oauth2-api/README.md)

#### 34. hotmail-outlook-auto-register - Hotmail/Outlook 自动注册

**功能**：高级 Hotmail / Outlook 账号创建和自动化工具，支持验证码绕过、代理轮换、指纹伪装和逼真的人类行为模拟。

**使用指南**：[packages/email/hotmail-outlook-auto-register/README.md](packages/email/hotmail-outlook-auto-register/README.md)

#### 35. outlook-auto-register - Outlook 邮箱注册工具集

**功能**：基于 Outlook 邮箱 OAuth2 认证的批量自动注册工具集，支持多个目标平台共享同一套邮箱接码模块。

**使用指南**：[packages/email/outlook-auto-register/README.md](packages/email/outlook-auto-register/README.md)

---

### 通用工具 (packages/general)

#### 36. any-auto-register - 多平台账号自动注册工具

**功能**：多平台账号自动注册工具，支持 ChatGPT、Cursor、Kiro 等多个平台.

**主要文件**：`main.py` · `api/` · `core/` · `platforms/`

**使用指南**：[packages/general/any-auto-register/README.md](packages/general/any-auto-register/README.md)

#### 37. api-key-scraper - 多平台 API 密钥抓取工具

**功能**：多平台 API 密钥抓取工具，支持从多个来源自动化获取 OpenAI、Gemini、Claude 的 API 密钥.

**使用指南**：[packages/general/api-key-scraper/README.md](packages/general/api-key-scraper/README.md)

#### 38. mregister - ChatGPT 注册机 Web UI

**功能**：基于 FastAPI 的控制台，用来统一管理 chatgpt_register_v2 和 grok-register 两个注册脚本. 它把原本偏命令行的执行方式包装成可持久化、可排队、可下载结果、可通过 API 调用的任务系统.

**主要文件**：`web_console/` · `chatgpt_register_v2/` · `docker-compose.yml`

**使用指南**：[packages/general/mregister/README.md](packages/general/mregister/README.md)

#### 39. exa-free - Exa 免费使用工具

**功能**：Exa 免费使用工具，提供 Exa 相关服务的免费访问.

**使用指南**：[packages/general/exa-free/README.md](packages/general/exa-free/README.md)

#### 40. real-random-taxfree-address - 真实随机免税地址生成

**功能**：生成真实的美国随机免税地址，用于账号注册等场景.

**使用指南**：[packages/general/real-random-taxfree-address/README.md](packages/general/real-random-taxfree-address/README.md)

#### 41. gopay-plus-auto - Gopay+ 自动化工具

**功能**：Gopay+ 平台自动化操作工具，支持批量支付、充值及账户维护.

**使用指南**：[packages/general/gopay-plus-auto/README.md](packages/general/gopay-plus-auto/README.md)

---

## 快速开始

### 1. 克隆项目

```bash
# 克隆项目（含所有子模块）
git clone --recurse-submodules https://github.com/adminlove520/AI-Account-Toolkit.git
cd AI-Account-Toolkit

# 如果已克隆但未拉取子模块
git submodule update --init --recursive
```

### 2. 环境准备

```bash
# 安装指定项目的依赖
pip install -r <项目目录>/requirements.txt

# 或递归安装所有项目依赖
find . -name "requirements.txt" -not -path "*/node_modules/*" -exec pip install -r {} +
```

### 3. 子模块列表

本项目包含以下子模块（共 22 个）：

| 分类 | 子模块 | 说明 |
|------|--------|------|
| **OpenAI** | `packages/openai/ab-card/` | ChatGPT Business/Plus 自动开通 |
| | `packages/openai/chatgpt-creator/` | ChatGPT 账号创建工具 |
| | `packages/openai/openai-oauth/` | OpenAI OAuth 认证工具 |
| **Claude** | `packages/claude/claude-key-switch/` | Claude 密钥切换工具 |
| **Gemini** | `packages/gemini/gemini-balance-do/` | Gemini 余额查询工具 |
| **Codex** | `packages/codex/codex-lb/` | Codex 负载均衡工具 |
| | `packages/codex/codex-register/` | Codex 注册脚本 |
| | `packages/codex/codex-register-fix/` | Codex 注册修复版本 |
| **Cursor** | `packages/cursor/cursor-auto-register/` | Cursor 自动注册工具 |
| **Grok** | `packages/grok/grok-register/` | x.ai 注册批处理 |
| | `packages/grok/grok2api/` | Grok API 转换服务 |
| **Email** | `packages/email/cloudflare-temp-email/` | Cloudflare 临时邮箱服务 |
| | `packages/email/tempmail/` | 自托管临时邮箱服务 |
| | `packages/email/ms-oauth2-api/` | 微软 OAuth2 邮件取件 API |
| | `packages/email/hotmail-outlook-auto-register/` | Hotmail 自动注册 |
| | `packages/email/outlook-auto-register/` | Outlook 邮箱注册工具集 |
| **General** | `packages/general/any-auto-register/` | 多平台账号自动注册 |
| | `packages/general/api-key-scraper/` | 多平台 API 密钥抓取 |
| | `packages/general/mregister/` | ChatGPT 注册机 Web UI |
| | `packages/general/exa-free/` | Exa 免费使用工具 |
| | `packages/general/real-random-taxfree-address/` | 真实随机免税地址生成 |
| | `packages/general/gopay-plus-auto/` | Gopay+ 自动化工具 |

### 4. 运行项目

```bash
# 运行 GPT-team 完整流程
python GPT-team/gpt-team-new.py

# 运行 CPAtools 管理 Codex 账号
python CPAtools/manager.py --mgmt-key your-key --target 100

# 运行 OpenAI 账号池编排器
python openai_pool_orchestrator-V6/run.py

# 运行多平台账号自动注册工具
python packages/general/any-auto-register/main.py
```

---

## 注意事项

1. **安全性**：本工具集涉及账号管理，请注意保护好配置文件中的敏感信息
2. **合规性**：请遵守 OpenAI 等相关服务的使用条款，不要滥用工具
3. **网络环境**：部分功能可能需要稳定的网络环境或代理支持
4. **依赖管理**：不同项目可能有不同的依赖要求，请按需安装
5. **版本兼容**：确保使用兼容的 Python 版本（建议 Python 3.10+）
6. **子模块管理**：定期运行 `git submodule update --remote` 以获取最新功能

---

## 故障排除

| 问题 | 解决方案 |
|------|----------|
| 子模块克隆失败 (`not our ref`) | 运行 `git submodule update --init --force --remote` |
| 网络错误 | 检查网络连接和代理设置 |
| 依赖错误 | 确保已安装所有必要的依赖包 |
| 配置错误 | 仔细检查配置文件中的各项参数 |
| API 限制 | 注意 API 调用频率，避免触发限制 |

---

## 贡献指南

欢迎提交 PR 和 Issue！请查阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详细的贡献流程。

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=adminlove520/AI-Account-Toolkit&type=Date)](https://star-history.com/#adminlove520/AI-Account-Toolkit&Date)

---

## 免责声明

本工具集仅供学习和研究使用，使用本工具产生的一切后果由使用者自行承担。请遵守相关服务的使用条款，不要用于任何违法或不当用途。如有侵权，请及时联系我，我们会及时删除。

---

**License**: [MIT](LICENSE) | **更新日期**：2026-05-13 | **版本**：2.4.0
