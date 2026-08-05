# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webui.security_utils import (
    check_token,
    check_token_optional_read,
    mask_email,
    redact_log_line,
    redact_proxy,
)


def test_redact_proxy_strips_userinfo():
    raw = "http://user:s3cretpass@127.0.0.1:7900"
    out = redact_proxy(raw)
    assert "s3cretpass" not in out
    assert "user" not in out.split("://", 1)[-1].split("@")[0] if "@" in out else True
    assert "127.0.0.1:7900" in out
    assert out.startswith("http://")


def test_redact_proxy_keeps_clean():
    assert redact_proxy("http://127.0.0.1:7900") == "http://127.0.0.1:7900"


def test_mask_email():
    assert mask_email("abcdef@example.com").startswith("ab***@")
    assert "abcdef" not in mask_email("abcdef@example.com")


def test_write_requires_token(monkeypatch=None):
    os.environ.pop("MONITOR_TOKEN", None)
    assert check_token_optional_read(None, write=True) is False
    os.environ["MONITOR_TOKEN"] = "test-secret-token-xyz"
    try:
        assert check_token_optional_read("Bearer test-secret-token-xyz", write=True) is True
        assert check_token_optional_read("Bearer wrong", write=True) is False
        assert check_token_optional_read(None, write=False) is False  # token set, read also needs it
        assert check_token_optional_read("Bearer test-secret-token-xyz", write=False) is True
    finally:
        os.environ.pop("MONITOR_TOKEN", None)


def test_log_redaction():
    opaque = "opaque-refresh-secret-value-123456"
    line = (
        "email=person@example.com proxy=http://user:pass@127.0.0.1:7900 "
        f"user_code=ABC-123 refresh_token={opaque}"
    )
    redacted = redact_log_line(line)
    assert "person@example.com" not in redacted
    assert "pass" not in redacted
    assert "ABC-123" not in redacted
    assert opaque not in redacted
    chinese = redact_log_line("\x1b[36m从邮件中提取到验证码: \x1b[32mG3B-J4J\x1b[0m")
    assert "G3B-J4J" not in chinese
    assert "验证码: [redacted]" in chinese
    assert "\x1b" not in chinese
    submitted = redact_log_line("已填写验证码并提交: O7F-S81")
    assert "O7F-S81" not in submitted
    assert "验证码并提交: [redacted]" in submitted


if __name__ == "__main__":
    test_redact_proxy_strips_userinfo()
    test_redact_proxy_keeps_clean()
    test_mask_email()
    test_write_requires_token()
    test_log_redaction()
    print("OK all security_utils tests")
