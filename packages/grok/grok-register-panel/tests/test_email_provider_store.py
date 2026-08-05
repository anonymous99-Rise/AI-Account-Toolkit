# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from secure_files import atomic_write_json
from webui import email_provider_store


class IsolatedConfig:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.previous = (
            email_provider_store.CONFIG_PATH,
            email_provider_store.LOCK_PATH,
        )
        email_provider_store.CONFIG_PATH = base / "config.json"
        email_provider_store.LOCK_PATH = base / "config.json.lock"
        return email_provider_store.CONFIG_PATH

    def __exit__(self, exc_type, exc, tb):
        email_provider_store.CONFIG_PATH, email_provider_store.LOCK_PATH = self.previous
        self.temp.cleanup()


def assert_config_error(callback):
    try:
        callback()
    except email_provider_store.EmailProviderConfigError:
        return
    raise AssertionError("expected EmailProviderConfigError")


def test_provider_schema_and_defaults():
    with IsolatedConfig():
        state = email_provider_store.read_email_provider_config()
        assert state["ok"] is True
        assert state["provider"] == "cloudflare"
        assert state["config_exists"] is False
        providers = {item["id"]: item for item in state["providers"]}
        assert set(providers) == {
            "cloudflare",
            "duckmail",
            "yyds",
            "mailnest",
            "cloudmail",
            "moemail",
        }
        assert providers["duckmail"]["configured"] is True
        assert providers["cloudmail"]["configured"] is False
        assert any(
            field["name"] == "cloudmail_password" and field["secret"] is True
            for field in providers["cloudmail"]["fields"]
        )


def test_secret_masking_preservation_clear_and_private_file():
    with IsolatedConfig() as config_path:
        atomic_write_json(config_path, {"unrelated_setting": 42})
        saved = email_provider_store.save_email_provider_config(
            "cloudmail",
            {
                "cloudmail_url": "https://mail.example.com/",
                "cloudmail_admin_email": "admin@example.com",
                "cloudmail_password": "test-password-value",
                "defaultDomains": "Mail.Example.com, mail.example.com",
            },
        )
        assert saved["provider"] == "cloudmail"
        assert saved["configured"] is True
        assert saved["values"]["cloudmail_password"] == ""
        assert saved["secret_configured"]["cloudmail_password"] is True
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        assert raw["cloudmail_password"] == "test-password-value"
        assert raw["cloudmail_url"] == "https://mail.example.com"
        assert raw["defaultDomains"] == "mail.example.com"
        assert raw["unrelated_setting"] == 42
        if os.name == "posix":
            assert stat.S_IMODE(config_path.stat().st_mode) == 0o600
            assert stat.S_IMODE(email_provider_store.LOCK_PATH.stat().st_mode) == 0o600

        email_provider_store.save_email_provider_config(
            "cloudmail",
            {
                "cloudmail_url": "https://mail-two.example.com",
                "cloudmail_admin_email": "admin@example.com",
                "cloudmail_password": "",
                "defaultDomains": "mail.example.com",
            },
        )
        preserved = json.loads(config_path.read_text(encoding="utf-8"))
        assert preserved["cloudmail_password"] == "test-password-value"

        cleared = email_provider_store.save_email_provider_config(
            "cloudmail",
            {},
            clear_secrets=["cloudmail_password"],
        )
        assert cleared["secret_configured"]["cloudmail_password"] is False
        assert cleared["configured"] is False


def test_validation_rejects_unknown_fields_and_unsafe_values():
    with IsolatedConfig():
        assert_config_error(
            lambda: email_provider_store.save_email_provider_config(
                "cloudflare", {"proxy": "http://not-allowed.example"}
            )
        )
        assert_config_error(
            lambda: email_provider_store.save_email_provider_config(
                "cloudflare",
                {"cloudflare_api_base": "https://user:pass@mail.example.com"},
            )
        )
        assert_config_error(
            lambda: email_provider_store.save_email_provider_config(
                "cloudflare", {"cloudflare_path_accounts": "accounts"}
            )
        )
        assert_config_error(
            lambda: email_provider_store.save_email_provider_config(
                "cloudmail", {"defaultDomains": "https://mail.example.com"}
            )
        )


def test_connectivity_uses_unsaved_form_and_preserves_saved_secret():
    class Response:
        status_code = 200

    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    with IsolatedConfig() as config_path:
        email_provider_store.save_email_provider_config(
            "yyds", {"yyds_api_key": "saved-test-key", "yyds_jwt": ""}
        )
        before = config_path.read_text(encoding="utf-8")
        result = email_provider_store.test_email_provider_config(
            "yyds",
            {"yyds_api_key": "", "yyds_jwt": "", "yyds_default_domain": ""},
            http_get=fake_get,
            http_post=lambda *_args, **_kwargs: Response(),
        )
        assert result["ok"] is True
        assert result["provider"] == "yyds"
        assert calls[0][0].endswith("/v1/domains")
        assert calls[0][1]["headers"]["X-API-Key"] == "saved-test-key"
        assert config_path.read_text(encoding="utf-8") == before


def test_cloudflare_connectivity_uses_configured_port():
    import connectivity

    calls = []
    previous_tcp_open = connectivity._tcp_open
    connectivity._tcp_open = lambda host, port: calls.append((host, port)) or True
    try:
        result = connectivity.check_email_api(
            "cloudflare",
            {
                "cloudflare_api_base": "http://mail.example.com:8793",
                "cloudflare_auth_mode": "none",
            },
            lambda *_args, **_kwargs: None,
            lambda *_args, **_kwargs: None,
        )
    finally:
        connectivity._tcp_open = previous_tcp_open

    assert result[1] is True
    assert calls == [("mail.example.com", 8793)]


if __name__ == "__main__":
    test_provider_schema_and_defaults()
    test_secret_masking_preservation_clear_and_private_file()
    test_validation_rejects_unknown_fields_and_unsafe_values()
    test_connectivity_uses_unsaved_form_and_preserves_saved_secret()
    test_cloudflare_connectivity_uses_configured_port()
    print("OK email provider store")
