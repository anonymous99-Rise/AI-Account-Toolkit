"""Persistent ASN blacklist state stored as data, never executable source."""

from __future__ import annotations

import json
import os
import re
import time
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
        "BLACKLIST_STATE_FILE",
        str(ROOT / "log" / "blacklist_state.json"),
    )
)
LOCK_PATH = STATE_PATH.with_suffix(STATE_PATH.suffix + ".lock")

BASELINE_ITEMS = {
    5650: "Frontier Communications",
    7922: "Comcast Cable",
}
BASELINE_ISP_KEYWORDS = (
    "comcast cable",
    "comcast ip services",
    "frontier communications",
)
MAX_ASN = 4_294_967_295


def sanitize_note(value: object, limit: int = 120) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _normalize_asn(value: object) -> int:
    asn = int(value)
    if not 1 <= asn <= MAX_ASN:
        raise ValueError(f"ASN out of range: {asn}")
    return asn


def _default_state(mode: str = "baseline") -> dict:
    if mode == "empty":
        items = []
        keywords = []
    else:
        items = [
            {"asn": asn, "note": note, "source": "baseline"}
            for asn, note in sorted(BASELINE_ITEMS.items())
        ]
        keywords = list(BASELINE_ISP_KEYWORDS)
    return {
        "version": 1,
        "items": items,
        "isp_keywords": keywords,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _normalize_state(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("blacklist state must be an object")
    items_by_asn: dict[int, dict] = {}
    for item in raw.get("items") or []:
        if not isinstance(item, dict):
            continue
        asn = _normalize_asn(item.get("asn"))
        items_by_asn[asn] = {
            "asn": asn,
            "note": sanitize_note(item.get("note")),
            "source": sanitize_note(item.get("source") or "runtime", 32),
        }
    keywords = []
    for value in raw.get("isp_keywords") or []:
        keyword = sanitize_note(value, 80).lower()
        if keyword and keyword not in keywords:
            keywords.append(keyword)
    return {
        "version": 1,
        "items": [items_by_asn[key] for key in sorted(items_by_asn)],
        "isp_keywords": keywords,
        "updated_at": sanitize_note(raw.get("updated_at"), 40)
        or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _read_unlocked() -> tuple[dict, list[str]]:
    if not STATE_PATH.exists():
        return _default_state(), []
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8") or "{}")
        return _normalize_state(raw), []
    except Exception as exc:
        return _default_state(), [f"state: {exc}"]


def read_blacklist() -> dict:
    with exclusive_file_lock(LOCK_PATH):
        state, errors = _read_unlocked()
    try:
        mtime = STATE_PATH.stat().st_mtime
    except OSError:
        mtime = None
    items = [
        {
            "asn": item["asn"],
            "label": f"AS{item['asn']}",
            "note": item.get("note") or "",
            "source": item.get("source") or "runtime",
        }
        for item in state["items"]
    ]
    return {
        "ok": not errors,
        "error": errors[0] if errors else None,
        "errors": errors,
        "count": len(items),
        "asns": [item["asn"] for item in items],
        "items": items,
        "isp_keywords": list(state["isp_keywords"]),
        "mtime": mtime,
        "mtime_human": (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
            if mtime
            else None
        ),
        "source": str(STATE_PATH),
    }


def add_asn(asn: object, note: object = "", source: str = "auto") -> bool:
    normalized_asn = _normalize_asn(asn)
    with exclusive_file_lock(LOCK_PATH):
        state, _ = _read_unlocked()
        existing = {item["asn"]: item for item in state["items"]}
        if normalized_asn in existing:
            return False
        existing[normalized_asn] = {
            "asn": normalized_asn,
            "note": sanitize_note(note),
            "source": sanitize_note(source, 32) or "auto",
        }
        state["items"] = [existing[key] for key in sorted(existing)]
        state["updated_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        atomic_write_json(STATE_PATH, _normalize_state(state))
    return True


def reset_blacklist(mode: str = "baseline") -> dict:
    normalized_mode = str(mode or "baseline").strip().lower()
    if normalized_mode not in ("baseline", "empty"):
        return {"ok": False, "error": f"unknown mode {normalized_mode}"}
    before = read_blacklist()
    with exclusive_file_lock(LOCK_PATH):
        atomic_write_json(STATE_PATH, _default_state(normalized_mode))
    after = read_blacklist()
    return {
        **after,
        "ok": True,
        "mode": normalized_mode,
        "before_count": before.get("count", 0),
        "before_asns": before.get("asns", []),
        "after_count": after.get("count", 0),
        "after_asns": after.get("asns", []),
        "message": (
            "Restored baseline blacklist"
            if normalized_mode == "baseline"
            else "Cleared blacklist"
        ),
    }


def import_legacy_source(source_path: str | os.PathLike[str]) -> dict:
    text = Path(source_path).read_text(encoding="utf-8")
    notes: dict[int, str] = {}
    block = re.search(r"_BLOCKED_ASN_SUBSTR\s*=\s*\((.*?)\)", text, re.S)
    if block:
        for line in block.group(1).splitlines():
            match = re.search(r'"AS(\d+)"\s*,?\s*(?:#\s*(.*))?', line)
            if match:
                notes[int(match.group(1))] = sanitize_note(match.group(2))
    nums = set(notes)
    number_block = re.search(r"_BLOCKED_ASN_NUMS\s*=\s*\{([^}]*)\}", text)
    if number_block:
        nums.update(int(value) for value in re.findall(r"\d+", number_block.group(1)))
    isp = []
    isp_block = re.search(r"_BLOCKED_ISP_SUBSTR\s*=\s*\((.*?)\)", text, re.S)
    if isp_block:
        isp = [sanitize_note(value, 80).lower() for value in re.findall(r'"([^"]+)"', isp_block.group(1))]
    state = {
        "version": 1,
        "items": [
            {
                "asn": asn,
                "note": notes.get(asn, ""),
                "source": "legacy",
            }
            for asn in sorted(nums)
        ],
        "isp_keywords": isp or list(BASELINE_ISP_KEYWORDS),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with exclusive_file_lock(LOCK_PATH):
        atomic_write_json(STATE_PATH, _normalize_state(state))
    return read_blacklist()
