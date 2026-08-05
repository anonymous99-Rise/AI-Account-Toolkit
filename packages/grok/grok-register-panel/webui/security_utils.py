# -*- coding: utf-8 -*-
"""Security helpers for the live panel and logging redaction."""
from __future__ import annotations

import os
import re
import hmac
from typing import Optional
from urllib.parse import urlparse, urlunparse


def redact_proxy(url: str) -> str:
    """Strip userinfo from proxy URLs. Empty stays empty."""
    s = str(url or "").strip()
    if not s:
        return ""
    # bare host:port:user:pass forms are not full URLs — handle http(s)/socks
    try:
        if "://" not in s:
            # host:port only or host:port:user:pass
            parts = s.split(":")
            if len(parts) >= 4:
                host, port = parts[0], parts[1]
                return f"{host}:{port}:***"
            return s
        p = urlparse(s)
        if p.username or p.password:
            host = p.hostname or ""
            if p.port:
                netloc = f"{host}:{p.port}"
            else:
                netloc = host
            return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))
        return s
    except Exception:
        return re.sub(r"://([^:/@]+):([^@/]+)@", r"://***:***@", s)


def mask_email(email: str) -> str:
    s = str(email or "").strip()
    if not s or "@" not in s:
        return s
    local, _, domain = s.partition("@")
    if len(local) <= 2:
        return f"{local[0]}***@{domain}" if local else f"***@{domain}"
    return f"{local[:2]}***@{domain}"


def extract_bearer(auth_header: Optional[str]) -> str:
    h = str(auth_header or "").strip()
    if not h:
        return ""
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return h


def token_required() -> bool:
    """If MONITOR_TOKEN is set (non-empty), auth is required."""
    return bool(str(os.environ.get("MONITOR_TOKEN", "") or "").strip())


def expected_token() -> str:
    return str(os.environ.get("MONITOR_TOKEN", "") or "").strip()


def check_token(provided: Optional[str]) -> bool:
    """Return True if request is authorized.

    - If MONITOR_TOKEN unset/empty: deny mutations (fail closed for write APIs).
      Callers may treat read-only differently.
    - If set: constant-time-ish equality of bearer token.
    """
    exp = expected_token()
    if not exp:
        return False
    return hmac.compare_digest(extract_bearer(provided), exp)


def check_token_optional_read(provided: Optional[str], *, write: bool) -> bool:
    """Read: allow if no token configured OR token matches.
    Write: require configured token AND match.
    """
    exp = expected_token()
    if write:
        if not exp:
            return False
        return check_token(provided)
    # read
    if not exp:
        return True
    return check_token(provided)


_EMAIL_RE = re.compile(r"(?<![\w.+-])([\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![\w.-])")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\b")
_PROXY_RE = re.compile(r"\b(?:https?|socks5h?)://[^\s]+")
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(access_token|refresh_token|id_token|sso|password|passwd|secret|api_key|management_key|token)"
    r"([\"']?\s*[:=]\s*[\"']?)([^\s,;\"'&]{8,})"
)


def redact_log_line(line: str) -> str:
    """Remove credentials and account identifiers from a display log line."""
    text = _ANSI_RE.sub("", str(line or ""))
    text = _JWT_RE.sub("[redacted-token]", text)
    text = re.sub(
        r"(?i)\b(Bearer\s+)[A-Za-z0-9._~-]{12,}",
        r"\1[redacted]",
        text,
    )
    text = re.sub(
        r"(?i)((?:user_code|verification code|验证码)[^A-Z0-9\r\n]{0,32})[A-Z0-9]{3}-[A-Z0-9]{3}\b",
        r"\1[redacted]",
        text,
    )
    text = _SECRET_VALUE_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[redacted]",
        text,
    )
    text = _EMAIL_RE.sub(lambda match: mask_email(match.group(1)), text)
    text = _PROXY_RE.sub(lambda match: redact_proxy(match.group(0)), text)
    return text
