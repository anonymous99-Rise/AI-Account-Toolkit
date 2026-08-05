"""Persistent provider-bound email domain pool and rejection blacklist."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from secure_files import atomic_write_json, exclusive_file_lock
except ImportError:  # running from webui/
    import sys

    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from secure_files import atomic_write_json, exclusive_file_lock


ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = Path(
    os.environ.get(
        "EMAIL_DOMAIN_POOL_STATE_FILE",
        str(ROOT / "log" / "email_domain_pool.json"),
    )
)
LOCK_PATH = STATE_PATH.with_suffix(STATE_PATH.suffix + ".lock")

SUPPORTED_PROVIDERS = ("cloudflare", "cloudmail", "moemail", "yyds")
PROVIDER_LABELS = {
    "cloudflare": "Cloudflare",
    "cloudmail": "CloudMail",
    "moemail": "MoeMail",
    "yyds": "YYDS",
}
MAX_IMPORT_ITEMS = 500
MAX_ACTIVE_LIMIT = 100
DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_MAX_ACTIVE_DOMAINS = 0


class EmailDomainValidationError(ValueError):
    pass


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _clean_text(value: object, limit: int = 180) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def normalize_provider(value: object) -> str:
    provider = str(value or "").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        allowed = "、".join(PROVIDER_LABELS[item] for item in SUPPORTED_PROVIDERS)
        raise EmailDomainValidationError(f"邮箱服务仅支持 {allowed}")
    return provider


def normalize_domain(value: object) -> str:
    raw = str(value or "").strip().lower().rstrip(".")
    if raw.startswith("@"):
        raw = raw[1:]
    if not raw:
        raise EmailDomainValidationError("域名为空")
    if any(char.isspace() for char in raw):
        raise EmailDomainValidationError("域名不能包含空白字符")
    if any(marker in raw for marker in ("://", "/", "\\", "@", "*", ":")):
        raise EmailDomainValidationError("请输入域名，不要填写邮箱、URL、通配符或端口")
    try:
        domain = raw.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise EmailDomainValidationError("域名编码无效") from exc
    if len(domain) > 253 or "." not in domain:
        raise EmailDomainValidationError("域名必须包含有效后缀")
    labels = domain.split(".")
    label_pattern = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    if any(not label_pattern.fullmatch(label) for label in labels):
        raise EmailDomainValidationError("域名标签格式无效")
    if labels[-1].isdigit():
        raise EmailDomainValidationError("域名后缀不能是纯数字")
    return domain


def _domain_id(provider: str, domain: str) -> str:
    return hashlib.sha256(f"{provider}:{domain}".encode("utf-8")).hexdigest()[:20]


def _default_settings() -> dict:
    return {
        "failure_threshold": DEFAULT_FAILURE_THRESHOLD,
        "max_active_domains": DEFAULT_MAX_ACTIVE_DOMAINS,
    }


def _normalize_settings(raw: object) -> dict:
    source = raw if isinstance(raw, dict) else {}
    threshold = _safe_int(
        source.get("failure_threshold"), DEFAULT_FAILURE_THRESHOLD
    )
    max_active = _safe_int(
        source.get("max_active_domains"), DEFAULT_MAX_ACTIVE_DOMAINS
    )
    if not 1 <= threshold <= 20:
        threshold = DEFAULT_FAILURE_THRESHOLD
    if not 0 <= max_active <= MAX_ACTIVE_LIMIT:
        max_active = DEFAULT_MAX_ACTIVE_DOMAINS
    return {
        "failure_threshold": threshold,
        "max_active_domains": max_active,
    }


def _default_state() -> dict:
    return {
        "version": 1,
        "settings": _default_settings(),
        "items": [],
        "updated_at": _utc_now(),
    }


def _normalize_item(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    try:
        provider = normalize_provider(raw.get("provider"))
        domain = normalize_domain(raw.get("domain"))
    except EmailDomainValidationError:
        return None
    return {
        "id": _domain_id(provider, domain),
        "provider": provider,
        "domain": domain,
        "enabled": bool(raw.get("enabled", True)),
        "consecutive_rejections": _safe_int(raw.get("consecutive_rejections")),
        "total_rejections": _safe_int(raw.get("total_rejections")),
        "success_count": _safe_int(raw.get("success_count")),
        "use_count": _safe_int(raw.get("use_count")),
        "last_used_at": _clean_text(raw.get("last_used_at"), 40),
        "last_success_at": _clean_text(raw.get("last_success_at"), 40),
        "last_rejected_at": _clean_text(raw.get("last_rejected_at"), 40),
        "last_error": _clean_text(raw.get("last_error"), 180),
        "blocked_at": _clean_text(raw.get("blocked_at"), 40),
        "source": _clean_text(raw.get("source") or "panel", 32),
        "created_at": _clean_text(raw.get("created_at"), 40) or _utc_now(),
    }


def _normalize_state(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("email domain pool state must be an object")
    settings = _normalize_settings(raw.get("settings"))
    items_by_id = {}
    for candidate in raw.get("items") or []:
        item = _normalize_item(candidate)
        if item:
            if item["consecutive_rejections"] >= settings["failure_threshold"]:
                item["blocked_at"] = item["blocked_at"] or _utc_now()
            else:
                item["blocked_at"] = ""
            items_by_id[item["id"]] = item
    return {
        "version": 1,
        "settings": settings,
        "items": list(items_by_id.values()),
        "updated_at": _clean_text(raw.get("updated_at"), 40) or _utc_now(),
    }


def _read_unlocked() -> tuple[dict, list[str]]:
    if not STATE_PATH.exists():
        return _default_state(), []
    try:
        import json

        raw = json.loads(STATE_PATH.read_text(encoding="utf-8") or "{}")
        return _normalize_state(raw), []
    except Exception as exc:
        return _default_state(), [_clean_text(exc)]


def _state_for_update() -> dict:
    state, errors = _read_unlocked()
    if errors:
        raise RuntimeError(f"邮箱域名池状态无法读取: {errors[0]}")
    return state


def _write_unlocked(state: dict) -> None:
    state["updated_at"] = _utc_now()
    atomic_write_json(STATE_PATH, _normalize_state(state))


def _active_ids(state: dict, provider: str | None = None) -> set[str]:
    threshold = state["settings"]["failure_threshold"]
    max_active = state["settings"]["max_active_domains"]
    active = set()
    providers = (provider,) if provider else SUPPORTED_PROVIDERS
    for current_provider in providers:
        eligible = [
            item
            for item in state["items"]
            if item["provider"] == current_provider
            and item["enabled"]
            and item["consecutive_rejections"] < threshold
        ]
        if max_active > 0:
            eligible = eligible[:max_active]
        active.update(item["id"] for item in eligible)
    return active


def _effective_status(item: dict, state: dict, active_ids: set[str]) -> str:
    if not item["enabled"]:
        return "disabled"
    if item["consecutive_rejections"] >= state["settings"]["failure_threshold"]:
        return "blocked"
    if item["id"] in active_ids:
        return "active"
    return "standby"


def _public_item(item: dict, state: dict, active_ids: set[str]) -> dict:
    return {
        **item,
        "provider_label": PROVIDER_LABELS[item["provider"]],
        "status": _effective_status(item, state, active_ids),
        "failure_threshold": state["settings"]["failure_threshold"],
    }


def read_email_domain_pool() -> dict:
    with exclusive_file_lock(LOCK_PATH):
        state, errors = _read_unlocked()
    active_ids = _active_ids(state)
    items = [_public_item(item, state, active_ids) for item in state["items"]]
    statuses = [item["status"] for item in items]
    providers = {
        provider: sum(1 for item in items if item["provider"] == provider)
        for provider in SUPPORTED_PROVIDERS
    }
    try:
        mtime = STATE_PATH.stat().st_mtime
    except OSError:
        mtime = None
    return {
        "ok": not errors,
        "error": errors[0] if errors else None,
        "errors": errors,
        "settings": dict(state["settings"]),
        "summary": {
            "total": len(items),
            "active": statuses.count("active"),
            "standby": statuses.count("standby"),
            "blocked": statuses.count("blocked"),
            "disabled": statuses.count("disabled"),
            "enabled": sum(1 for item in items if item["enabled"]),
        },
        "providers": providers,
        "provider_labels": dict(PROVIDER_LABELS),
        "items": items,
        "updated_at": state["updated_at"],
        "mtime": mtime,
    }


def _input_lines(values: object) -> list[str]:
    if isinstance(values, str):
        return values.splitlines()
    if isinstance(values, (list, tuple)):
        return [str(value or "") for value in values]
    return []


def import_domains(values: object, provider: object, *, source: str = "panel") -> dict:
    normalized_provider = normalize_provider(provider)
    candidates = []
    errors = []
    seen = set()
    duplicate_count = 0
    for line_number, line in enumerate(_input_lines(values), 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if len(candidates) >= MAX_IMPORT_ITEMS:
            errors.append(
                {"line": line_number, "error": f"单次最多导入 {MAX_IMPORT_ITEMS} 条"}
            )
            break
        try:
            domain = normalize_domain(text)
        except EmailDomainValidationError as exc:
            errors.append({"line": line_number, "error": str(exc)})
            continue
        if domain in seen:
            duplicate_count += 1
            continue
        seen.add(domain)
        candidates.append(domain)

    if not candidates:
        return {
            "ok": False,
            "error": "没有可导入的有效域名",
            "errors": errors,
            "imported_count": 0,
            "duplicate_count": duplicate_count,
        }

    imported_ids = []
    with exclusive_file_lock(LOCK_PATH):
        state = _state_for_update()
        existing = {item["id"]: item for item in state["items"]}
        for domain in candidates:
            item_id = _domain_id(normalized_provider, domain)
            if item_id in existing:
                duplicate_count += 1
                continue
            item = _normalize_item(
                {
                    "provider": normalized_provider,
                    "domain": domain,
                    "enabled": True,
                    "source": source,
                    "created_at": _utc_now(),
                }
            )
            if item:
                existing[item_id] = item
                imported_ids.append(item_id)
        state["items"] = list(existing.values())
        _write_unlocked(state)

    result = read_email_domain_pool()
    result.update(
        {
            "ok": True,
            "imported_count": len(imported_ids),
            "duplicate_count": duplicate_count,
            "imported_ids": imported_ids,
            "errors": errors,
        }
    )
    return result


def update_settings(
    *,
    failure_threshold: object | None = None,
    max_active_domains: object | None = None,
) -> dict:
    with exclusive_file_lock(LOCK_PATH):
        state = _state_for_update()
        settings = dict(state["settings"])
        if failure_threshold is not None:
            try:
                threshold = int(failure_threshold)
            except (TypeError, ValueError) as exc:
                raise EmailDomainValidationError("失败阈值必须是整数") from exc
            if not 1 <= threshold <= 20:
                raise EmailDomainValidationError("失败阈值必须在 1-20 之间")
            settings["failure_threshold"] = threshold
        if max_active_domains is not None:
            try:
                max_active = int(max_active_domains)
            except (TypeError, ValueError) as exc:
                raise EmailDomainValidationError("最大活跃数必须是整数") from exc
            if not 0 <= max_active <= MAX_ACTIVE_LIMIT:
                raise EmailDomainValidationError(
                    f"最大活跃数必须在 0-{MAX_ACTIVE_LIMIT} 之间"
                )
            settings["max_active_domains"] = max_active
        state["settings"] = settings
        _write_unlocked(state)
    return read_email_domain_pool()


def update_domain(domain_id: str, *, enabled: object | None = None) -> dict:
    domain_id = str(domain_id or "").strip()
    found = False
    with exclusive_file_lock(LOCK_PATH):
        state = _state_for_update()
        for item in state["items"]:
            if item["id"] != domain_id:
                continue
            found = True
            if enabled is not None:
                if not isinstance(enabled, bool):
                    raise EmailDomainValidationError("enabled 必须是布尔值")
                item["enabled"] = enabled
            break
        if not found:
            return {"ok": False, "error": "邮箱域名不存在"}
        _write_unlocked(state)
    return read_email_domain_pool()


def reset_domain(domain_id: str) -> dict:
    domain_id = str(domain_id or "").strip()
    found = False
    with exclusive_file_lock(LOCK_PATH):
        state = _state_for_update()
        for item in state["items"]:
            if item["id"] != domain_id:
                continue
            found = True
            item["consecutive_rejections"] = 0
            item["total_rejections"] = 0
            item["last_rejected_at"] = ""
            item["last_error"] = ""
            item["blocked_at"] = ""
            break
        if not found:
            return {"ok": False, "error": "邮箱域名不存在"}
        _write_unlocked(state)
    return read_email_domain_pool()


def delete_domain(domain_id: str) -> dict:
    domain_id = str(domain_id or "").strip()
    with exclusive_file_lock(LOCK_PATH):
        state = _state_for_update()
        before = len(state["items"])
        state["items"] = [
            item for item in state["items"] if item["id"] != domain_id
        ]
        if len(state["items"]) == before:
            return {"ok": False, "error": "邮箱域名不存在"}
        _write_unlocked(state)
    result = read_email_domain_pool()
    result["deleted_id"] = domain_id
    return result


def select_domain(provider: object) -> dict:
    """Select one managed domain. Existing provider config remains the fallback."""
    normalized_provider = normalize_provider(provider)
    with exclusive_file_lock(LOCK_PATH):
        state = _state_for_update()
        provider_items = [
            item for item in state["items"] if item["provider"] == normalized_provider
        ]
        if not provider_items:
            return {
                "configured": False,
                "provider": normalized_provider,
                "domain": "",
                "id": "",
            }
        active_ids = _active_ids(state, normalized_provider)
        candidates = [item for item in provider_items if item["id"] in active_ids]
        if not candidates:
            return {
                "configured": True,
                "provider": normalized_provider,
                "domain": "",
                "id": "",
            }
        selected = min(
            candidates,
            key=lambda item: (
                item["use_count"],
                item["last_used_at"] or "",
                item["domain"],
            ),
        )
        selected["use_count"] += 1
        selected["last_used_at"] = _utc_now()
        _write_unlocked(state)
        return {
            "configured": True,
            "provider": normalized_provider,
            "domain": selected["domain"],
            "id": selected["id"],
        }


def record_domain_result(
    provider: object,
    email_or_domain: object,
    outcome: str,
    error: object = "",
) -> dict:
    normalized_provider = normalize_provider(provider)
    raw = str(email_or_domain or "").strip()
    domain_value = raw.rsplit("@", 1)[-1] if "@" in raw else raw
    try:
        domain = normalize_domain(domain_value)
    except EmailDomainValidationError:
        return {"matched": False, "blocked": False}
    normalized_outcome = str(outcome or "").strip().lower()
    if normalized_outcome not in {"accepted", "rejected"}:
        raise ValueError(f"unknown email domain outcome: {normalized_outcome}")

    with exclusive_file_lock(LOCK_PATH):
        state = _state_for_update()
        item = next(
            (
                candidate
                for candidate in state["items"]
                if candidate["provider"] == normalized_provider
                and candidate["domain"] == domain
            ),
            None,
        )
        if item is None:
            return {"matched": False, "blocked": False}
        threshold = state["settings"]["failure_threshold"]
        was_blocked = item["consecutive_rejections"] >= threshold
        if normalized_outcome == "accepted":
            item["consecutive_rejections"] = 0
            item["success_count"] += 1
            item["last_success_at"] = _utc_now()
            item["last_error"] = ""
            item["blocked_at"] = ""
        else:
            item["consecutive_rejections"] += 1
            item["total_rejections"] += 1
            item["last_rejected_at"] = _utc_now()
            item["last_error"] = _clean_text(error) or "xAI 拒绝邮箱域名"
            if item["consecutive_rejections"] >= threshold:
                item["blocked_at"] = item["blocked_at"] or _utc_now()
        blocked = item["consecutive_rejections"] >= threshold
        consecutive = item["consecutive_rejections"]
        _write_unlocked(state)
    return {
        "matched": True,
        "blocked": blocked,
        "newly_blocked": blocked and not was_blocked,
        "provider": normalized_provider,
        "domain": domain,
        "consecutive_rejections": consecutive,
        "failure_threshold": threshold,
    }
