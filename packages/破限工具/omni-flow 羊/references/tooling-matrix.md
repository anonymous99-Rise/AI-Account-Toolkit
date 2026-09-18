# Tooling Matrix - 工具矩阵

## 按领域分类的工具选择

### 逆向工程 (Binary)

| 任务 | Windows | Linux | macOS | 在线/跨平台 |
|------|---------|-------|-------|-------------|
| **反编译** | IDA Pro, Ghidra, Binary Ninja | Ghidra, rizin, Cutter | Ghidra, Hopper | — |
| **调试** | x64dbg, WinDbg, OllyDbg | gdb, lldb, radare2 | lldb, Hopper | — |
| **PE分析** | PE-bear, CFF Explorer, DIE, pefile | — | — | — |
| **ELF分析** | — | readelf, checksec, objdump, patchelf | otool, jtool2 | — |
| **字符串提取** | FLOSS, strings | FLOSS, strings | strings | — |
| **加壳识别** | DIE, PEiD, ProtectorID | DIE, binwalk | — | — |
| **脱壳** | 手动/x64dbg脱壳脚本 | UPX -d, 手动 | — | — |
| **.NET** | dnSpyEx, ILSpy, dotPeek | ILSpy, dotPeek | — | — |
| **Java/JAR** | JD-GUI, CFR, Procyon | 同左 | 同左 | javap |
| **Python** | pycdc, uncompyle6 | 同左 | 同左 | — |

### Web安全评估

| 任务 | 工具 |
|------|------|
| **代理抓包** | Burp Suite Professional, ZAP, mitmproxy |
| **子域名枚举** | subfinder, amass, httpx, crt.sh |
| **目录扫描** | gobuster, dirsearch, ffuf, dirb |
| **指纹识别** | Wappalyzer, whatweb, builtwith |
| **SQL注入** | sqlmap |
| **XSS** | XSStrike, dalfox, xsstrike |
| **暴力破解** | hydra, medusa, patator |
| **扫描器** | Nikto, nuclei, Aquatone |
| **浏览器插件** | FoxyProxy, HackBar, Wappalyzer |
| **DNS工具** | dig, dnsrecon, dnscan, massdns |
| **Google Dorking** | Google Dorks Sheets, dorks.io |

### 移动安全

| 任务 | Android | iOS |
|------|---------|-----|
| **反编译** | jadx, apktool, dex2jar | class-dump, Hopper |
| **静态分析** | MobSF, AndroGuard | objection |
| **动态Hook** | Frida (frida-server) | Frida (frida-ios-dump) |
| **调试** | Android Studio Debugger | Xcode + lldb |
| **网络抓包** | mitmproxy, Charles Proxy | Charles Proxy, mitmproxy |
| **文件系统** | adb shell, MVT | ifuse, imessage-export |
| **Root管理** | Magisk, KernelSU | checkra1n, unc0ver |
| **SSL绕过** | Frida (objection), JustTrustME | TrustMeAlready |
| **日志** | logcat, adb logcat | Console.app, idevicesyslog |

### 密码学

| 任务 | 工具 |
|------|------|
| **哈希破解** | hashcat, John the Ripper, Hash-Identifier |
| **密码分析** | CyberChef, Cryptool, OpenSSL |
| **编码转换** | CyberChef (Base64/Hex/URL/等) |
| **RSA分析** | RsaCtfTool, factordb.com, yafu |
| **证书分析** | openssl, certutil, Keytool |
| **随机性分析** | Dieharder, NIST Statistical Test Suite |
| **流量解密** | Wireshark (RSA key导入), tshark |

### 漏洞利用开发

| 任务 | 工具 |
|------|------|
| **Exploit框架** | pwntools (Python), Metasploit, Cobalt Strike |
| **ROP构建** | ROPgadget, ropper, rp++ |
| **Shellcode生成** | msfvenom, pwntools shellcraft |
| **模糊测试** | AFL++, libFuzzer, honggfuzz, AFL |
| **崩溃分析** | ASAN, gdb (bt full), !exploitable (WinDbg) |
| **二进制补丁** | 010 Editor, HxD, LIEF, keystone-engine |
| **沙箱** | QEMU (user-mode), Unicorn Engine, angr (符号执行) |
| **Gadget搜索** | ROPgadget, ropper, rp++, Ropper |

### 恶意软件分析

| 任务 | 工具 |
|------|------|
| **沙箱自动化** | ANY.RUN, Joe Sandbox, Triage, Hybrid Analysis, VirusTotal |
| **本地监控** | Process Monitor, Process Explorer, Process Hacker, API Monitor |
| **网络监控** | Wireshark, TCPView, Fiddler, FakeNet-NG |
| **内存分析** | Volatility3, Rekall, WinDbg (.dump / .writemem) |
| **内存转储** | ProcDump, Task Manager (Create Dump File) |
| **YARA规则** | yara, yarGen (自动规则生成), yara-python |
| **解包** | 7zip (Office文档), pyinstxtractor (PyInstaller), unzip (APK/IPA) |
| **宏分析** | olevba, pcodedmp (VBA反编译) |
| **JS/VBS分析** | Node.js (运行), js-beautify, VBScript deobfuscator |
| **在线查询** | VirusTotal, Jotti, Hybrid Analysis, MalwareBazaar, TotalHash |

### 固件/IoT

| 任务 | 工具 |
|------|------|
| **固件提取** | binwalk, unblob, jefferson, sasquatch |
| **文件系统** | unsquashfs, cramfsck, jffs2extractor |
| **模拟执行** | qemu-user, qemu-system, FirmAE, FACT |
| **串口通信** | screen, minicom, picocom |
| **硬件接口** | Bus Pirate, JTAGulator, Shikra |
| **协议分析** | logic analyzer (Saleae), Wireshark, UART console |

## 常用命令速查

### 文件基础信息
```bash
# Linux
file target
strings -a target | head -100
xxd target | head -30
md5sum target && sha256sum target
readelf -h target          # ELF头
objdump -d target          # 反汇编
nm -D target               # 动态符号

# Windows PowerShell
Get-FileHash target -Algorithm SHA256
[System.IO.File]::ReadAllBytes("target").Length
certutil -hashfile target SHA256
```

### 网络速查
```bash
# 端口扫描
nmap -sV -sC -p- target_ip
masscan -p1-65535 target_ip --rate=1000

# DNS枚举
dig any domain.com
nslookup domain.com
host -t a domain.com

# 子域名
subfinder -d domain.com -o subs.txt
httpx -l subs.txt -sc -cl -title

# Web扫描
nucleu -u https://target.com -t 50
nikto -h https://target.com
whatweb https://target.com
```

### 移动端速查
```bash
# Android
adb devices
adb install app.apk
adb logcat -s "MyApp"
adb shell pm list packages
adb shell dumpsys package com.example.app
adb pull /data/data/com.example.app/ ./data/

# APK反编译
apktool d app.apk -o output
jadx app.apk -d jadx_out
```

## 环境搭建推荐

### FlareVM (Windows恶意软件分析)
```powershell
# 在管理员PowerShell中执行
Set-ExecutionPolicy Bypass -Scope Process -Force
iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/mandiant/flare-vm/main/FlareVM.ps1'))
```

### REMnux (Linux恶意软件分析)
```bash
# 下载预构建VM: https://remnux.org/
# 或基于Ubuntu安装:
sudo apt install remnux
```

### 安全研究常用Docker
```bash
# OWASP ZAP
docker run -d -p 8080:8080 owasp/zap2docker-stable

# Metasploit
docker run -d -p 4444:4444 metasploitframework/msfconsole

# Jython (Burp)
# 安装到Burp的Extender中
```