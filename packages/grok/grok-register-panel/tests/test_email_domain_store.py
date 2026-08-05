# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webui import email_domain_store


class IsolatedStore:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.previous = (
            email_domain_store.STATE_PATH,
            email_domain_store.LOCK_PATH,
        )
        email_domain_store.STATE_PATH = base / "log" / "email_domain_pool.json"
        email_domain_store.LOCK_PATH = base / "log" / "email_domain_pool.json.lock"
        return base

    def __exit__(self, exc_type, exc, tb):
        email_domain_store.STATE_PATH, email_domain_store.LOCK_PATH = self.previous
        self.temp.cleanup()


def assert_invalid(value: str):
    try:
        email_domain_store.normalize_domain(value)
    except email_domain_store.EmailDomainValidationError:
        return
    raise AssertionError(f"expected invalid domain: {value}")


def test_normalize_import_deduplicate_and_private_state():
    assert (
        email_domain_store.normalize_domain("@Mail.Example.COM.")
        == "mail.example.com"
    )
    for value in (
        "https://mail.example.com",
        "user@mail.example.com",
        "*.example.com",
        "localhost",
    ):
        assert_invalid(value)

    with IsolatedStore():
        result = email_domain_store.import_domains(
            "\n".join(
                (
                    "mail-a.example.com",
                    "mail-a.example.com",
                    "mail-b.example.com",
                    "broken",
                )
            ),
            "cloudflare",
        )
        assert result["ok"] is True
        assert result["imported_count"] == 2
        assert result["duplicate_count"] == 1
        assert len(result["errors"]) == 1
        assert result["summary"]["active"] == 2
        if os.name == "posix":
            assert stat.S_IMODE(email_domain_store.STATE_PATH.stat().st_mode) == 0o600
            assert stat.S_IMODE(email_domain_store.LOCK_PATH.stat().st_mode) == 0o600


def test_max_active_is_per_provider_and_standby_promotes():
    with IsolatedStore():
        imported = email_domain_store.import_domains(
            "a.example.com\nb.example.com\nc.example.com",
            "cloudflare",
        )
        email_domain_store.import_domains("mail.example.net", "moemail")
        state = email_domain_store.update_settings(max_active_domains=2)
        cf_items = [
            item for item in state["items"] if item["provider"] == "cloudflare"
        ]
        assert [item["status"] for item in cf_items] == [
            "active",
            "active",
            "standby",
        ]
        moemail_item = next(
            item for item in state["items"] if item["provider"] == "moemail"
        )
        assert moemail_item["status"] == "active"

        first = email_domain_store.select_domain("cloudflare")
        second = email_domain_store.select_domain("cloudflare")
        assert first["domain"] != second["domain"]
        email_domain_store.update_domain(first["id"], enabled=False)
        promoted = email_domain_store.read_email_domain_pool()
        promoted_item = next(
            item for item in promoted["items"] if item["domain"] == "c.example.com"
        )
        assert promoted_item["status"] == "active"
        assert imported["summary"]["total"] == 3


def test_rejection_threshold_blocks_and_reset_restores_selection():
    with IsolatedStore():
        imported = email_domain_store.import_domains(
            "blocked.example.com",
            "cloudmail",
        )
        domain_id = imported["items"][0]["id"]
        email_domain_store.update_settings(failure_threshold=2)

        first = email_domain_store.record_domain_result(
            "cloudmail",
            "first@blocked.example.com",
            "rejected",
            "xAI rejected this email domain",
        )
        assert first["blocked"] is False
        second = email_domain_store.record_domain_result(
            "cloudmail",
            "second@blocked.example.com",
            "rejected",
            "xAI rejected this email domain",
        )
        assert second["newly_blocked"] is True
        assert email_domain_store.select_domain("cloudmail") == {
            "configured": True,
            "provider": "cloudmail",
            "domain": "",
            "id": "",
        }

        reset = email_domain_store.reset_domain(domain_id)
        item = reset["items"][0]
        assert item["status"] == "active"
        assert item["consecutive_rejections"] == 0
        assert item["total_rejections"] == 0
        selected = email_domain_store.select_domain("cloudmail")
        assert selected["domain"] == "blocked.example.com"

        accepted = email_domain_store.record_domain_result(
            "cloudmail",
            "ok@blocked.example.com",
            "accepted",
        )
        assert accepted["matched"] is True
        final = email_domain_store.read_email_domain_pool()["items"][0]
        assert final["success_count"] == 1
        assert final["consecutive_rejections"] == 0

        unrelated = email_domain_store.record_domain_result(
            "cloudmail",
            "other@unknown.example.com",
            "rejected",
        )
        assert unrelated["matched"] is False


if __name__ == "__main__":
    test_normalize_import_deduplicate_and_private_state()
    test_max_active_is_per_provider_and_standby_promotes()
    test_rejection_threshold_blocks_and_reset_restores_selection()
    print("OK email domain store")
