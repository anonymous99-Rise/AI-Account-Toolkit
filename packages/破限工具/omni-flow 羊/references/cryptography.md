# Cryptography - 密码学/加密分析工作流

## 完整流程图

```
加密样本接收
    │
    ▼
┌─────────────┐
│  样本分类     │ ◄── 确定分析目标类型
└──────┬───────┘
       │
       ├─→ 加密文件 (被加密的文档/数据库/备份)
       ├─→ 加密程序 (需要分析的加解密算法)
       ├─→ 通信协议 (网络流量中的加密数据)
       ├─→ 密码哈希 (需要破解的用户密码)
       └─→ 数字签名/证书 (验证/伪造)
       │
       ▼
┌─────────────┐
│  算法识别     │ ◄── 确定使用了什么加密方式
└──────┬───────┘
       │
       ├─→ 魔数/文件头识别
       ├─→ 特征字节模式 (块大小/填充/结构)
       ├─→ 字符串搜索 (algorithm/crypto/aes/rsa)
       ├─→ 常量识别 (S-box/轮常数/素数)
       └─→ 工具自动检测 (file/magic/binwalk)
       │
       ▼
┌─────────────┐
│  密钥/参数提取 │ ◄── 找到密钥就成功了一半
└──────┬───────┘
       │
       ├─→ 硬编码密钥 (代码中直接写死)
       ├─→ 配置文件 (xml/json/env/ini)
       ├─→ 运行时内存 (dump/调试器)
       ├─→ 派生密钥 (PBKDF2/Argon2/scrypt → 从密码派生)
       └─→ 密钥交换 (DH/ECDH → 协议捕获)
       │
       ▼
┌─────────────┐
│  解密/破解    │ ◄── 执行实际的解密操作
└──────┬───────┘
       │
       ├─→ 对称加密 (AES/DES/ChaCha20 + 密钥+IV)
       ├─→ 非对称加密 (RSA/ECIES + 私钥)
       ├─→ 哈希破解 (MD5/SHA1/bcrypt + 字典/彩虹表)
       ├─→ 自定义算法 (逆向还原后实现)
       └─→ 侧信道/实现缺陷利用
       │
       ▼
┌─────────────┐
│  验证与报告   │
└─────────────┘
```

---

## Phase 1: 样本分类与目标确认

### 1.1 目标类型矩阵

| 类型 | 典型场景 | 分析重点 |
|------|----------|----------|
| **加密文件** | 勒索软件加密、数据库加密、备份加密 | 文件格式、算法识别、密钥恢复 |
| **加密程序** | 软件保护、协议实现、自定义加密 | 算法逆向、密钥生成逻辑 |
| **通信协议** | 自定义协议、私有API、IoT通信 | 抓包、协议逆向、密钥协商 |
| **密码哈希** | 登录认证、文件校验、口令保护 | 哈希类型识别、字典攻击 |
| **数字签名** | 证书验证、代码签名、完整性校验 | 公钥提取、签名伪造 |

### 1.2 信息收集清单

```
输入:
  - 加密文件/样本本身
  - 加密程序（如果有）
  - 已知明文（可选，但极有价值）
  - 密码提示（如果有）
  - 相关配置文件

上下文:
  - 这个加密来自什么应用/系统?
  - 有没有原始未加密版本做对比?
  - 有没有已知的正确密码/密钥?
  - 加密是什么时候发生的?
```

## Phase 2: 算法识别

### 2.1 文件头/魔数识别

| 魔数/特征 | 可能的格式/算法 |
|-----------|-----------------|
| `Salted__` | OpenSSL EVP (通常AES/CBC/PBKDF2) |
| `-----BEGIN` / PEM头 | RSA/DSA/EC私钥或证书 (Base64) |
| `\x1f\x8b` | Gzip压缩 (可能叠加加密) |
| `PK\x03\x04` | ZIP (可能加密) |
| `SQLite format 3\000` | SQLite数据库 (可能SQLCipher) |
| 高熵无结构 | 流密码/块密码(CTR/OFB/GCM模式) |
| 固定块重复 | ECB模式 (可观察模式) |
| 16字节对齐 | AES/3DES/Serpent等块密码 |
| 8字节对齐 | DES/Blowfish/CAST5 |
| 32字节对齐 | SHA-256输出? 或256位密钥相关 |

### 2.2 特征分析工具

```bash
# 文件类型识别
file encrypted_file.bin
xxd encrypted_file.bin | head -50

# 熵分析 (高熵=可能加密/压缩)
python3 -c "
import sys, math
data = open(sys.argv[1],'rb').read()
freq = [0]*256
for b in data: freq[b] += 1
entropy = -sum((c/len(data))*math.log2(c/len(data)) for c in freq if c)
print(f'Entropy: {entropy:.2f} / 8.00')
" encrypted_file.bin

# 块长度检测 (找重复模式)
python3 -c "
data = open(sys.argv[1],'rb').read()
for bs in [8,16,32,64,128]:
    blocks = [data[i:i+bs] for i in range(0,len(data),bs)]
    unique = len(set(blocks))
    total = len(blocks)
    print(f'Block size {bs}: {unique}/{total} unique ({100*unique//total}%)')
" encrypted_file.bin

# 字符串搜索
strings -n 10 encrypted_file.bin | head -30
# 搜索加密相关关键词
strings encrypted_file.bin | grep -iE "aes|rsa|sha|md5|key|salt|iv|password|encrypt|decrypt|cipher"
```

### 2.3 常见算法特征

#### 对称加密特征
```
AES:
  - 块大小: 16字节
  - 密钥长度: 16/24/32字节 (128/192/256位)
  - 常见模式: CBC (需IV), GCM (需Nonce+Tag), CTR, ECB
  - OpenSSL特征: "Salted__" + 8字节 salt

DES/3DES:
  - 块大小: 8字节
  - 密钥长度: 8字节(DES) / 24字节(3DES)
  - 较老系统中常见

ChaCha20-Poly1305:
  - 流密码, 无固定块大小
  - 12字节 Nonce + 16字节 Tag
  - Google/Mobile常用

RC4:
  - 流密码, 无块边界
  - 可通过已知明文攻击破解
  - WEP/TLS旧版中使用
```

#### 哈希算法特征
```
MD5:  16字节 (32 hex字符)
SHA1: 20字节 (40 hex字符)
SHA256: 32字节 (64 hex字符)
SHA512: 64字节 (128 hex字符)

bcrypt: $2a$/$2b$/$2y$ + 53字符 (60字节base64)
scrypt: $scrypt$ + 参数 + base64
Argon2: $argon2{id}$ + 参数 + base64
PBKDF2: 通常带salt和迭代次数信息
```

### 2.4 代码中算法识别

```
在二进制/源码中搜索:

导入函数线索:
  Windows: CryptEncrypt/AES_encrypt/RSA_public_encrypt
  OpenSSL: EVP_EncryptInit_ex / EVP_DigestInit_ex
  Java: Cipher.getInstance / MessageDigest.getInstance
  .NET: Aes.Create() / SHA256Managed()

常量线索:
  AES S-box值 (0x63, 0x7c, 0x77, 0x7b...)
  SHA初始向量 (0x6a09e667, 0xbb67ae85...)
  圆周率前几位 (常见随机种子)
  大素数 (RSA模数)

字符串线索:
  "AES", "CBC", "PKCS5Padding" (Java)
  "EVP_aes_256_cbc" (OpenSSL)
  "pbkdf2", "hmac-sha256", "rsa-oaep"
```

## Phase 3: 密钥/参数提取

### 3.1 硬编码密钥搜索

```bash
# 二进制文件中搜索可能的密钥
strings -n 16 target.exe | grep -E "^[A-Za-z0-9+/]{16,32}={0,2}$"
# 16-32字符的Base64-like字符串可能是密钥

# 十六进制密钥
strings target.exe | grep -E "^[0-9a-fA-F]{32,64}$"

# Python自动化搜索
python3 << 'EOF'
import re, struct

data = open('target.exe', 'rb').read()

# 搜索高熵区域 (可能是密钥)
for i in range(len(data)-32):
    chunk = data[i:i+32]
    freq = [chunk.count(bytes([b])) for b in range(256)]
    entropy = -sum((c/32)*__import__('math').log2(c/32) for c in freq if c)
    if 6.0 < entropy < 8.0:
        print(f"Possible key at 0x{i:X}: {chunk.hex()}")

# 搜索PE资源中的密钥
EOF
```

### 3.2 配置文件检查

```
常见位置:
  - .env, .config, settings.json, app.config
  - *.properties (Java)
  - plist (iOS/macOS)
  - registry (Windows)
  - shared_prefs (Android)

搜索模式:
  "password": "...",
  "secret_key": "...",
  "encryption_key": "...",
  "api_secret": "...",
  "private_key": "---BEGIN..."
```

### 3.3 内存中密钥提取

```javascript
// Frida Hook: 捕获密钥使用时刻
Interceptor.attach(Module.findExportByName("libcrypto.so", "EVP_EncryptUpdate"), {
    onEnter: function(args) {
        var ctx = args[0];
        // ctx->cipher_data 包含密钥信息
        console.log("EVP_EncryptUpdate called");
        // dump context to find key
    }
});

// Hook Java crypto
Java.perform(function() {
    var SecretKeySpec = Java.use("javax.crypto.spec.SecretKeySpec");
    SecretKeySpec.$init.overload("[B","java.lang.String").implementation = function(key, algo) {
        console.log("Key (" + algo + "): " + hexdump(key));
        return this.$init(key, algo);
    };
});
```

### 3.4 密钥派生函数分析

```
PBKDF2-HMAC-SHA256:
  输入: password + salt + iterations
  输出: derived key
  破解: hashcat -m 10900 或 John

Argon2id:
  输入: password + salt + iterations + memory + parallelism
  输出: derived key
  破解: hashcat -m 17210 (较慢, GPU友好度低)

scrypt:
  输入: password + salt + N/r/p 参数
  输出: derived key
  破解: hashcat -m 17900

从代码中提取参数:
  找到 PBKDF2/Argon2/scrypt 调用点
  提取 salt 值和迭代次数
  这些参数是离线破解所必需的
```

## Phase 4: 解密/破解执行

### 4.1 对称加密解密

```python
# OpenSSL格式解密 (Salted__)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import hashlib

def decrypt_openssl_eas(data, password):
    # 解析 "Salted__" + 8-byte salt
    assert data[:8] == b'Salted__'
    salt = data[8:16]
    ciphertext = data[16:]

    # PBKDF2派生密钥和IV
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=48,  # 32(key) + 16(iv)
        salt=salt,
        iterations=10000,
    )
    derived = kdf.derive(password.encode())
    key = derived[:32]
    iv = derived[32:48]

    # AES-256-CBC解密
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    # PKCS7 unpadding
    pad_len = padded[-1]
    return padded[:-pad_len]

# 使用
with open('encrypted.enc', 'rb') as f:
    data = f.read()
decrypted = decrypt_openssl_eas(data, 'password_here')
print(decrypted.decode())
```

### 4.2 哈希破解

```bash
# hashcat 使用指南

# MD5 ($1$)
hashcat -m 500 hashes.txt wordlist.txt

# SHA-256 ($5$)
hashcat -m 1800 hashes.txt wordlist.txt

# bcrypt ($2a$/2b$/2y$)
hashcat -m 3200 hashes.txt wordlist.txt

# scrypt ($s0$)
hashcat -m 89100 hashes.txt wordlist.txt

# Argon2 ($argon2*)
hashcat -m 17210 hashes.txt wordlist.txt

# 规则攻击 (常用密码变形)
hashcat -m 0 hashes.txt rockyou.txt -r rules/best64.rule

# 掩码攻击 (已知部分密码)
hashcat -m 0 hashes.txt '?u?l?l?l?d?d?d?d'
# ?u=大写 ?l=小写 ?d=数字
# 例: Pass1234 格式

# 组合攻击
hashcat -m 0 hashes.txt dict1.txt dict2.txt --combine
```

### 4.3 RSA相关分析

```
情况1: 有公钥，想求私钥
  - 小指数(e=3) + 低填充 → 广播攻击
  - 小N (<512bit) → 因式分解 (factordb.com, yafu, msieve)
  - 共享因子 → GCD攻击
  - Fermat因式分解 (p,q接近)

情况2: 有私钥但不知道密码
  - PKCS#8加密私钥 → openssl rsa / john / hashcat (-m 18221)
  - PFX/P12 → openssl pkcs12 / patator

情况3: RSA-OAEP/PKCS1v15 padding oracle
  - Bleichenbacher攻击 (PKCS1v15)
  - Manger攻击 (OAEP)
```

### 4.4 自定义算法逆向

```
步骤:
1. 定位加密/解密函数入口
2. 反编译为伪代码
3. 识别核心操作:
   - S-box查找表替换
   - 位运算 (XOR/ROT/SHIFT)
   - 数学运算 (模乘/幂运算)
   - Feistel网络结构
4. 用Python/C重写算法
5. 用已知明文验证正确性
6. 实现逆运算 (解密)

常见自定义加密特征:
  - 多轮XOR (简单但常见于游戏/小型应用)
  - 字节置换 + 替换 (类AES简化版)
  - 基于LUT的流密码
  - 混合多种操作的"独创"算法
```

## Phase 5: 实现缺陷利用

### 5.1 常见密码学错误

| 错误 | 影响 | 检测方法 |
|------|------|----------|
| ECB模式使用 | 图案泄露 | 相同明文→相同密文 |
| 固定IV | 字典攻击 | 多次加密同一消息对比 |
| 弱PRNG | 种子预测 | 时间戳作为种子? |
| 认证标签缺失 | 比特翻转 | 修改密文看是否报错 |
| 密钥复用 (OTP) | XOR泄露 | 两密文XOR = 两明文XOR |
| 侧信道时间差异 | 时序攻击 | 测量响应时间变化 |
| Padding Oracle | 完全解密 | 修改密文末尾观察错误 |

### 5.2 Padding Oracle Attack

```python
# CBC模式Padding Oracle攻击概念
def padding_oracle_attack(ciphertext_block, prev_block, oracle_func):
    # oracle_func(ciphertext) returns True if padding valid
    intermediate = bytearray(16)
    plaintext = bytearray(16)

    for byte_pos in range(15, -1, -1):
        padding_value = 16 - byte_pos
        crafted = bytearray(16)

        # 设置已知字节的padding
        for k in range(byte_pos + 1, 16):
            crafted[k] = intermediate[k] ^ padding_value

        # 爆破当前字节
        for guess in range(256):
            crafted[byte_pos] = guess
            test_ct = bytes(crafted) + ciphertext_block
            if oracle_func(test_ct):
                intermediate[byte_pos] = guess ^ padding_value
                plaintext[byte_pos] = intermediate[byte_pos] ^ prev_block[byte_pos]
                break

    return bytes(plaintext)
```

## 报告模板

```markdown
# 密码学分析报告: [目标]

## 基本信息
- 目标类型: 加密文件 / 加密程序 / 通信协议
- 文件大小: ...
- 熵值: ... / 8.00

## 算法识别结果
- 加密算法: AES-256-CBC
- 密钥派生: PBKDF2-HMAC-SHA256 (10000 iterations)
- 填充方案: PKCS7

## 密钥/参数
- Salt: (hex)
- IV: (hex or derived)
- 密钥来源: 硬编码 / 配置文件 / 用户输入

## 解密结果
- 成功: 是/否
- 方法: ...
- 明文预览: ...

## 安全建议
...
```