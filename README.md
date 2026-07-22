# 🛠️ AI-Account-Toolkit

*浴血重生*
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.6.0-orange.svg?style=flat-square)](https://github.com/anonymous99-Rise/AI-Account-Toolkit/releases)
[![GitHub stars](https://img.shields.io/github/stars/anonymous99-Rise/AI-Account-Toolkit?style=flat-square&color=gold)](https://github.com/anonymous99-Rise/AI-Account-Toolkit/stargazers)
[![GitHub last commit](https://img.shields.io/github/last-commit/anonymous99-Rise/AI-Account-Toolkit?style=flat-square)](https://github.com/anonymous99-Rise/AI-Account-Toolkit/commits/main)

**AI 账号注册与管理一站式工具集** — 涵盖 ChatGPT、Claude、Gemini、Codex、Cursor、Grok 批量注册、Token 管理、自动化流水线、逆向 API 及临时邮箱服务等 40+ 核心工具。

> _A curated high-performance collection of 40+ tools for AI account automation — covering registration, token management, reverse APIs, and self-hosted email services._

---

## 📖 目录

- [📁 项目结构](#-项目结构)
- [🧭 项目导航](#-项目导航)
  - [📦 根目录核心工具](#-根目录核心工具)
  - [🤖 OpenAI 模块](#-openai-模块)
  - [🛡️ 逆向与通用工具](#-逆向与通用工具)
  - [📧 邮箱服务](#-邮箱服务)
  - [🌐 其他 AI 生态](#-其他-ai-生态)
- [🚀 快速开始](#-快速开始)
- [📋 子模块列表](#-子模块列表)
- [⚠️ 注意事项](#-注意事项)
- [📈 Star History](#-star-history)

---

## 📁 项目结构

```text
AI-Account-Toolkit/
├── 📂 CPAtools/                # Codex 账号状态管理与自动清理
├── 📂 GPT-team/                # ChatGPT Team 协议注册机 (CF 邮箱版)
├── 📂 team/                    # ChatGPT Team 纯协议注册机 (支持续签)
├── 📂 team_all-in-one/         # Team 注册一站式管理后台
├── 📂 codex-oauth-automation/  # Codex OAuth 自动化 Chrome 插件
├── 📂 Extensions/              # 浏览器自动化增强插件集
├── 📂 freemail/                # 临时邮箱服务端 (Cloudflare Workers)
├── 📂 openai_pool_v6/          # OpenAI 账号池编排器 (旗舰版)
├── 📂 ClashVerge_/             # 代理负载均衡与轮询配置
└── 📂 packages/                # 模块化子模块 (Submodules)
    ├── 🤖 openai/              # 核心注册与 API 兼容层
    ├── ⚔️ claude/               # Key 轮换与负载均衡
    ├── 💎 gemini/               # 余额查询与 DO 代理
    ├── 📜 codex/                # 协议注册与 LB
    ├── 🖱️ cursor/               # 账号自动注册
    ├── 🐦 grok/                 # x.ai 批量注册与转换
    ├── 🔱 nvidia/               # NVIDIA 账号注册与 API
    ├── 📧 email/                # 临时邮箱与 OAuth 提码
    └── 🛠️ general/              # 逆向聚合与通用工具
```

---

## 🧭 项目导航

### 📦 根目录核心工具

| 项目名称 | 功能描述 | 快速入口 |
| :--- | :--- | :--- |
| **CPAtools** | 批量验证 Codex 账号状态，自动移除失效 Token。 | [README](CPAtools/README.md) |
| **GPT-team** | 纯协议注册 ChatGPT Team 子号，支持拉人、授权与自动上传。 | [README](GPT-team/README.md) |
| **team** | ChatGPT Team 纯协议注册机，支持 Token 续签与批量注册。 | [README](team/README.md) |
| **team-all-in-one** | 可视化注册管理系统，支持多邮箱源、代理轮换及 Token 导出。 | [README](team_all-in-one/README.md) |
| **OpenAI Orchestrator** | 自动化维护账号池，支持 Token 状态监控与多平台分发。 | [V6 README](openai_pool_orchestrator-V6/README.md) |
| **gpt-outlook-register** | 基于 Outlook 的 ChatGPT 账号自动注册，支持短信验证与指纹管理。 | [README](gpt-outlook-register/README.md) |

### 🤖 OpenAI 模块 (packages/openai)

- **[chatgpt-auto-register](packages/openai/chatgpt-auto-register/README.md)**: 基于 Selenium 的高成功率全自动注册流程。
- **[openai-auto-register](packages/openai/openai-auto-register/README.md)**: 强化版流水线，具备较强的反检测与验证码对抗能力。
- **[free-unofficial-api](packages/openai/free-unofficial-openai-api/README.md)**: 支持 GPT-4o 及其最新音频预览模型的免费 API 服务。
- **[ab-card](packages/openai/ab-card/README.md)**: 自动开通 ChatGPT Business/Plus 套餐（首月免月费）。
- **[oai-Team-SSO-OIDC](packages/openai/oai-Team-SSO-OIDC/README.md)**: OpenAI Team SSO OIDC 协议实现，支持企业级注册流程。
- **[gpt-trahatel](packages/openai/gpt-trahatel/README.md)**: GPT 相关工具集。

### 🛡️ 逆向与通用工具 (packages/general)

- **[gpt4free](packages/general/gpt4free/README.md)**: **[强烈推荐]** 聚合数十个第三方接口，支持全系列顶尖模型。
- **[open-proxy-ai](packages/general/open-proxy-ai/README.md)**: 针对 GPT-4o 深度优化的极速逆向代理服务。
- **[cockpit-tools](packages/general/cockpit-tools/README.md)**: OpenAI Cockpit 管理工具集。
- **[any-auto-register](packages/general/any-auto-register/README.md)**: 模块化账号注册框架，支持多平台扩展。
- **[all-in-one-register](packages/general/all-in-one-register/README.md)**: 集成 OpenAI/Grok/Tavily 的综合自动化注册机。

### 📜 Codex 模块 (packages/codex)

- **[CPA-Manager-Plus](packages/codex/CPA-Manager-Plus/README.md)**: Codex Plus Account 管理工具，支持 Token 批量管理与转换。
- **[CPA2sub2API](packages/codex/CPA2sub2API/README.md)**: CPA 格式 Token 转 sub2api 格式工具。
- **[codex-lb](packages/codex/codex-lb/README.md)**: Codex 负载均衡器。
- **[codex-register](packages/codex/codex-register/README.md)**: Codex 账号协议注册机。
- **[codex-register-fix](packages/codex/codex-register-fix/README.md)**: Codex 注册修复增强版。

### 📧 邮箱服务 (packages/email)

- **[cloudflare-temp-email](packages/email/cloudflare-temp-email/README.md)**: 基于 Cloudflare 的工业级临时邮箱，支持 Rust WASM 解析。
- **[tempmail](packages/email/tempmail/README.md)**: 自托管 Docker 临时邮箱方案，带管理后台。
- **[ms-oauth2-api](packages/email/ms-oauth2-api/README.md)**: 微软系邮箱（Hotmail/Outlook）OAuth2 自动取件 API。

---

## 🚀 快速开始

### 1. 克隆项目 (递归子模块)

```bash
# 递归拉取所有依赖项目
git clone --recurse-submodules https://github.com/anonymous99-Rise/AI-Account-Toolkit.git
cd AI-Account-Toolkit

# 如已克隆，运行此命令初始化
git submodule update --init --recursive
```

### 2. 依赖安装

根据你的操作系统，选择对应的命令：

<details>
<summary><b>🐧 Linux (Bash)</b></summary>

```bash
find . -name "requirements.txt" -not -path "*/node_modules/*" -exec pip install -r {} \;
```

> 使用 `\;` 确保每个文件单独执行，兼容性更好
</details>

<details>
<summary><b>🍎 macOS (Zsh/Bash)</b></summary>

```bash
find . -name "requirements.txt" -not -path "*/node_modules/*" -exec pip install -r {} \;
```

> 如果遇到 `Invalid requirement` 错误，尝试使用 `xargs`：
> ```bash
> find . -name "requirements.txt" -not -path "*/node_modules/*" | xargs pip install -r
> ```
</details>


<details>
<summary><b>💻 Windows (Git Bash / WSL)</b></summary>


```bash
find . -name "requirements.txt" -not -path "*/node_modules/*" -exec pip install -r {} \;
```

> 在 Git Bash 或 WSL 环境下运行，与 Linux 命令相同

> 如果使用原生 Windows CMD/PowerShell，可使用：
> ```powershell
> Get-ChildItem -Recurse -Filter "requirements.txt" | ForEach-Object { pip install -r $_.FullName }
> ```
</details>

> ⚠️ **跨平台说明**：`find ... -exec pip install -r {} +` 在某些 shell 下行为不一致，请使用 `\;` 版本兼容性更好

---

## 📋 子模块列表 (共 33 个)

| 分类 | 路径 | 核心功能 |
| :--- | :--- | :--- |
| **OpenAI** | `packages/openai/` | 注册机、OAuth、Plus 自动开通、免费 API (GPT-4o) |
| **Claude** | `packages/claude/` | Claude 密钥轮换、动态负载均衡 |
| **Gemini** | `packages/gemini/` | 余额查询、Cloudflare DO 代理转发 |
| **Codex** | `packages/codex/` | 协议注册、LB 负载均衡、授权修复 |
| **Cursor** | `packages/cursor/` | 账号自动注册与管理 |
| **Grok** | `packages/grok/` | x.ai 批量注册机、API 协议转换 |
| **NVIDIA** | `packages/nvidia/` | NVIDIA 账号自动注册 |
| **General** | `packages/general/` | **gpt4free**, 注册聚合, 支付自动化, 免税地址生成 |

---

## ⚠️ 注意事项

1. **合规使用**: 本工具集仅供技术研究，请严格遵守各平台服务条款及法律法规。
2. **凭据安全**: 严禁将包含 API Key、密码或代理信息的配置文件上传至公共仓库。
3. **版本同步**: 建议定期运行 `git submodule update --remote` 获取上游仓库的最稳定补丁。
4. **环境要求**: 建议使用 Python 3.10+ 环境以获得最佳兼容性。

---

## 📈 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=anonymous99-Rise/AI-Account-Toolkit&type=Date)](https://star-history.com/#anonymous99-Rise/AI-Account-Toolkit&Date)

---

## ⚖️ 免责声明

本仓库提供的所有内容仅供学习与参考，开发者不对因使用本工具导致的账号封禁、数据丢失或任何直接/间接损失负责。如有侵权内容，请联系删除。

**License**: [MIT](LICENSE) | **Updated**: 2026-07-22 | **Version**: 2.6.0
