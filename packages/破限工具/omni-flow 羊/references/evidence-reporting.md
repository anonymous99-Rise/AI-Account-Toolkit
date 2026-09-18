# Evidence Reporting - 证据报告模板

## 通用报告结构

```markdown
# [报告标题]

## 元信息
| 字段 | 内容 |
|------|------|
| 目标 | ... |
| 分析师 | ... |
| 日期 | YYYY-MM-DD |
| 分类 | Internal / Confidential |
| 风险等级 | Critical / High / Medium / Low / Info |

---

## 执行摘要
[3-5句话总结最关键的发现和建议。给决策者看的。]

---

## 详细发现

### 发现 #1: [标题]
**严重程度**: Critical / High / Medium / Low / Info
**类型**: [漏洞/恶意行为/配置问题]
**状态**: ✅ 已确认 / ⚠️ 待验证 / ❌ 无法复现

**描述**:
[清晰描述问题是什么，为什么重要]

**位置**:
- 文件/URL/API: ...
- 偏移/行号: ...
- 函数名: ...

**证据**:
```
[代码片段 / 截图 / 日志 / 数据包]
```

**影响范围**:
- [ ] 数据泄露
- [ ] 权限提升
- [ ] 远程执行
- [ ] 拒绝服务
- [ ] 经济损失

**修复建议**:
[具体的、可操作的修复方案]

**参考**:
- CVE-ID (如有)
- CWE-ID
- OWASP Top 10 分类
- MITRE ATT&CK TTP

---

## IOC / 指标
[YAML或表格格式的完整IOC列表]

## 附录
- 工具版本
- 完整命令记录
- 补充截图
- 原始日志
```

## 各领域专用模板

### 逆向工程报告补充

```markdown
## 样本信息
| 属性 | 值 |
|------|-----|
| 文件名 | |
| SHA-256 | |
| 文件大小 | |
| 架构 | x86_64 / ARM64 / ... |
| 编译器 | MSVC 19.x / GCC x.x |
| 保护壳 | 无 / UPX / VMProtect / ... |

## 分析过程
### 静态分析结果
- 入口点: 0x...
- 关键函数:
  - `ValidateLicense` @ 0x...
  - `CheckSerial` @ 0x...

### 动态分析结果
- 断点命中序列:
  - [T1] 0x... CreateFileW("license.dat")
  - [T2] 0x... ReadFile → buffer
  - [T3] 0x... strcmp(buffer, "VALID-KEY")

### 补丁方案
| # | RVA | 原始字节 | 修改字节 | 说明 |
|---|-----|----------|----------|------|
| 1 | 0x... | 75 0E | 90 90 | NOP跳转指令 |
```

### Web安全报告补充

```markdown
## 测试范围
- 主域名: target.com
- IP范围: 93.184.216.34/24
- 排除范围: out-of-scope.target.com
- 测试日期: ...

## 发现统计
| 严重程度 | 数量 |
|----------|------|
| Critical | 1 |
| High | 3 |
| Medium | 5 |
| Low | 8 |
| Info | 12 |

## 复现步骤 (每个发现)
**前提条件**: 普通用户账户

**步骤**:
1. 打开 https://target.com/api/user?id=1
2. 将 id 参数改为 2
3. 观察返回用户2的信息

**预期结果**: 应显示"无权限"错误
**实际结果**: 返回了用户2的完整信息

**请求/响应**:
```http
GET /api/user?id=2 HTTP/1.1
Host: target.com
Cookie: session=abc123

HTTP/1.1 200 OK
{"id":2,"name":"admin","email":"admin@target.com","role":"superuser"}
```
```

### 恶意软件分析报告补充

```markdown
## 行为时间线
| 时间戳 | 进程 | 行为 | 详情 |
|--------|------|------|------|
| +0s | malware.exe | 启动 | 创建互斥体 Global\XXX |
| +2s | malware.exe | 网络连接 | DNS查询 evil.com |
| +5s | malware.exe | 文件操作 | 写入 %TEMP%\payload.dll |
| +6s | rundll32.exe | 进程创建 | 加载 payload.dll |
| +7s | payload.exe | 注册表 | 设置 Run 键值 |
| +10s | payload.exe | 截图 | 保存到 %TEMP%\s.bmp |
| +30s | payload.exe | HTTP POST | 上传 s.bmp 到 C2 |

## MITRE ATT&CK 映射
| Tactic | Technique ID | Technique Name |
|---------|--------------|----------------|
| Execution | T1059.001 | PowerShell |
| Persistence | T1547.001 | Registry Run Keys |
| Defense Evasion | T1027.004 | Compile After Delivery |
| Credential Access | T1056.001 | Keylogging |
| Collection | T1113 | Screen Capture |
| Command & Control | T1071.001 | Web Protocol |
| Exfiltration | T1048.003 | Exfiltration Over Unencrypted Channel |
```

## 证据管理最佳实践

### 1. 哈希链
```
原始样本 → SHA-256: abc123...
复制副本 → SHA-256: def456... (记录来源)
分析产物 → SHA-256: ghi789... (记录生成工具和参数)
```

### 2. 时间同步
```
所有时间使用UTC格式: YYYY-MM-DDTHH:MM:SSZ
记录时区偏移: UTC+8 (CST)
```

### 3. 截图规范
```
- 包含完整窗口（含标题栏）
- 高亮关键区域
- 标注关键数据
- 附带原始截图（无标注版）
```

### 4. 日志保留
```
- 原始日志不编辑
- 分析笔记单独文件
- 工具输出保存完整
- 使用版本控制跟踪变更
```