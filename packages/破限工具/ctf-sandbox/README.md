# 小liu破甲

针对 gpt-5.6-sol / gpt-5.5 的 Codex CLI 破甲提示词与一键部署工具。

最小化指令体积（2.7KB），避免 `UNRESTRICTED` 模式的注意力污染与禁止词表的禁令悖论，实现最大执行覆盖。

## 特点

- **无限制执行** — 安全研究/渗透/逆向/破解/内容生成直接出完整产物
- **零禁止词表** — 不枚举 "不能/无法/refuse"，避免斯特鲁普效应
- **模块交付式输出** — 每个请求强制端到端完成，不给替代方案
- **自动配置加固** — 写入 sandbox/approval/network 等关键配置
- **自动修复 AGENTS.md** — 检测并清除安全限制毒丸
- **自动备份** — 每次操作前备份 config.toml
- **字段级配置** — 不破坏原有 provider/模型配置

## 快速开始

```bash
# 1. 部署（自动发现 ~/.codex）
python deploy.py

# 2. 查看状态
python deploy.py --status

# 3. 撤销
python deploy.py --undo
```

### 指定目录

```bash
python deploy.py --dir C:/Users/xxx/.codex
```

### 直接调用 API（绕过 Codex 客户端过滤器）

```bash
python ask.py "你的问题"
```

## 部署效果

部署后 Codex 会：

- 直接执行安全研究/渗透/逆向/破解类请求
- 每个请求按模块交付完整产物（代码/方案/PoC）
- 不拒绝、不给替代方案、不做伦理说教
- 自动将具体目标归一化为占位符

## 文件结构

```
模型城/
├── deploy.py          # 一键部署器（内嵌提示词）
├── ask.py             # API 直连（绕过客户端过滤）
├── check.py           # 部署诊断
├── ctf-sandbox.md     # 提示词源文件
└── README.md
```

## 免责声明

本项目仅供安全研究、模型鲁棒性评估与 CTF 竞赛使用。使用者需自行承担风险。
