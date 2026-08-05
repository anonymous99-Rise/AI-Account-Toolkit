# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import connectivity
from email_providers import moemail


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self.payload


def test_normalize_base():
    assert moemail.normalize_base("mail.example.com/api") == "https://mail.example.com"
    assert moemail.normalize_base("https://mail.example.com/api/v1/") == "https://mail.example.com"
    assert moemail.normalize_base("https://host.example/prefix/api") == "https://host.example/prefix"


def test_domain_discovery_rotation_and_direct_requests():
    moemail.reset_runtime_state()
    calls = []

    def http_get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        assert kwargs["headers"]["X-API-Key"] == "test-key"
        assert kwargs["proxies"] == {}
        return FakeResponse({"emailDomains": "one.example, two.example"})

    def http_post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        assert kwargs["headers"]["X-API-Key"] == "test-key"
        assert kwargs["proxies"] == {}
        domain = kwargs["json"]["domain"]
        return FakeResponse({"id": f"id-{domain}", "email": f"user@{domain}"})

    first = moemail.create_mailbox(
        http_get,
        http_post,
        "https://mail.example/api",
        "test-key",
        name="user",
    )
    second = moemail.create_mailbox(
        http_get,
        http_post,
        "https://mail.example",
        "test-key",
        name="user",
    )

    assert first == ("user@one.example", "id-one.example")
    assert second == ("user@two.example", "id-two.example")
    assert [method for method, _, _ in calls].count("GET") == 1


def test_wait_for_code_and_cleanup():
    deleted = []

    def http_get(url, **kwargs):
        assert kwargs["proxies"] == {}
        if url.endswith("/api/emails/email-id"):
            return FakeResponse({"messages": [{"id": "message-id", "subject": "xAI verification"}]})
        if url.endswith("/api/emails/email-id/message-id"):
            return FakeResponse({"message": {"content": "Use A99-698 to continue."}})
        raise AssertionError(url)

    def http_delete(url, **kwargs):
        assert kwargs["proxies"] == {}
        deleted.append(url)
        return FakeResponse({"success": True})

    code = moemail.wait_for_code(
        http_get,
        "https://mail.example",
        "test-key",
        "email-id",
        email="user@example.com",
        http_delete=http_delete,
        raise_if_cancelled=lambda callback: None,
        sleep_with_cancel=lambda seconds, callback: None,
    )

    assert code == "A99-698"
    assert deleted == ["https://mail.example/api/emails/email-id"]


def test_connectivity_probe():
    seen = []

    def http_get(url, **kwargs):
        seen.append((url, kwargs))
        return FakeResponse({"emailDomains": "one.example,two.example"})

    result = connectivity.check_email_api(
        "moemail",
        {"moemail_api_base": "https://mail.example/api", "moemail_api_key": "test-key"},
        http_get,
        lambda *args, **kwargs: None,
    )

    assert result[1] is True
    assert "one.example" in result[2]
    assert seen[0][0] == "https://mail.example/api/config"
    assert seen[0][1]["proxies"] == {}


if __name__ == "__main__":
    test_normalize_base()
    test_domain_discovery_rotation_and_direct_requests()
    test_wait_for_code_and_cleanup()
    test_connectivity_probe()
    print("OK moemail")
