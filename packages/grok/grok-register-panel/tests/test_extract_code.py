# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from email_providers.common import extract_verification_code


def test_reject_per100():
    assert extract_verification_code("width per-100 class footer", "") is None
    assert extract_verification_code(
        "class=per-100 style and real code later QO7-TUD near xAI",
        "",
    ) == "QO7-TUD"
    assert extract_verification_code(
        "CloudMail template per-100 max-100\nYour code",
        "CXX-PC2 xAI verify",
    ) == "CXX-PC2"


def test_subject_wins():
    assert extract_verification_code("per-100 junk", "B2R-9QB xAI sign-up") == "B2R-9QB"


def test_mixed_real_codes():
    assert extract_verification_code("please use XSB-802 to continue with xAI", "") == "XSB-802"
    assert extract_verification_code("code A99-698", "A99-698 xAI") == "A99-698"
    assert extract_verification_code("only max-100 in mail chrome", "") is None


if __name__ == "__main__":
    test_reject_per100()
    test_subject_wins()
    test_mixed_real_codes()
    print("OK extract_code")
