# Network Analysis - 网络流量分析工作流

## 完整流程图

```
流量样本接收 (pcap/ng/日志)
    │
    ▼
┌─────────────┐
│  数据预处理   │ ◄── 清洗和格式化
└──────┬───────┘
       │
       ├─→ 格式转换 (pcapng→pcap, hccapx提取)
       ├─→ 流量过滤 (按IP/端口/协议)
       ├─→ 时间范围裁剪
       └─→ 会话提取 (TCP流重组)
       │
       ▼
┌─────────────┐
│  协议识别     │ ◄── 确定使用的协议栈
└──────┬───────┘
       │
       ├─→ 应用层协议 (HTTP/DNS/TLS/自定义)
       ├─→ 传输层特征 (TCP flags, UDP模式)
       ├─→ 加密检测 (TLS握手分析)
       └─→ 隧道检测 (DNS隧道/ICMP隧道)
       │
       ▼
┌─────────────┐
│  内容分析     │ ◄── 提取有效载荷
└──────┬───────┘
       │
       ├─→ HTTP请求/响应完整重构
       ├─→ DNS查询/响应解析
       ├─→ TLS证书/SNI/JA3指纹
       ├─→ 二进制文件提取 (从HTTP下载)
       ├─→ 凭据提取 (Basic Auth/POST参数/Cookie)
       └─→ 自定义协议字段解析
       │
       ▼
┌─────────────┐
│  行为分析     │ ◄── 识别恶意行为模式
└──────┬───────┘
       │
       ├─→ C2通信模式 (心跳/beacon/指令下发)
       ├─→ 数据外传 (文件上传/批量数据发送)
       ├─→ 横向移动 (SMB/RDP/SSH扫描)
       ├─→ 侦察活动 (端口扫描/DNS枚举)
       └─→ 命令与控制 (远程命令执行)
       │
       ▼
┌─────────────┐
│  IOC提取      │ ◄── 提取可行动的情报
└──────┬───────┘
       │
       ├─→ 恶意IP/域名/URL
       ├─→ 恶意文件哈希 (下载的payload)
       ├─→ 攻击者基础设施特征
       └─→ 时间线重建
       │
       ▼
┌─────────────┐
│  报告         │
└─────────────┘
```

---

## Phase 1: Wireshark使用指南

### 1.1 常用显示过滤器

```wireshark
# 基础过滤
ip.addr == 192.168.1.1          # 特定IP
tcp.port == 8080                 # 特定端口
http                             # HTTP流量
dns                              # DNS流量
tls                              # TLS流量

# 组合条件
ip.src == 10.0.0.5 && ip.dst != 10.0.0.0/8  # 内网到外网
http.request.method == "POST"               # POST请求
dns.qry.name contains "evil"                # 包含特定域名的DNS
tls.handshake.extensions_server_name contains "c2"  # SNI包含c2

# 排除噪声
!arp && !mdns && !ssdp && !llmnr && !nbns   # 排除局域网广播
!icmp && icmp.type == 8                     # 只看ping请求

# 高级过滤
tcp.flags.syn == 1 && tcp.flags.ack == 0    # SYN包(新连接)
http.response.code >= 400                    # HTTP错误响应
frame.len > 1500                              # 大包(Jumbo帧?)
tcp.analysis.retransmission                   # 重传包
```

### 1.2 统计功能

```
菜单 → Statistics:

Conversations:
  - 查看所有通信对(IP/ TCP/UDP)
  - 按字节数排序 → 找到数据量最大的会话
  - 可能是C2通道或数据外传

Endpoints:
  - 所有参与通信的端点
  - 发现异常的外部IP

HTTP:
  - 请求统计
  - 包大小分布
  - 负载分布

DNS:
  - 查询类型分布
  - 最常查询的域名
  - 异常长域名(DNS隧道)

IO Graphs:
  - 流量时间图
  - 发现周期性通信(beacon)
  - 突发流量(数据外传)

```

## Phase 2: 协议深度分析

### 2.1 HTTP/HTTPS分析

```bash
# tshark命令行提取
# 提取所有HTTP请求URL
tshark -r capture.pcap -Y "http.request" -T fields -e http.host -e http.request.uri -e http.request.method

# 提取POST数据
tshark -r capture.pcap -Y "http.request.method == POST" -T fields -e http.file_data -e http.content_type

# 提取下载的文件
tshark -r capture.pcap -z "follow,tcp,ascii,<stream_number>" > extracted.txt
# 或使用Wireshark: 右键 → Follow → TCP Stream → Save as

# 导出HTTP对象
Wireshark: File → Export Objects → HTTP
# 自动保存所有下载的文件
```

### 2.2 DNS分析

```bash
# DNS查询提取
tshark -r capture.pcap -Y "dns.qr == 0" -T fields -e dns.qry.name -e dns.qry.type -e ip.dst

# DNS隧道检测指标:
# 1. 子域名请求数异常多 (>100/min)
# 2. 子域名长度异常长 (>50字符)
# 3. 子域名使用随机字符集 (高熵值)
# 4. TXT记录请求 (用于数据传输)

# 使用dnscat2-extractor或DNS隧道检测工具
```

### 2.3 TLS分析

```bash
# TLS握手信息
tshark -r capture.pcap -Y "tls.handshake.type == 1" -T fields -e tls.handshake.extensions_server_name -e ip.dst -e tls.handshake.ciphersuite

# JA3指纹 (客户端指纹识别)
# 安装: https://github.com/salesforce/ja3
ja3 -r capture.pcap

# 常见JA3指纹:
# Chrome: <chrome-specific-hash>
# Python requests: <python-requests-hash>
# curl: <curl-hash>
# 自定义工具: <unique-hash> ← 可疑!
```

### 2.4 自定义/未知协议逆向

```
步骤:
1. 提取完整的TCP/UDP流 (Follow Stream)
2. 观察数据模式:
   - 固定头部? (Magic bytes / Length field)
   - 分隔符? (\x00, \n, |, comma)
   - 编码方式? (ASCII hex, Base64, binary)
3. 寻找重复结构:
   - 长度字段位置
   - 类型/命令标识
   - 校验和位置
4. 对比多个数据包找变化部分
5. 用Python写解析器验证假设
```

## Phase 3: 恶意行为检测

### 3.1 Beacon/C2检测

```
Beacon特征:
  - 固定间隔的心跳包 (如每60秒一次)
  - 心跳包大小相似
  - 心跳期间无其他通信
  - 快速响应 (服务器→客户端数据量小)

检测方法:
  IO Graphs → 设置过滤器为目标IP → 观察周期性
  Statistics → I/O Graph → 可视化时间模式

计算beacon间隔:
  tshark -r pcap -Y "ip.addr == C2_IP" -T fields -e frame.time_epoch |
  python3 -c "
import sys, time
times = [float(l.strip()) for l in sys.stdin if l.strip()]
intervals = [times[i+1]-times[i] for i in range(len(times)-1)]
print(f'Avg interval: {sum(intervals)/len(intervals):.1f}s')
print(f'Min: {min(intervals):.1f}s, Max: {max(intervals):.1f}s')
"
```

### 3.2 数据外传检测

```
特征:
  - 大量数据向外部IP传输
  - 非标准端口的大流量
  - 加密流量在非正常时段
  - POST请求体异常大

检测:
  Conversations → 按 Bytes → A列排序
  关注出站流量大的外部IP
```

### 3.3 凭据提取

```bash
# Basic Authentication
tshark -r capture.pcap -Y "http.authorization" -T fields -e http.authorization

# Cookie中的Session Token
tshark -r capture.pcap -Y "http.cookie" -T fields -e http.cookie

# FTP登录
tshark -r capture.pcap -Y "ftp.request.command == USER || ftp.request.command == PASS" -T fields -e ftp.request.arg

# Telnet (明文!)
tshark -r capture.pcap -Y "telnet" -z "follow,telnet,ascii,<stream>"

# NTLM Hashes (可离线破解)
tshark -r capture.pcap -Y "ntlmssp" -T fields -e ntlmssp.auth.user -e ntlmssp.auth.ntlmresp
```

## Phase 4: 文件提取与还原

```bash
# 方法1: Wireshark导出
File → Export Objects → HTTP/DNS/SMB/CoAP

# 方法2: tshark + 手动重组
# 找到包含文件的TCP流编号
tshark -r capture.pcap -z "follow,tcp,raw,<stream_num>" > raw.bin

# 方法3: tcpextract (自动)
pip install tcpextract
tcpextract -f capture.pcap -o output_dir/

# 方法4: NetworkMiner (GUI, Windows)
# 自动提取文件、图片、证书等

# 提取后处理
file extracted_file
strings extracted_file | head -20
sha256sum extracted_file
# 上传到VirusTotal检查
```

## 报告模板

```markdown
# 网络流量分析报告

## 样本信息
- 文件名: ...
- 大小: ...
- 时间范围: YYYY-MM-DD HH:MM to YYYY-MM-DD HH:MM
- 抓包接口: ...

## 统计概览
| 指标 | 数值 |
|------|------|
| 总包数 | ... |
| 总大小 | ... |
| 协议分布 | TCP: X%, UDP: Y%, ... |
| 唯一IP数 | ... |
| 外部通信IP数 | ... |

## 关键发现
### 发现 #1: [标题]
**类型**: C2通信 / 数据外传 / 凭据泄露 / ...
**严重程度**: Critical / High / Medium

**描述**: ...

**证据**:
- 目标IP: ...
- 协议: ...
- 数据量: ...
- 时间模式: ...

**IOC**:
- IP: ...
- 域名: ...
- 文件哈希: ...

## 完整IOC列表
[所有提取的IOC]

## 时间线
[T1] ... - 首次通信
[T2] ... - C2建立
[T3] ... - 数据外传开始
...
```