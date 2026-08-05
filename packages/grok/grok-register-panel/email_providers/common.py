"""邮箱提供商共用工具。"""

from __future__ import annotations

import re
import random
import string
from typing import Any, List, Optional


def generate_username(length: int = 10) -> str:
    """更像真人的邮箱本地部分（无 tmp 前缀、避免纯随机串）。"""
    first = random.choice([
        "james", "john", "robert", "michael", "david", "william", "richard",
        "mary", "patricia", "jennifer", "linda", "emily", "sarah", "emma",
        "daniel", "matthew", "andrew", "joshua", "ryan", "justin", "brandon",
        "anna", "amy", "olivia", "hannah", "grace", "chloe", "lily", "noah",
    ])
    last = random.choice([
        "smith", "johnson", "williams", "brown", "jones", "garcia", "miller",
        "davis", "wilson", "anderson", "thomas", "taylor", "moore", "jackson",
        "martin", "lee", "clark", "lewis", "walker", "hall", "young", "king",
        "wright", "scott", "green", "baker", "adams", "nelson", "carter",
    ])
    n = random.randint(0, 99)
    patterns = [
        f"{first}.{last}",
        f"{first}{last}",
        f"{first}.{last}{n}",
        f"{first}{n}",
        f"{first}_{last}",
        f"{first[0]}{last}{n}",
        f"{first}{last[0]}{random.randint(10, 99)}",
    ]
    name = random.choice(patterns)
    name = "".join(ch for ch in name if ch.isalnum() or ch in "._-")
    return (name[:30] or f"{first}{random.randint(10, 99)}")


def pick_list_payload(data: Any) -> List[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("results"), list):
            return [item for item in data["results"] if isinstance(item, dict)]
        if isinstance(data.get("hydra:member"), list):
            return [item for item in data["hydra:member"] if isinstance(item, dict)]
        if isinstance(data.get("data"), list):
            return [item for item in data["data"] if isinstance(item, dict)]
        if isinstance(data.get("messages"), list):
            return [item for item in data["messages"] if isinstance(item, dict)]
        if isinstance(data.get("data"), dict):
            nested = data.get("data") or {}
            if isinstance(nested.get("messages"), list):
                return [item for item in nested["messages"] if isinstance(item, dict)]
    return []


# xAI 邮件验证码：XXX-YYY（如 QO7-TUD / CXX-PC2 / XSB-802）
_CODE_RE = re.compile(r"\b([A-Za-z0-9]{3}-[A-Za-z0-9]{3})\b")

# CloudMail / 邮件模板 HTML 常见左词（per-100、max-100…）
_BAD_LEFT = {
    "per", "max", "min", "top", "all", "col", "row", "box", "pad", "gap",
    "pre", "sub", "new", "old", "use", "set", "get", "app", "web", "api",
    "css", "img", "src", "div", "span", "flex", "grid", "auto", "full",
    "half", "one", "two", "low", "mid", "end", "fit", "fix", "var",
    "eml", "htm", "pdf", "png", "jpg", "gif", "svg", "btn", "nav",
    "tab", "mod", "pop", "tip", "tag", "key", "val", "num", "pct",
}
_BAD_TOKENS = {
    "per-100", "max-100", "min-100", "top-100", "all-100",
    "col-100", "row-100", "box-100", "pad-100", "gap-100",
}


def _normalize_code(code: str) -> str:
    return str(code or "").strip().upper()


def _is_plausible_xai_code(code: str) -> bool:
    """过滤邮件 HTML/模板伪验证码（如 per-100）。

    真码也可能是「三字母-三数字」(XSB-802)，不能整类 letter-digit 干掉；
    只拦模板常见左词 + 黑名单 token。
    """
    if not code or "-" not in code:
        return False
    raw = code.strip()
    if raw.lower() in _BAD_TOKENS:
        return False
    left, _, right = raw.partition("-")
    if len(left) != 3 or len(right) != 3:
        return False
    if not (left.isalnum() and right.isalnum()):
        return False
    if left.isdigit() and right.isdigit():
        return False
    if left.isalpha() and right.isdigit() and left.lower() in _BAD_LEFT:
        return False
    return True


def _score_code(code: str, hay: str, index: int) -> int:
    """上下文打分：靠近 xAI / verification / code 优先。"""
    score = 0
    c = code.upper()
    if any(ch.isalpha() for ch in c) and any(ch.isdigit() for ch in c):
        score += 3
    parts = c.split("-")
    if len(parts) == 2 and any(ch.isalpha() for ch in parts[0]) and any(ch.isalpha() for ch in parts[1]):
        score += 1
    window = hay[max(0, index - 48): index + len(code) + 48].lower()
    for kw, pts in (
        ("xai", 8),
        ("verification", 6),
        ("verify", 5),
        ("one-time", 5),
        ("one time", 5),
        ("security code", 6),
        ("your code", 5),
        ("code is", 4),
        ("code:", 4),
        ("确认码", 6),
        ("验证码", 6),
    ):
        if kw in window:
            score += pts
    for bad in ("class=", "stylesheet", "width:", "percent", "padding", "margin"):
        if bad in window:
            score -= 4
    return score


def extract_verification_code(text: str, subject: str = "") -> Optional[str]:
    """从主题/正文提取 xAI 邮件验证码（形如 XXX-YYY）。

    CloudMail 等会把管理后台 HTML（含 per-100 等 class）拼进正文；
    旧逻辑取「第一个 XXX-YYY」会误把 per-100 当成验证码。
    """
    subject = subject or ""
    text = text or ""

    m = re.search(r"^([A-Za-z0-9]{3}-[A-Za-z0-9]{3})\s+xAI\b", subject, re.IGNORECASE)
    if m and _is_plausible_xai_code(m.group(1)):
        return _normalize_code(m.group(1))

    for pat in (
        r"\b([A-Za-z0-9]{3}-[A-Za-z0-9]{3})\b\s*xAI\b",
        r"\bxAI\b[^\n]{0,48}\b([A-Za-z0-9]{3}-[A-Za-z0-9]{3})\b",
        r"(?:verification|security|confirm(?:ation)?)\s+code[:\s]+([A-Za-z0-9]{3}-[A-Za-z0-9]{3})\b",
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m and _is_plausible_xai_code(m.group(1)):
            return _normalize_code(m.group(1))

    hay = f"{subject}\n{text}"
    best = None
    best_score = -10**9
    for m in _CODE_RE.finditer(hay):
        cand = m.group(1)
        if not _is_plausible_xai_code(cand):
            continue
        sc = _score_code(cand, hay, m.start())
        if sc > best_score:
            best_score = sc
            best = cand
    if best:
        return _normalize_code(best)

    for pattern in (
        r"verification\s+code[:\s]+(\d{4,8})",
        r"your\s+code[:\s]+(\d{4,8})",
        r"confirm(?:ation)?\s+code[:\s]+(\d{4,8})",
        r"验证码[：:\s]+(\d{4,8})",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def random_subdomain_domain(apex: str) -> str:
    """在 apex 下生成一次性子域名，降低根域被批量标记的权重。"""
    apex = str(apex or "").strip().lower().lstrip("@")
    if not apex or "." not in apex:
        return apex
    parts = apex.split(".")
    label = "".join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(6, 10)))
    if random.random() < 0.35:
        word = random.choice([
            "mail", "inbox", "box", "get", "app", "go", "my", "use", "fast", "safe",
            "home", "note", "post", "send", "hub", "net", "lab", "pro",
        ])
        label = f"{word}{random.randint(10, 99)}"
    if len(parts) >= 3:
        parts[0] = label
        return ".".join(parts)
    return f"{label}.{apex}"
