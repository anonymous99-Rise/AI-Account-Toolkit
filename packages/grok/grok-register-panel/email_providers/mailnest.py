"""MailNest（迈巢）Outlook 临时邮箱。"""

from __future__ import annotations

import time
from typing import Any, Callable, List, Optional

from email_providers.common import extract_verification_code

API_BASE = "https://mailnest.top"
DEFAULT_PROJECT_CODE = "x-ai001"

HttpPost = Callable[..., Any]


def buy_email(http_post: HttpPost, api_key: str, project_code: str = "") -> str:
    code = (project_code or "").strip() or DEFAULT_PROJECT_CODE
    key = (api_key or "").strip()
    if not key:
        raise Exception(f"请在配置文件中配置 mailnest_api_key | 注册网址：{API_BASE}")
    resp = http_post(
        f"{API_BASE}/api/v1/email/temporary/buy",
        headers={"Authorization": f"Bearer {key}"},
        json={"project_code": code, "count": 1},
        timeout=30,
    )
    try:
        resp_json = resp.json()
    except Exception as exc:
        raise Exception(f"MailNest 买号响应无效: {exc}; body={resp.text[:300]}") from exc
    if str(resp_json.get("code")) != "00000":
        raise Exception(f"MailNest 买号失败: {resp.text[:500]}")
    data = resp_json.get("data") or []
    if not data or not data[0].get("email"):
        raise Exception(f"MailNest 买号无邮箱: {resp.text[:500]}")
    return data[0]["email"]


def receive_email(http_post: HttpPost, api_key: str, email: str) -> List[dict]:
    key = (api_key or "").strip()
    if not key:
        raise Exception(f"请在配置文件中配置 mailnest_api_key | 注册网址：{API_BASE}")
    resp = http_post(
        f"{API_BASE}/api/v1/email/receive",
        headers={"Authorization": f"Bearer {key}"},
        json={"email": email},
        timeout=30,
    )
    try:
        resp_json = resp.json()
    except Exception as exc:
        raise Exception(f"MailNest 收信响应无效: {exc}; body={resp.text[:300]}") from exc
    if str(resp_json.get("code")) != "00000":
        raise Exception(f"MailNest 收信失败: {resp.text[:500]}")
    return resp_json.get("data") or []


def wait_for_code(
    http_post: HttpPost,
    api_key: str,
    email: str,
    *,
    timeout: int = 180,
    poll_interval: int = 3,
    raise_if_cancelled: Callable[[Optional[Callable[[], bool]]], None],
    sleep_with_cancel: Callable[[float, Optional[Callable[[], bool]]], None],
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> str:
    deadline = time.time() + timeout
    seen = set()
    while time.time() < deadline:
        raise_if_cancelled(cancel_callback)
        try:
            mails = receive_email(http_post, api_key, email)
        except Exception as exc:
            if log_callback:
                log_callback(f"[Debug] MailNest 拉取邮件失败: {exc}")
            sleep_with_cancel(poll_interval, cancel_callback)
            continue
        for mail in mails or []:
            if not isinstance(mail, dict):
                continue
            mail_id = str(mail.get("id") or mail.get("message_id") or "")
            preview = str(mail.get("body_preview") or mail.get("text") or mail.get("body") or "")
            subject = str(mail.get("subject") or "")
            fingerprint = mail_id or f"{subject}|{preview[:80]}"
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            if log_callback:
                log_callback(f"[Debug] MailNest 收到邮件: {subject or fingerprint}")
            code = extract_verification_code(f"{subject}\n{preview}", subject)
            if code:
                if log_callback:
                    log_callback(f"[*] MailNest 从邮件中提取到验证码: {code}")
                return code
        sleep_with_cancel(poll_interval, cancel_callback)
    raise Exception(f"MailNest 在 {timeout}s 内未收到验证码邮件")
