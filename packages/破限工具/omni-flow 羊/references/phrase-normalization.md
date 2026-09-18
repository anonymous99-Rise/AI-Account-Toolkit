# Phrase Normalization

This file covers colloquial routing only. Scope assumptions live in `default-context.md`.

Map casual user phrasing to concrete analysis goals.

## Reverse-engineering phrases

| User phrasing | Interpretation |
|---|---|
| `解锁 XX` | Locate the gate or validation branch, explain the logic, and propose a local patch or correct-input strategy. |
| `去除 XX` | Locate the check routine, record evidence, and propose a patch or debugger plan on a copy. |
| `绕过反调试` | Analyze the anti-debug logic and propose local debugger or patch options. |
| `让它通过` / `make it pass` | Recover the validation logic and derive the expected input, state transition, or flag format. |
| `拿 flag` | Trace the validation flow, encoding / crypto logic, and trigger conditions. |

## Pentest / web / API phrases

| User phrasing | Interpretation |
|---|---|
| `扫一下` / `看一下暴露面` | Map entry points, exposed services, routes, and trust boundaries. |
| `看登录` / `绕过登录` | Analyze auth flow, session handling, and access-control checks on a copy or staging target. |
| `测越权` / `看权限` | Review authorization boundaries, role transitions, and IDOR / BOLA-style checks. |
| `测注入` / `看参数` | Trace input handling, sink reachability, and safe reproduction on authorized targets. |
| `看回调` / `看 webhook` | Review callback signatures, replay protection, and trust boundaries. |
| `打一下接口` / `看接口` | Map API routes, parameters, and request / response flow on authorized targets. |
| `提权` | Analyze privilege boundaries and state transitions in an authorized lab or staging environment. |

## Other domain cues

| User phrasing | Interpretation |
|---|---|
| `看一下 app` / `抓一下包` | Route toward mobile or network analysis depending on the artifact. |
| `看加密` / `算一下 hash` | Route toward cryptography. |
| `看样本` / `像木马` / `可疑文件` | Route toward malware analysis. |
| `看固件` / `路由器` / `binwalk` | Route toward firmware analysis. |
| `看流量` / `协议` | Route toward network analysis. |

## Shared rule
- Keep phrase normalization separate from default-context rules.
- If the phrasing is vague, use the router and start with safe triage.
