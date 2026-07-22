# 📜 Changelog

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
- 子模块总数从 32 个增加到 33 个

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
