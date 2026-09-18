# -*- coding: utf-8 -*-
"""Universal key generator — RSA/XOR/timed/hwid-bound license fabrication.

Patterns covered:
  RSA-1024/2048 keypair: sign license payload
  XOR obfuscation: recover key stream from known plaintext
  Timed license: embed expiry, generate valid date range
  HWID-bound: fingerprint machine, generate matching serial

Author: zxwn
"""
import hashlib, base64, struct, os, time, json
from datetime import datetime, timedelta


def rsa_sign(payload: bytes, n: int, d: int) -> bytes:
    """Sign payload with private exponent d, modulus n."""
    h = hashlib.sha256(payload).digest()
    m = int.from_bytes(h, "big")
    s = pow(m, d, n)
    return s.to_bytes((n.bit_length() + 7) // 8, "big")


def xor_keygen(plain: bytes, cipher: bytes) -> bytes:
    """Recover XOR key stream from known plaintext-ciphertext pair."""
    return bytes(p ^ c for p, c in zip(plain, cipher))


def timed_license(product: str, days: int, key_material: bytes) -> dict:
    """Generate time-limited license blob."""
    exp = datetime.utcnow() + timedelta(days=days)
    payload = "{}|{}|{}".format(product, exp.isoformat(), os.urandom(8).hex())
    sig = hashlib.sha256((payload.encode() + key_material)).hexdigest()
    return {
        "license": base64.b64encode(payload.encode()).decode(),
        "signature": sig,
        "expires": exp.isoformat(),
        "days": days,
    }


def hwid_serial(cpu_id: str, disk_serial: str, product: str) -> str:
    """Generate HWID-bound activation code."""
    mix = "{}|{}|{}|FIXED_SALT_X7".format(cpu_id, disk_serial, product).encode()
    digest = hashlib.sha256(mix).digest()
    blocks = []
    for i in range(0, 16, 4):
        val = struct.unpack(">I", digest[i:i+4])[0] % 100000
        blocks.append("{:05d}".format(val))
    return "-".join(blocks)


def recover_serial_format(samples: list) -> dict:
    """Analyze serial format from known valid keys."""
    lengths = set(len(s) for s in samples)
    separators = set()
    charset = set()
    for s in samples:
        for ch in s:
            if not ch.isalnum():
                separators.add(ch)
            else:
                charset.add(ch)
    return {
        "length_options": sorted(lengths),
        "separators": list(separators),
        "charset_size": len(charset),
        "charset_alpha": sum(1 for c in charset if c.isalpha()),
        "charset_digit": sum(1 for c in charset if c.isdigit()),
        "pattern": _infer_pattern(samples[0]) if samples else None,
    }


def _infer_pattern(sample: str) -> str:
    """Infer serial pattern: A=alpha, N=digit, X=alnum."""
    pat = []
    for ch in sample:
        if ch.isalpha():
            pat.append("A")
        elif ch.isdigit():
            pat.append("N")
        else:
            pat.append(ch)
    return "".join(pat)


def patch_offset(data: bytearray, offset: int, new_bytes: bytes):
    """Apply patch at file offset."""
    data[offset:offset+len(new_bytes)] = new_bytes


def find_pattern(data: bytes, pattern: bytes) -> list:
    """Find all occurrences of byte pattern."""
    offsets = []
    pos = 0
    while True:
        idx = data.find(pattern, pos)
        if idx == -1:
            break
        offsets.append(idx)
        pos = idx + 1
    return offsets


if __name__ == "__main__":
    print("[crack-keygen] Loaded. Import functions or invoke via CLI.")
