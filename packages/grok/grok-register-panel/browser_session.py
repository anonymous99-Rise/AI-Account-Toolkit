# -*- coding: utf-8 -*-
"""浏览器会话管理（线程本地 browser/page）。

使用 Camoufox（C++ 引擎层指纹伪装）替代 DrissionPage。
Camoufox 从编译层修改 Gecko，JS 完全不可检测。
"""
from __future__ import annotations

import gc
import os
import shutil
import tempfile
import threading
import time
import uuid
from typing import Callable, Optional, Tuple
from urllib.parse import urlparse

import asyncio
from greenlet import greenlet
from typing import cast as _tcast

from camoufox.sync_api import Camoufox as _Camoufox, NewBrowser
from playwright._impl._connection import Connection as _PwConnection
from playwright._impl._greenlets import MainGreenlet as _PwMainGreenlet
from playwright._impl._object_factory import create_remote_object as _pw_create_remote
from playwright._impl._playwright import Playwright as _PwImpl
from playwright._impl._transport import PipeTransport as _PwPipeTransport
from playwright.sync_api._generated import Playwright as _SyncPlaywright

from camoufox_adapter import CamoufoxBrowser, CamoufoxPage
from secure_files import ensure_private_dir
from webui.blacklist_store import read_blacklist
from webui.security_utils import redact_log_line, redact_proxy


class SafeCamoufox(_Camoufox):
    """Camoufox 子类，绕过 PlaywrightContextManager 的事件循环检查。

    PlaywrightContextManager.__enter__() 调用 asyncio.get_running_loop()，
    如果当前线程有运行中的 asyncio 事件循环（如 tkinter 或其他库遗留），
    就会报错 "Sync API inside the asyncio loop"。

    此子类直接创建全新的、非运行状态的事件循环，完全绕过该检查。
    通过重写 __enter__()，跳过 get_running_loop() / is_running() 判断，
    直接用 asyncio.new_event_loop() 创建干净的事件循环。
    """

    def __enter__(self):
        # 强制创建全新的事件循环，跳过 get_running_loop() / is_running() 检查
        self._loop = asyncio.new_event_loop()
        self._own_loop = True

        # 复制 PlaywrightContextManager.__enter__() 的 greenlet 调度逻辑
        def _greenlet_main():
            self._loop.run_until_complete(self._connection.run_as_sync())

        dispatcher_fiber = _PwMainGreenlet(_greenlet_main)

        self._connection = _PwConnection(
            dispatcher_fiber,
            _pw_create_remote,
            _PwPipeTransport(self._loop),
            self._loop,
        )

        g_self = greenlet.getcurrent()

        def _callback_wrapper(channel_owner):
            playwright_impl = _tcast(_PwImpl, channel_owner)
            self._playwright = _SyncPlaywright(playwright_impl)
            g_self.switch()

        self._connection.call_on_object_with_known_name("Playwright", _callback_wrapper)
        dispatcher_fiber.switch()

        playwright = self._playwright
        playwright.stop = self.__exit__

        # Camoufox 特有：启动浏览器
        try:
            self.browser = NewBrowser(self._playwright, **self.launch_options)
        except BaseException as e:
            super().__exit__(type(e), e, e.__traceback__)
            raise
        return self.browser


# 仅允许删除该目录树下的临时 profile，防止误删其它路径
_PROFILE_ROOT_MARKER = "grok-register-camoufox"

_tls = threading.local()
_get_proxy: Optional[Callable[[], dict]] = None
_is_debug: Optional[Callable[[], bool]] = None
_extension_path: str = ""
_start_fail_lock = threading.Lock()
_start_fail_streak = 0
_start_fail_threshold = 3


def configure(get_proxies=None, is_debug=None, extension_path=""):
    global _get_proxy, _is_debug, _extension_path
    _get_proxy = get_proxies
    _is_debug = is_debug
    _extension_path = extension_path or ""


def get_start_fail_streak() -> int:
    with _start_fail_lock:
        return _start_fail_streak


def _note_start_success():
    global _start_fail_streak
    with _start_fail_lock:
        _start_fail_streak = 0


def _note_start_failure():
    global _start_fail_streak
    with _start_fail_lock:
        _start_fail_streak += 1
        return _start_fail_streak


def _proxies() -> dict:
    if _get_proxy:
        return _get_proxy() or {}
    return {}


def _debug() -> bool:
    return bool(_is_debug()) if _is_debug else False


def active_browser():
    return getattr(_tls, "browser", None)


def active_page():
    return getattr(_tls, "page", None)


def get_exit_ip() -> str:
    """当前线程浏览器启动时解析到的代理出口 IP。"""
    return str(getattr(_tls, "exit_ip", "") or "")


def get_bound_proxy() -> str:
    """当前线程绑定的代理 URL。"""
    return str(getattr(_tls, "bound_proxy", "") or "")


def set_exit_context(proxy: str = "", exit_ip: str = "") -> None:
    _tls.bound_proxy = proxy or ""
    _tls.exit_ip = exit_ip or ""


def clear_exit_context() -> None:
    for k in ("bound_proxy", "exit_ip"):
        if hasattr(_tls, k):
            try:
                delattr(_tls, k)
            except Exception:
                setattr(_tls, k, "")




# Baseline values remain as compatibility constants. Runtime additions live in
# log/blacklist_state.json and are never written into Python source.
_BLOCKED_ASN_SUBSTR = (
    "AS7922",  # Comcast Cable
    "AS5650",  # Frontier Communications
)
_BLOCKED_ISP_SUBSTR = (
    "comcast cable",
    "comcast ip services",
    "frontier communications",
)
_BLOCKED_ASN_NUMS = {5650, 7922}
_asn_cache = {}
_asn_cache_lock = __import__("threading").Lock()


def lookup_exit_meta(ip: str) -> dict:
    """查出口 ISP/AS。强制直连（忽略环境 HTTP_PROXY），优先 ipwho.is。"""
    import json
    import urllib.request
    ip = (ip or "").strip()
    if not ip:
        return {}
    with _asn_cache_lock:
        if ip in _asn_cache:
            return dict(_asn_cache[ip])
    info = {"query": ip}
    # 服务器环境常设 HTTP_PROXY，geo API 走代理会 502/超时；必须直连
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    errors = []
    # 1) ipwho.is over TLS
    try:
        raw = opener.open(f"https://ipwho.is/{ip}", timeout=10).read().decode("utf-8", errors="replace")
        data = json.loads(raw or "{}")
        if data.get("success") is False:
            raise RuntimeError(data.get("message") or "ipwho fail")
        conn = data.get("connection") or {}
        asn_num = conn.get("asn")
        info = {
            "query": ip,
            "status": "success",
            "as": f"AS{asn_num}" if asn_num is not None else "",
            "asn": asn_num,
            "isp": conn.get("isp") or data.get("isp") or "",
            "org": conn.get("org") or "",
            "city": data.get("city") or "",
            "regionName": data.get("region") or "",
            "country": data.get("country") or "",
            "mobile": bool((data.get("type") or "").lower() == "mobile") if False else None,
            "source": "ipwho.is",
        }
    except Exception as exc:
        errors.append(f"ipwho:{exc}")
        # 2) fallback ipapi.co over TLS
        try:
            url = f"https://ipapi.co/{ip}/json/"
            raw = opener.open(url, timeout=10).read().decode("utf-8", errors="replace")
            data = json.loads(raw or "{}")
            if data.get("error"):
                raise RuntimeError(data.get("reason") or "ipapi.co fail")
            as_text = str(data.get("asn") or "")
            info = {
                "query": ip,
                "status": "success",
                "as": as_text,
                "isp": data.get("org") or "",
                "org": data.get("org") or "",
                "city": data.get("city") or "",
                "regionName": data.get("region") or "",
                "country": data.get("country_name") or "",
                "source": "ipapi.co",
            }
            m = __import__("re").search(r"AS(\d+)", as_text)
            if m:
                info["asn"] = int(m.group(1))
        except Exception as exc2:
            errors.append(f"ipapi:{exc2}")
            info = {"query": ip, "error": "; ".join(errors)}
    with _asn_cache_lock:
        _asn_cache[ip] = dict(info)
    return info


def is_blocked_exit_ip(ip: str) -> tuple:
    """若应跳过该出口，返回 (True, reason)；否则 (False, meta摘要)."""
    info = lookup_exit_meta(ip)
    asn = str(info.get("as") or "")
    asn_num = info.get("asn")
    try:
        if asn_num is None:
            m = __import__("re").search(r"AS(\d+)", asn)
            asn_num = int(m.group(1)) if m else None
        else:
            asn_num = int(asn_num)
    except Exception:
        asn_num = None
    isp = str(info.get("isp") or "")
    org = str(info.get("org") or "")
    blob = f"{asn} | {isp} | {org}".lower()
    state = read_blacklist()
    blocked_asns = set(state.get("asns") or _BLOCKED_ASN_NUMS)
    blocked_asn_labels = tuple(f"AS{value}" for value in blocked_asns)
    blocked_isp_keywords = tuple(state.get("isp_keywords") or _BLOCKED_ISP_SUBSTR)
    if asn_num in blocked_asns:
        return True, f"blocked ASN AS{asn_num}: {asn} / {isp} / {org} / {info.get('city')}"
    for key in blocked_asn_labels:
        if key.lower() in blob:
            return True, f"blocked ASN {key}: {asn} / {isp} / {info.get('city')}"
    for key in blocked_isp_keywords:
        if key in blob:
            return True, f"blocked ISP '{key}': {asn} / {isp} / {info.get('city')}"
    summary = f"{asn or '?'} | {isp or '?'} | {info.get('city') or '?'}"
    return False, summary



def set_browser_session(browser_obj=None, page_obj=None):
    _tls.browser = browser_obj
    _tls.page = page_obj


class _SessionProxy:
    __slots__ = ("_key",)

    def __init__(self, key):
        self._key = key

    def _obj(self):
        return getattr(_tls, self._key, None)

    def __bool__(self):
        return self._obj() is not None

    def __eq__(self, other):
        return self._obj() is other

    def __ne__(self, other):
        return self._obj() is not other

    def __getattr__(self, name):
        obj = self._obj()
        if obj is None:
            raise AttributeError(f"{self._key} is not started")
        return getattr(obj, name)


browser = _SessionProxy("browser")
page = _SessionProxy("page")


def _is_managed_profile_dir(path: str) -> bool:
    """是否为本工具创建的临时 Camoufox 资料目录。"""
    if not path:
        return False
    norm = os.path.normpath(path).replace("\\", "/").lower()
    marker = _PROFILE_ROOT_MARKER.lower()
    return f"/{marker}/" in f"/{norm}/" or norm.rstrip("/").endswith(f"/{marker}")


def _rmtree_with_retry(path: str, max_retries: int = 3, delay: float = 0.5) -> bool:
    """Windows 上文件锁可能导致 rmtree 失败，带重试。

    返回 True 表示最终删除成功。
    """
    for attempt in range(max_retries):
        try:
            shutil.rmtree(path, ignore_errors=False)
            return True
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))
            # 最后一次尝试：强制忽略错误
            try:
                shutil.rmtree(path, ignore_errors=True)
                return not os.path.isdir(path)
            except Exception:
                return False
    return not os.path.isdir(path)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False


def _cleanup_profile_dir(profile_dir=None) -> None:
    """关闭浏览器后删除临时 user-data，避免 TEMP 堆积。"""
    path = profile_dir if profile_dir is not None else getattr(_tls, "profile_dir", None)
    try:
        if getattr(_tls, "profile_dir", None) and (
            profile_dir is None
            or os.path.normpath(str(getattr(_tls, "profile_dir")))
            == os.path.normpath(str(path or ""))
        ):
            _tls.profile_dir = None
    except Exception:
        pass
    if not path or not _is_managed_profile_dir(str(path)):
        return
    if os.path.isdir(path):
        _rmtree_with_retry(path)


def cleanup_stale_profiles(log_callback=None) -> int:
    """启动时清理上次崩溃 / 强杀残留的临时 profile 目录。

    扫描 TEMP/grok-register-camoufox/ 下的子目录，
    删除所有未被当前进程占用的旧目录。
    返回清理的目录数量。
    """
    root = os.path.join(tempfile.gettempdir(), _PROFILE_ROOT_MARKER)
    if not os.path.isdir(root):
        return 0
    ensure_private_dir(root)

    current_pid = os.getpid()
    cleaned = 0
    try:
        for entry in os.listdir(root):
            entry_path = os.path.join(root, entry)
            if not os.path.isdir(entry_path):
                continue
            # Directory format: {pid}-{thread_id}-{uuid8}. Unknown names are
            # never removed, and profiles owned by any live process are kept.
            match = __import__("re").fullmatch(r"(\d+)-\d+-[0-9a-fA-F]{8}", entry)
            if not match:
                continue
            owner_pid = int(match.group(1))
            if owner_pid == current_pid or _pid_alive(owner_pid):
                continue
            if _rmtree_with_retry(entry_path):
                cleaned += 1
    except Exception:
        pass

    # 如果 root 目录已空，顺便删掉
    if cleaned > 0:
        try:
            remaining = os.listdir(root)
            if not remaining:
                shutil.rmtree(root, ignore_errors=True)
        except Exception:
            pass

    if cleaned > 0 and log_callback:
        log_callback(f"[*] 启动清理: 已删除 {cleaned} 个残留浏览器资料目录")
    return cleaned



def _resolve_proxy_exit_ip(proxy_str: str, timeout: float = 8.0, log_callback=None) -> str:
    """经代理探测出口公网 IP（比 Camoufox 内置 public_ip 更耐住宅延迟）。

    Camoufox geoip=True 时会自己请求 ipecho/ipify，timeout 仅 5s，
    住宅 sticky 稍慢就 Failed to get IP → 浏览器启动失败。
    这里加长超时、多源探测，成功后把 IP 字符串传给 geoip=，跳过库内探测。
    """
    import re as _re
    import warnings
    import requests
    from urllib3.exceptions import InsecureRequestWarning

    proxy_str = (proxy_str or "").strip()
    if not proxy_str:
        raise RuntimeError("代理为空，无法探测出口 IP")
    urls = (
        "https://api.ipify.org",
        "https://checkip.amazonaws.com",
        "https://ipinfo.io/ip",
        "https://icanhazip.com",
        "https://ifconfig.me/ip",
        "https://ipecho.net/plain",
    )
    proxies = {"http": proxy_str, "https": proxy_str}
    last_exc = None
    hard_fails = 0
    # 死代理别把 6 个源全扫完（最坏 ~72s）；连续 2 次连接/SSL 失败即放弃
    per_try = min(float(timeout), 8.0)
    for url in urls:
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=InsecureRequestWarning)
                resp = requests.get(url, proxies=proxies, timeout=per_try, verify=False)
            resp.raise_for_status()
            ip = (resp.text or "").strip().split()[0]
            if _re.match(r"^(?:\d{1,3}\.){3}\d{1,3}$", ip) or ":" in ip:
                if log_callback:
                    log_callback(f"[*] 代理出口 IP: {ip} (via {url.split('/')[2]})")
                return ip
            last_exc = RuntimeError(f"非 IP 响应: {ip[:60]!r}")
            hard_fails = 0
        except Exception as exc:
            last_exc = exc
            hard_fails += 1
            if log_callback:
                host = url.split("/")[2]
                log_callback(f"[Debug] 出口 IP 探测失败 {host}: {redact_log_line(str(exc))}")
            if hard_fails >= 2:
                break
            continue
    raise RuntimeError(
        f"代理出口 IP 探测失败(timeout={per_try}s): {redact_log_line(str(last_exc))}"
    )


def _build_camoufox_proxy(proxy_str: str) -> dict:
    """把 http://host:port 格式的代理 URL 转换为 Camoufox/Playwright proxy dict。"""
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return {}
    parsed = urlparse(proxy_str)
    if parsed.scheme and parsed.hostname:
        server = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            server += f":{parsed.port}"
    else:
        server = proxy_str
    result: dict = {"server": server}
    if parsed.username:
        result["username"] = parsed.username
    if parsed.password:
        result["password"] = parsed.password
    return result


def _detect_camoufox_exe() -> str:
    """检测 Camoufox 可执行文件路径，支持新旧两种安装格式。

    新格式（multiversion）：browsers/{repo}/{version}/camoufox.exe + .0.5_FLAG
    旧格式（legacy）：直接在 INSTALL_DIR 下，无 .0.5_FLAG

    旧格式下 installed_verstr() 会报错 "official/stable is not installed"，
    需要传 executable_path + ff_version 绕过该检查。
    """
    import json as _json
    from camoufox.pkgman import INSTALL_DIR, LAUNCH_FILE, OS_NAME

    exe_name = LAUNCH_FILE.get(OS_NAME, "camoufox.exe")
    compat_flag = INSTALL_DIR / ".0.5_FLAG"

    # 新格式：COMPAT_FLAG 存在，让 launch_options() 自行处理
    if compat_flag.exists():
        return ""

    # 旧格式：直接在 INSTALL_DIR 下查找
    legacy_exe = INSTALL_DIR / exe_name
    if legacy_exe.exists():
        return str(legacy_exe)

    return ""


def _detect_ff_version() -> str:
    """从 version.json 读取 Firefox 主版本号（如 "152"）。

    旧格式安装的 version.json 格式：{"version": "152.0.4", "release": "beta.28"}
    新格式还包含 "build" 字段。
    """
    import json as _json
    from camoufox.pkgman import INSTALL_DIR

    version_file = INSTALL_DIR / "version.json"
    if not version_file.exists():
        # 检查 browsers/ 子目录
        browsers_dir = INSTALL_DIR / "browsers"
        if browsers_dir.exists():
            for vf in browsers_dir.rglob("version.json"):
                version_file = vf
                break
    if not version_file.exists():
        return ""

    try:
        data = _json.loads(version_file.read_bytes())
        version_str = str(data.get("version", ""))
        major = version_str.split(".")[0]
        return major if major.isdigit() else ""
    except Exception:
        return ""


def create_browser_options(unique_profile=True) -> dict:
    """构建 Camoufox 启动参数 dict。

    返回可直接传给 Camoufox(**opts) 的参数字典。
    替代原 DrissionPage 的 ChromiumOptions。

    反检测策略：
    - headless=False：有头模式（headless 更易被检测）
    - humanize=True：人类化鼠标移动 + 点击轨迹
    - geoip=True：基于代理 IP 匹配时区 / 语言 / 经纬度
    - block_webrtc=True：WebRTC IP 泄漏防护（避免真实 IP 通过 STUN 暴露）
    - 指纹由 BrowserForge 自动生成（匹配 Firefox/Camoufox 引擎）
    """
    opts: dict = {
        "headless": False,      # 反检测：有头模式（headless 更易被检测）
        "humanize": True,       # 人类化鼠标移动 + 贝塞尔轨迹
        "geoip": True,          # 基于 IP 匹配时区 / 语言 / 经纬度
        "locale": "en-US",      # 与美西出口一致，避免 UI 语言漂移
        "block_webrtc": True,   # 防止 WebRTC 泄漏真实 IP（即使使用代理）
        "i_know_what_im_doing": True,  # 抑制 Firefox 版本伪装警告（Camoufox 引擎层伪装是预期行为）
    }

    # 旧格式安装兼容：传 executable_path 绕过 installed_verstr() 检查
    # 注意：不传 ff_version，让 Camoufox 自动检测版本号
    # 传 ff_version 会导致指纹中版本号与引擎不匹配，Turnstile 检测到不一致会拒绝通过
    # 前提：config.json 中已设置 active_version="." 让 installed_verstr() 正常工作
    exe_path = _detect_camoufox_exe()
    if exe_path:
        opts["executable_path"] = exe_path

    # 代理 + 出口 IP 预解析
    # Camoufox geoip=True 会经代理访问 ipecho/ipify（库内 timeout=5s）。
    # 住宅 sticky 稍慢就 Failed to get IP → 浏览器启动失败。
    # 这里预解析成功后传 geoip="x.x.x.x"，跳过库内 5s 探测。
    proxies = _proxies()
    proxy = str(proxies.get("https") or proxies.get("http") or "").strip()
    if proxy:
        opts["proxy"] = _build_camoufox_proxy(proxy)
        try:
            exit_ip = _resolve_proxy_exit_ip(proxy, timeout=8.0)
            blocked, meta = is_blocked_exit_ip(exit_ip)
            if blocked:
                set_exit_context(proxy=proxy, exit_ip=exit_ip)
                raise RuntimeError(
                    f"出口IP命中黑名单，将换 sticky: ip={exit_ip} {meta}"
                )
            opts["geoip"] = exit_ip
            set_exit_context(proxy=proxy, exit_ip=exit_ip)
            # 把 ISP 摘要挂到 tls 方便结果日志
            try:
                _tls.exit_meta = meta
            except Exception:
                pass
        except Exception as ip_exc:
            # 已是我们的 RuntimeError 直接抛；探测失败也清空
            if "出口IP命中黑名单" in str(ip_exc):
                raise
            set_exit_context(proxy=proxy, exit_ip="")
            raise RuntimeError(
                f"代理不可用或过慢，无法解析出口 IP（将换 sticky）: {redact_log_line(str(ip_exc))}"
            ) from ip_exc
    else:
        set_exit_context(proxy="", exit_ip="")

    # 扩展（Camoufox 使用 addons 参数，加载 Firefox 扩展目录 / xpi）
    if _extension_path and os.path.exists(_extension_path):
        opts["addons"] = [_extension_path]

    # Profile 隔离
    if unique_profile:
        profile_root = ensure_private_dir(
            os.path.join(tempfile.gettempdir(), _PROFILE_ROOT_MARKER)
        )
        profile_dir = str(
            profile_root
            / f"{os.getpid()}-{threading.get_ident()}-{uuid.uuid4().hex[:8]}"
        )
        ensure_private_dir(profile_dir)
        opts["persistent_context"] = True
        opts["user_data_dir"] = profile_dir
        _tls.profile_dir = profile_dir

    return opts


def start_browser(log_callback=None) -> Tuple[object, object]:
    """启动 Camoufox 浏览器，返回 (CamoufoxBrowser, CamoufoxPage)。

    使用 Camoufox C++ 引擎层指纹伪装：
    - 从编译层修改 Gecko，JS 完全不可检测
    - 内置 BrowserForge 指纹生成器
    - GeoIP 自动匹配时区 / 语言
    - 人类化鼠标轨迹
    """
    last_exc = None
    for attempt in range(1, 5):
        profile_dir = None
        try:
            opts = create_browser_options(unique_profile=True)
            profile_dir = getattr(_tls, "profile_dir", None)
            if log_callback and isinstance(opts.get("geoip"), str):
                log_callback(f"[Debug] geoip 使用预解析出口 IP: {opts['geoip']}")

            # SafeCamoufox.__enter__() 直接创建全新事件循环，
            # 完全绕过 PlaywrightContextManager 的 get_running_loop() 检查
            camoufox = SafeCamoufox(**opts)
            browser_context = camoufox.__enter__()

            # 获取或创建页面
            raw_pages = (
                browser_context.pages
                if hasattr(browser_context, "pages")
                else []
            )
            if raw_pages:
                raw_page = raw_pages[0]
            else:
                raw_page = browser_context.new_page()

            # Playwright/Camoufox: uncaught pageerror with empty location can crash
            # the Node driver (location.url on undefined). Swallow safely.
            def _safe_pageerror(err):
                try:
                    msg = str(err)[:200]
                except Exception:
                    msg = "pageerror"
                # do not re-raise
                return None
            try:
                raw_page.on("pageerror", _safe_pageerror)
            except Exception:
                pass
            try:
                browser_context.on("pageerror", _safe_pageerror)
            except Exception:
                pass
            # Prefer reading cookies from context even if page is navigating
            try:
                raw_page.set_default_timeout(60000)
            except Exception:
                pass

            page_obj = CamoufoxPage(raw_page, browser_context)
            browser_obj = CamoufoxBrowser(
                browser=None,
                context=browser_context,
                camoufox_instance=camoufox,
            )
            browser_obj.user_data_path = profile_dir or ""

            set_browser_session(browser_obj, page_obj)
            _note_start_success()

            if log_callback and profile_dir:
                log_callback(f"[Debug] 当前浏览器资料目录: {profile_dir}")
            if log_callback:
                eip = get_exit_ip()
                bpx = get_bound_proxy()
                meta = str(getattr(_tls, "exit_meta", "") or "")
                if eip or bpx:
                    extra = f" | {meta}" if meta else ""
                    log_callback(f"[*] 出口IP={eip or '?'} 代理={redact_proxy(bpx) or '?'}{extra}")
            if log_callback and attempt > 1:
                log_callback(f"[*] 浏览器第 {attempt} 次启动成功")
            return browser_obj, page_obj
        except Exception as exc:
            last_exc = exc
            streak = _note_start_failure()
            if log_callback:
                log_callback(
                    f"[Debug] 浏览器启动失败(第{attempt}/4次, 连续失败{streak}): {redact_log_line(str(exc))}"
                )
            # 同一 sticky 出口探测失败：再试 3 次无意义，交给上层换口
            msg = str(exc)
            if (
                "无法解析出口 IP" in msg
                or "Failed to get IP address" in msg
                or "代理不可用或过慢" in msg
                or "出口IP命中黑名单" in msg
            ):
                break
            profile_dir = profile_dir or getattr(_tls, "profile_dir", None)
            try:
                cur = active_browser()
                if cur is not None:
                    cur.quit(del_data=True)
            except Exception:
                pass
            set_browser_session(None, None)
            _cleanup_profile_dir(profile_dir)
            time.sleep(min(1.5 * attempt, 4))
    raise Exception(f"浏览器启动失败，已重试4次: {last_exc}")


def stop_browser(force=False):
    if _debug() and not force:
        return
    current = active_browser()
    profile_dir = getattr(_tls, "profile_dir", None)
    set_browser_session(None, None)
    if current is None:
        _cleanup_profile_dir(profile_dir)
        return
    try:
        current.quit(del_data=True)
    except BaseException:
        pass
    _cleanup_profile_dir(profile_dir)


def restart_browser(log_callback=None):
    stop_browser(force=True)
    return start_browser(log_callback=log_callback)


def cleanup_runtime_memory(log_callback=None, reason="定期清理"):
    try:
        if _debug():
            if log_callback:
                log_callback(f"[*] 调试模式：保留浏览器（{reason}）")
            collected = gc.collect()
            if log_callback:
                log_callback(f"[*] Python GC 已回收对象数: {collected}")
            return
        if log_callback:
            log_callback(f"[*] {reason}: 关闭浏览器并清理内存")
        stop_browser(force=True)
        collected = gc.collect()
        if log_callback:
            log_callback(f"[*] Python GC 已回收对象数: {collected}")
    except BaseException:
        try:
            if not _debug():
                stop_browser(force=True)
        except BaseException:
            pass


def refresh_active_page():
    if active_browser() is None:
        restart_browser()
    try:
        browser_obj = active_browser()
        tabs = browser_obj.get_tabs()
        page_obj = tabs[-1] if tabs else browser_obj.new_tab()
        set_browser_session(browser_obj, page_obj)
    except Exception:
        restart_browser()
    return page


def extract_cf_clearance_and_ua(log_callback=None, ensure_grok=True):
    """提取 grok.com 域 cf_clearance + UA。"""
    cf_clearance = ""
    user_agent = ""
    try:
        active = refresh_active_page()
        if active is None:
            return "", ""

        def _read_cf_and_ua(page_obj, grok_only=False):
            clearance = ""
            ua_text = ""
            cookies = page_obj.cookies(all_domains=True, all_info=True) or []
            for item in cookies:
                if isinstance(item, dict):
                    name = str(item.get("name", "")).strip()
                    value = str(item.get("value", "")).strip()
                    domain = str(item.get("domain", "")).strip().lower()
                else:
                    name = str(getattr(item, "name", "")).strip()
                    value = str(getattr(item, "value", "")).strip()
                    domain = str(getattr(item, "domain", "")).strip().lower()
                if name != "cf_clearance" or not value:
                    continue
                if grok_only and "grok.com" not in domain:
                    continue
                if "grok.com" in domain:
                    clearance = value
                    break
                if not clearance and not grok_only:
                    clearance = value
            try:
                ua = page_obj.run_js("return navigator.userAgent;")
                if ua:
                    ua_text = str(ua).strip()
            except Exception:
                pass
            return clearance, ua_text

        def _page_passed_cf(page_obj):
            try:
                title = str(
                    page_obj.run_js("return document.title || '';") or ""
                ).lower()
                body = str(
                    page_obj.run_js(
                        "return (document.body && (document.body.innerText||'')) || '';"
                    )
                    or ""
                ).lower()
                if "just a moment" in title or "just a moment" in body[:200]:
                    return False
                if "checking your browser" in body[:300]:
                    return False
                return True
            except Exception:
                return False

        cf_clearance, user_agent = _read_cf_and_ua(active, grok_only=True)
        if ensure_grok and not cf_clearance:
            if log_callback:
                log_callback("[*] 未找到 grok.com 的 cf_clearance，打开 grok.com 过盾...")
            try:
                active.get("https://grok.com/")
                try:
                    active.wait.doc_loaded()
                except Exception:
                    pass
                time.sleep(2)
                for _ in range(20):
                    if _page_passed_cf(active):
                        cf_clearance, user_agent = _read_cf_and_ua(
                            active, grok_only=True
                        )
                        if cf_clearance:
                            break
                    time.sleep(1.0)
                if log_callback:
                    if cf_clearance:
                        log_callback("[*] 已取得 grok.com 的 cf_clearance")
                    else:
                        log_callback(
                            "[!] 打开 grok.com 后仍无有效 cf_clearance"
                            "（页面可能仍卡在 Just a moment）"
                        )
            except Exception as nav_exc:
                if log_callback:
                    log_callback(f"[Debug] 打开 grok.com 取 cf_clearance 失败: {nav_exc}")
                cf_clearance, user_agent = _read_cf_and_ua(active, grok_only=True)
    except Exception as exc:
        if log_callback:
            log_callback(f"[Debug] 提取 cf_clearance 失败: {exc}")
    return cf_clearance, user_agent
