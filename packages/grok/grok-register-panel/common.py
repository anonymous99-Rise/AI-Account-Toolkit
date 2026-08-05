"""邮箱提供商共用工具。"""

from __future__ import annotations

import re
import secrets
import string
from typing import Any, List, Optional


def generate_username(length: int = 10) -> str:
    """更像真人的邮箱本地部分（无 tmp 前缀、避免纯随机串）。"""
    import random
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


def extract_verification_code(text: str, subject: str = "") -> Optional[str]:
    if subject:
        match = re.search(r"^([A-Z0-9]{3}-[A-Z0-9]{3})\s+xAI", subject, re.IGNORECASE)
        if match:
            return match.group(1)
    match = re.search(r"\b([A-Z0-9]{3}-[A-Z0-9]{3})\b", text or "", re.IGNORECASE)
    if match:
        return match.group(1)
    patterns = [
        r"verification\s+code[:\s]+(\d{4,8})",
        r"your\s+code[:\s]+(\d{4,8})",
        r"confirm(?:ation)?\s+code[:\s]+(\d{4,8})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "", re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def random_subdomain_domain(apex: str) -> str:
    """在 apex 下生成一次性子域名，降低根域被批量标记的权重。

    例: example.com -> k7m2qx.example.com
    若已是子域 (a.b.com) 则仍在最左侧再挂一层随机标签。
    """
    import random
    import string
    apex = str(apex or "").strip().lower().lstrip("@")
    if not apex or "." not in apex:
        return apex
    # 避免重复叠太多层：若已有 >=3 段，只替换最左标签
    parts = apex.split(".")
    label = "".join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(6, 10)))
    # 更像普通子域：偶尔用词根
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
