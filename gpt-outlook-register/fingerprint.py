"""浏览器指纹随机化（macOS Safari）。

每次注册调用 generate_fingerprint() 生成一套一致的指纹组合：
  - TLS impersonate（curl_cffi 用）
  - User-Agent（macOS Safari）
  - 屏幕分辨率（Mac 常见分辨率）
  - Accept-Language

Safari 不发送 sec-ch-ua 系列头（Client Hints 是 Chromium 独有），
返回的 sec_ch_ua / sec_ch_ua_platform / sec_ch_ua_mobile 均为空字符串，
调用方据此跳过这些头。
"""
from __future__ import annotations

import random

_SAFARI_VERSIONS = [
    {
        "impersonate": "safari15_3",
        "safari_ver": "15.3",
        "webkit_ver": "605.1.15",
    },
    {
        "impersonate": "safari15_5",
        "safari_ver": "15.5",
        "webkit_ver": "605.1.15",
    },
    {
        "impersonate": "safari17_0",
        "safari_ver": "17.0",
        "webkit_ver": "605.1.15",
    },
    {
        "impersonate": "safari18_0",
        "safari_ver": "18.0",
        "webkit_ver": "605.1.15",
    },
]

_MAC_SCREENS = [
    "1440x900",    # MacBook Air 13"
    "1512x982",    # MacBook Pro 14"
    "1728x1117",   # MacBook Pro 16"
    "2560x1440",   # iMac 27" / 外接显示器
    "1920x1080",   # 外接显示器
]

_LANGUAGES = [
    ("en-US", "en-US,en;q=0.9"),
    ("en-US", "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7"),
    ("en-GB", "en-GB,en;q=0.9,en-US;q=0.8"),
    ("en-US", "en-US,en;q=0.9,ja;q=0.8"),
]


def generate_fingerprint(rng: random.Random | None = None) -> dict:
    """生成一套一致的 macOS Safari 浏览器指纹。

    返回 dict:
        impersonate: str      — curl_cffi TLS 指纹名
        user_agent: str       — 完整 UA 字符串（macOS Safari）
        sec_ch_ua: str        — 空串（Safari 不发 Client Hints）
        sec_ch_ua_platform: str — 空串
        sec_ch_ua_mobile: str — 空串
        screen: str           — 屏幕分辨率 (WxH)
        lang: str             — 主语言 (Accept-Language q=1)
        lang_full: str        — 完整 Accept-Language
    """
    r = rng or random

    safari = r.choice(_SAFARI_VERSIONS)
    screen = r.choice(_MAC_SCREENS)
    lang, lang_full = r.choice(_LANGUAGES)

    user_agent = (
        f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        f"AppleWebKit/{safari['webkit_ver']} (KHTML, like Gecko) "
        f"Version/{safari['safari_ver']} Safari/{safari['webkit_ver']}"
    )

    return {
        "impersonate": safari["impersonate"],
        "user_agent": user_agent,
        "sec_ch_ua": "",
        "sec_ch_ua_platform": "",
        "sec_ch_ua_mobile": "",
        "screen": screen,
        "lang": lang,
        "lang_full": lang_full,
    }
