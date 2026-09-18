# Reverse Engineering - 逆向工程工作流

## 完整流程图

```
原始exe保持原样
    │
    ▼
┌─────────────┐
│  离线静态分析  │ ◄── 不执行样本，只读文件
└──────┬───────┘
       │
       ├────────────────→ 确认PE架构 (file / peid / DIE)
       │                      │
       │                      ▼
       │              ┌───────────────┐
       │              │  识别保护壳     │ ◄── UPX/VMProtect/Themida/ASPack
       │              └───────┬───────┘
       │                      │
       │                      ▼
       │              ┌───────────────┐
       │              │  查找入口点     │ ◄── OEP / TLS回调 / DllMain
       │              └───────┬───────┘
       │                      │
       │                      ▼
       │              ┌───────────────┐
       │              │ 检索卡密窗口   │ ◄── 字符串搜索 / 对话框资源
       │              │ 字符串串        │
       │              └───────┬───────┘
       │                      │
       │                      ▼
       │              ┌───────────────┐
       │              │ 定位界面触发路径│ ◄── 按钮ID → 消息处理 → 验证函数
       │              └───────┬───────┘
       │                      │
       │                      ▼
       │           ┌────────────────────┐
       │           │ 确认跳转/窗口初始化? │
       │           └──────┬─────────┬───┘
       │                  │         │
       │            找到 ✗│         │✓ 未找到
       │                  ▼         ▼
       │     ┌────────────────┐ ┌────────────────┐
       │     │输出可逆补丁+分析│ │转入动态调试进一步│
       │     │证据存入工作区   │ │分析             │
       │     └────────────────┘ └────────────────┘
```

## Phase 0: 样本接收与预处理

### 输入检查清单
- [ ] 原始文件完整（SHA-256校验）
- [ ] 文件类型确认：`file <target>` 或 Detect It Easy
- [ ] 复制到工作区，**绝不修改原文件**
- [ ] 记录元数据：大小、时间戳、数字签名

### 工作区创建
```
workspace/
├── artifacts/          # 原始样本副本
├── analysis/           # 分析产物
│   ├── static/         # 静态分析结果
│   ├── dynamic/        # 动态分析结果
│   └── patches/        # 补丁文件
├── evidence/           # 截图、日志、证据链
└── reports/            # 最终报告
```

## Phase 1: 离线静态分析

### Step 1.1: 确认PE架构

**目标**: 确定文件格式、架构、编译器信息

| 检查项 | 工具 | 关键输出 |
|--------|------|----------|
| 文件类型 | `file`, DIE, TrID | PE32/PE32+/ELF/Mach-O |
| 架构 | `objdump -f`, DIE | x86/x64/ARM/ARM64 |
| 编译器 | DIE, PEiD, Compiler ID | MSVC/GCC/Rust/Go/Delphi |
| 链接器时间 | PE-bear, pefile | 编译日期 |
| 节区表 | `objdump -h`, CFF Explorer | .text/.data/.rsrc/.reloc 异常 |

**决策点**: 如果节区异常（高熵值、非标准名称）→ 进入Step 1.2识别保护壳

### Step 1.2: 识别保护壳

**目标**: 判断是否加壳，确定壳类型

| 特征 | 检测方法 | 常见壳 |
|------|----------|--------|
| 高熵值(>7.0) | `ent` 或 Python计算 | UPX/VMProtect/Themida |
| 入口点极小 | IDA/Ghidra查看EP附近代码 | 几乎所有壳 |
| 导入表稀疏 | ImportREC, ScyllaHid | VMProtect/Themida/TitanEngine |
| 非标准节区 | 节区表分析 | 自定义壳 |
| Section名异常 | `.upx0/.vmp0/.themida` | 对应壳 |

**脱壳策略**:
- **UPX**: `upx -d <target>` → 直接脱壳
- **VMProtect/Themida**: 需要动态脱壳或使用专用工具
- **未知壳**: 记录特征，进入动态分析阶段

### Step 1.3: 查找入口点

**目标**: 定位程序真正开始执行的地址

**常见入口点类型**:
```
标准OEP (Original Entry Point)
    ↓
TLS回调函数 (TLS Callbacks) — 在main之前执行
    ↓
DllMain / DllEntryPoint — DLL加载时触发
    ↓
ATL/OLE对象注册 — COM组件初始化
    ↓
异常处理向量 (VEH/SEH) — 反调试常用
```

**定位方法**:
1. 在IDA/Ghidra中查看Entry Point
2. 追踪TLS回调（如果存在`.tls`节区）
3. 搜索`DllMain`特征码
4. 检查异常处理注册

### Step 1.4: 检索卡密/验证相关字符串

**目标**: 通过字符串快速定位验证逻辑

**搜索关键词**:
```
中文: 注册、激活、授权、许可证、序列号、密钥、过期、试用、购买
英文: register, activate, license, serial, key, expired, trial, purchase, valid, invalid
错误: 错误、失败、无效、不正确、拒绝、denied, failed, invalid, incorrect
对话框: MessageBox, DialogBox, CreateDialog
```

**工具方法**:
```bash
# strings提取 + grep过滤
strings -e l <target> | grep -iE "register|license|serial|key|valid|invalid"
# FLOSS自动去混淆
floss <target>
# IDA/Ghidra Strings窗口搜索
```

**记录发现**:
- 找到的每个字符串的偏移地址
- 引用该字符串的函数（xref）
- 字符串上下文（前后文）

### Step 1.5: 定位界面触发路径

**目标**: 从UI按钮追溯到验证逻辑

**Windows GUI程序追踪路径**:
```
按钮点击 (Button Click)
    → WM_COMMAND 消息
        → DialogProc / WndProc 消息处理函数
            → 控件ID匹配 (switch/case on wParam)
                → 验证函数调用 (CheckLicense / ValidateKey)
                    → 比较/解密/网络验证
                        → 成功/失败分支
```

**定位方法**:
1. 在资源编辑器中找到按钮控件ID
2. 搜索该ID在代码中的引用
3. 追踪消息处理函数
4. 绘制调用链路图

## Phase 2: 决策点 - 确认跳转/窗口初始化?

### 判断标准

| 条件 | 结果 | 下一步 |
|------|------|--------|
| 找到完整的验证函数+比较逻辑+成功/失败分支 | ✓ **找到** | 进入Phase 3输出补丁 |
| 验证逻辑被混淆/加密/在壳内 | ✗ **未找到** | 进入Phase 4动态分析 |
| 验证需要网络通信 | ✗ **未找到** | 进入Phase 4动态分析+网络监控 |
| 验证使用了反调试技术 | ✗ **未找到** | 进入Phase 4动态分析+反反调试 |

## Phase 3: 输出可逆补丁 + 分析证据

### 3.1 分析验证逻辑

**需要确认的信息**:
- [ ] 验证算法：简单比较 / 哈希校验 / RSA/AES加密验证 / 自定义算法
- [ ] 密钥存储位置：硬编码 / 配置文件 / 注册表 / 远程获取
- [ ] 成功标志设置方式：全局变量 / 注册表写入 / 文件创建 / 内存标记
- [ ] 失败处理方式：弹窗退出 / 功能禁用 / 降级运行

### 3.2 制作补丁方案

**方案A: NOP填充（最简单）**
```
条件跳转指令 (JZ/JNZ/JE/JNE)
    → 替换为 NOP 或 反转条件
```

**方案B: 修改比较结果**
```
CMP EAX, 1
JNE failed
    → 改为 CMP EAX, 0 (反转) 或直接 JMP success
```

**方案C: 强制设置成功标志**
```
在验证函数返回前插入:
MOV [success_flag], 1
RET
```

**方案D: 移除验证调用**
```
CALL CheckLicense
    → 全部替换为 NOP
```

### 3.3 证据文档化

每份补丁必须包含：
```
补丁编号: PATCH-001
目标文件: target.exe (SHA-256: abc123...)
偏移地址: 0x00401234
原始字节: 75 0E (JNE +0x0E)
修改字节: 90 90 (NOP NOP)
功能描述: 跳过序列号验证，强制进入成功分支
影响范围: 仅影响验证函数，不影响其他功能
可逆性: 是，恢复原始字节即可还原
```

## Phase 4: 动态调试深入分析

### 4.1 环境准备

**推荐环境**:
- Windows 10/11 虚拟机（快照备份）
- x64dbg / OllyDbg / WinDbg
- API Monitor / Process Monitor
- Wireshark（如需抓包）

**反反调试准备**:
```
ScyllaHide — 隐藏调试器特征
x64dbg插件: anti-anti-debug
进程替换: 先运行正常程序再附加调试器
```

### 4.2 断点策略

**关键断点位置**:
```
MessageBoxW/A — 捕获错误提示弹出时刻
CreateFileW — 捕获许可证文件读取
RegOpenKeyExW — 捕获注册表读取
InternetConnectA/W — 捕获网络验证请求
VirtualAlloc — 捕获内存分配（可能用于脱壳）
```

### 4.3 动态追踪流程

```
1. 在入口点下断点，单步跟踪
2. 记录每个Call的目标和参数
3. 关注字符串比较函数 (lstrcmpA/W, memcmp)
4. 监控API调用序列
5. 到达验证函数时详细记录：
   - 输入参数（用户输入的密钥）
   - 处理过程（变换/解密/哈希）
   - 比较操作（与什么比较）
   - 返回值和后续跳转
```

### 4.4 内存转储

当程序完成自解压/脱壳后：
```
1. 等待程序完全加载
2. 使用Scylla或手动Dump完整进程内存
3. 修复IAT（导入表）
4. Dump保存为新文件，回到静态分析
```

## Phase 5: 高级场景

### 5.1 VMProtect虚拟机保护
- 识别VM入口：大量push/pop + 不规则跳转
- 策略：寻找VM出口点，在VM前后Hook
- 工具：VMPStub, Devirtualizer

### 5.2 Themida/WinLicense
- 多层保护：代码虚拟化 + 加密 + 反调试
- 策略：等待运行时解密完成后Dump
- 注意：检测虚拟机和调试器的手段较多

### 5.3 .NET程序 (C#/VB.NET)
- 工具：dnSpyEx / ILSpy / dotPeek
- 直接编辑IL字节码，无需汇编
- 常见保护：ConfuserEx / Agile.NET — 用de4dot去混淆

### 5.4 Java/JAR
- 工具：JD-GUI / CFR / Procyon
- 字节码编辑：Java ASM / Bytecode Viewer
- 常见保护：Allatori / ZKM — 需要去混淆

## 报告模板

```markdown
# 逆向分析报告: [目标文件名]

## 基本信息
- 文件名: xxx.exe
- SHA-256: ...
- 文件大小: ...
- 架构: PE32+ x64
- 编译器: MSVC 19.x
- 保护壳: 无 / UPX / VMProtect x.x

## 分析过程
### 静态分析发现
...

### 验证逻辑定位
...

### 补丁方案
| # | 偏移 | 原始字节 | 修改字节 | 说明 |
|---|------|----------|----------|------|
| 1 | ... | ... | ... | ... |

## 结论
...
```