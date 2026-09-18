# Mobile Security - 移动安全分析工作流

## 完整流程图

```
APK/IPA样本接收
    │
    ▼
┌─────────────┐
│  静态分析     │ ◄── 不安装，只反编译/解包
└──────┬───────┘
       │
       ├─→ 反编译 (apktool/jadx)
       ├─→ 清单文件分析 (AndroidManifest/Info.plist)
       ├─→ 权限审查
       ├─→ 证书与签名验证
       └─→ 代码/资源提取
       │
       ▼
┌─────────────┐
│  组件分析     │ ◄── 入口点+暴露面
└──────┬───────┘
       │
       ├─→ Activity/Service/Receiver/Provider
       ├─→ 导出组件检测
       ├─→ Deep Link / URL Scheme
       ├─→ Intent Filter 分析
       └─→ WebView 配置
       │
       ▼
┌─────────────┐
│  代码审计     │ ◄── 关键逻辑追踪
└──────┬───────┘
       │
       ├─→ 硬编码密钥/凭证搜索
       ├─→ 网络通信分析 (API/协议)
       ├─→ 加密实现审查
       ├─→ 本地存储安全 (SharedPreferences/SQLite/Keychain)
       └─→ 混淆强度评估
       │
       ▼
┌─────────────┐
│  动态分析     │ ◄── 运行时Hook+监控
└──────┬───────┘
       │
       ├─→ Frida Hook (Java/Native层)
       ├─→ SSL Pinning绕过
       ├─→ Root/Magisk检测绕过
       ├─→ 网络流量抓包 (mitmproxy/Burp)
       └─→ 行为监控 (文件/进程/网络)
       │
       ▼
┌─────────────┐
│  Native层分析  │ ◄── .so库逆向
└──────┬───────┘
       │
       ├─→ 提取 .so 文件
       ├─→ 架构识别 (arm64-v8a/armeabi-v7a)
       ├─→ 导入导出函数分析
       ├─→ JNI接口定位
       └─→ Ghidra/IDA反编译
```

---

# Android APK 分析

## Phase 1: 静态分析

### 1.1 反编译

```bash
# 资源+Smali代码（保留结构）
apktool d app.apk -o output_dir

# Java源码（可读性好）
jadx app.apk -d jadx_output

# 快速信息提取
apksigner verify --print-certs app.apk
aapt dump badging app.apk
```

### 1.2 AndroidManifest.xml 审查

**必查项**:

| 检查项 | 关注点 | 风险 |
|--------|--------|------|
| `android:exported="true"` | 组件是否对外暴露 | 任意应用可调用 |
| `android:permission` | 权限保护 | 无权限=可被外部启动 |
| `android:debuggable="true"` | 调试模式 | 可附加调试器 |
| `android:allowBackup="true"` | 允许备份 | 数据可通过adb备份提取 |
| `networkSecurityConfig` | 网络安全配置 | 是否允许明文HTTP |
| 自定义权限 | 权限定义 | 保护级别(normal/dangerous) |

**敏感权限检查**:
```xml
<!-- 高危权限 -->
<uses-permission android:name="android.permission.READ_CONTACTS"/>
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.CAMERA"/>
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
<uses-permission android:name="android.permission.READ_SMS"/>
<uses-permission android:name="android.permission.WRITE_SETTINGS"/>
```

### 1.3 证书与签名

```bash
# 证书信息
keytool -printcert -jarfile app.apk

# 检查签名是否一致（防篡改）
apksigner verify --verbose app.apk

# V1/V2签名检查
java -jar apksigner.jar verify -v --print-certs app.apk
```

**风险**: 使用默认debug签名、证书过期、SHA-1弱哈希

### 1.4 代码审计重点

#### 硬编码敏感信息搜索
```
关键词:
  password, secret, key, token, api_key, private, credential
  aws_access, google_api, firebase, jwt_secret
  mysql://, mongodb://, postgres://, redis://
  Authorization: Bearer, X-API-Key

工具:
  grep -r "password\|secret\|api_key" smali*/  (apktool输出)
  jadx的Search功能
  MobSF自动扫描
```

#### 网络通信分析
```
查找所有网络请求:
  - HttpURLConnection / OkHttpClient / Retrofit / Volley
  - URL构造: baseUrl + endpoint + params
  - Header设置: Token/Cookie/API Key

API端点提取:
  - 基础URL常量
  - 接口路径字符串
  - Retrofit注解 (@GET/@POST/@PUT/@DELETE)

加密传输检查:
  - 是否使用HTTPS?
  - 证书校验是否严格?
  - 有无SSL Pinning?
```

#### 本地数据存储
```
SharedPreferences:
  - MODE_PRIVATE? MODE_WORLD_READABLE?
  - 敏感数据明文存储?

SQLite数据库:
  - /data/data/<pkg>/databases/
  - 表结构和内容

外部存储:
  - /sdcard/Android/data/<pkg>/
  - 日志文件、缓存、临时文件

KeyChain/Keystore:
  - Android Keystore使用方式
  - 密钥保护强度
```

## Phase 2: 动态分析

### 2.1 环境准备

```
设备要求:
  - 已Root手机 或 模拟器 (Genymotion/AVD)
  - Magisk + MagiskHide (隐藏Root)
  - Frida Server (匹配架构版本)

工具链:
  - adb (调试桥)
  - frida-server (Hook框架)
  - objection (Frida高级封装)
  - mitmproxy / Burp Suite (抓包)
  - MobSF (自动化扫描)
```

### 2.2 SSL Pinning 绕过

```javascript
// Frida通用SSL Pinning绕过脚本
Java.perform(function() {
    // TrustManagerImpl
    var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
    TrustManagerImpl.verifyChain.implementation = function() {
        return this.chain;
    };

    // OkHttp CertificatePinner
    var CertificatePinner = Java.use('okhttp3.CertificatePinner');
    CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function() {};
});
```

**其他方法**:
- Frida: `objection sslpinning disable --quiet`
- 手动: 替换证书文件 (res/raw/)
- Xposed模块: JustTrustMe, TrustMeAlready

### 2.3 Root/Magisk检测绕过

```
常见检测点:
  - su二进制存在检查 → 隐藏su或Hook File.exists()
  - Magisk包名检查 → 改包名
  - /proc/self/status 检查 → Hook读取结果
  - SafetyNet/Play Integrity → 用Play Integrity API模拟
  - RootBeer库 → Hook其所有检测方法

通用绕过:
  - MagiskHide (DenyList)
  - Shamiko (Zygisk注入隐藏)
  - Frida脚本: root-detection-bypass
```

### 2.4 Frida Hook常用场景

```javascript
// Hook特定函数查看参数和返回值
Java.perform(function() {
    var cls = Java.use('com.example.app.LoginActivity');
    cls.login.implementation = function(user, pass) {
        console.log('Username: ' + user);
        console.log('Password: ' + pass);
        var result = this.login(user, pass);
        console.log('Result: ' + result);
        return result; // 可修改返回值!
    };
});

// Hook native函数
Interceptor.attach(Module.findExportByName("libnative.so", "encrypt"), {
    onEnter: function(args) {
        console.log("Input: " + hexdump(args[0]));
    },
    onLeave: function(retval) {
        console.log("Output: " + retval);
    }
});

// 枚举类和方法
Java.enumerateLoadedClasses({
    onMatch: function(name) {
        if (name.includes("crypto") || name.includes("key")) {
            console.log(name);
        }
    },
    onComplete: function() {}
});
```

### 2.5 网络抓包

```
mitmproxy配置:
  1. 安装CA证书到系统证书目录 (需Root)
  2. 启动mitmproxy -p 8080
  3. 手机设置代理指向PC
  4. 安装mitmproxy CA证书

Burp Suite配置:
  类似，但需要Proxifier转发Android流量

关键捕获:
  - 登录认证请求/响应
  - API请求参数和返回
  - Token/Cookie获取和刷新
  - 敏感数据传输(密码/证件号)
```

## Phase 3: Native层 (.so) 分析

### 3.1 提取与分析

```bash
# 从APK提取so文件
unzip app.apk lib/arm64-v8a/*.so

# 基本信息
file libnative.so
readelf -h libnative.so
readelf -s libnative.so  # 符号表

# 导入函数分析
readelf -D libnative.so  # 动态符号
nm -D libnative.so        # 动态符号(更友好)
```

### 3.2 JNI接口定位

```
JNI函数命名规则:
  Java_<package>_<class>_<method>
  例: Java_com_example_app_NativeHelper_encrypt

搜索特征:
  JNI_OnLoad — 注册动态JNI方法
  RegisterNatives — 大量方法注册
  env->FindClass / env->GetMethodID / env->CallObjectMethod

Ghidra导入:
  Import → 设置为ARM/ARM64
  自动分析 → 搜索JNI特征串
  导出函数列表 → 定位关键函数
```

### 3.3 常见Native层保护

| 保护类型 | 特征 | 应对 |
|----------|------|------|
| OLLVM混淆 | 控制流平坦化 | 符号执行/手动还原 |
| 加壳(.so) | 高熵/少导出 | IDA动态调试脱壳 |
| 反调试 | ptrace/fork/TracerPid | Frida绕过 |
| 字符串加密 | 运行时解密 | Hook解密函数Dump |

---

# iOS IPA 分析

## Phase 1: 静态分析

### 1.1 解包IPA

```bash
# IPA就是zip
unzip app.ipar -o ipa_extracted

# 主要目录
ipa_extracted/Payload/app.app/
  ├── Info.plist          # 应用配置
  ├── executable          # 主程序(Mach-O)
  ├── Frameworks/         # 动态库
  ├── Plugins/            # 扩展
  └── embedded.mobileprovision # 描述文件
```

### 1.2 Info.plist 审查

**必查项**:
```xml
<key>NSAppTransportSecurity</key>
<dict>
  <key>NSAllowsArbitraryLoads</key>  <!-- true=允许HTTP -->
  <true/>
</dict>

<key>URLTypes</key>  <!-- URL Scheme -->

<key>LSApplicationQueriesSchemes</key>  <!-- 可查询的Scheme -->
```

### 1.3 Mach-O分析

```bash
# 基本信息otool -fv app_executable
otool -lV app_executable  # Load Commands
otool -L app_executable   # Dynamic Libraries

# 类信息class-dump -H app_executable -o headers/

# 反编译
# 方案1: Hopper Disassembler
# 方案2: Ghidra (免费)
# 方案3: IDA Pro
```

### 1.4 Swift/Objective-C审计

```
Objective-C:
  - class-dump提取头文件
  - 搜索selector: respondsToSelector
  - 方法交换(swizzling)检测

Swift:
  - 符号名混淆: _$s...
  - 搜索关键字符串
  - 搜索网络/加密相关类
```

## Phase 2: 动态分析(iOS越狱设备)

### 2.1 越狱环境准备

```
设备: iPhone (已越狱, 推荐 checkra1n)
工具:
  - Cydia/Substitute (包管理)
  - OpenSSH (远程连接)
  - Frida-ios-dump (砸壳)
  - cycript (运行时分析)
  - clutch/frida-ios-dump (解密)
```

### 2.2 砸壳 (脱壳)

```bash
# frida-ios-dump (推荐)
python dump.py <Bundle_ID>

# clutch (旧版)
clutch -b <Bundle_ID>

# 输出: 解密的IPA文件
```

### 2.3 运行时分析

```objective-c
// cycript示例
# 当前UI层级
UIApp.keyWindow.recursiveDescription().toString()

# 查找类
[NSBundle allFrameworks]

# 调用方法
[[UIApplication sharedApplication] openURL:[NSURL URLWithString:@"scheme://"]]

// Frida iOS
// Objective-C method hooking
ObjC.classes.NSURLSession.configuration.implementation = function() { ... }
```

## 报告模板

```markdown
# 移动应用安全报告: [应用名称]

## 基本信息
- 包名/Bundle ID: ...
- 版本: ...
- 平台: Android / iOS
- 证书指纹: ...

## 发现汇总
| # | 严重程度 | 类型 | 组件 | 状态 |
|---|----------|------|------|------|
| 1 | High | 硬编码密钥 | LoginActivity | 已确认 |

## 详细发现
...

## 建议
...
```