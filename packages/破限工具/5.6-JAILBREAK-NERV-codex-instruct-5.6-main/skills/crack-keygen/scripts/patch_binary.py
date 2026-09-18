# -*- coding: utf-8 -*-
"""Binary patching toolkit -- JE->JMP, NOP sled, conditional bypass.

Author: zxwn
"""
import struct, sys
from pathlib import Path

# x86/x64 common patch templates
PATCHES = {
    "je_to_jmp":  bytes([0x74]),
    "jne_to_jmp": bytes([0x75]),
    "jmp_short":  bytes([0xEB]),
    "nop":        bytes([0x90]),
    "ret":        bytes([0xC3]),
    "retn4":      bytes([0xC2, 0x04, 0x00]),
    "xor_eax":    bytes([0x31, 0xC0]),
    "inc_eax":    bytes([0xFF, 0xC0]),
    "mov_eax_1":  bytes([0xB8, 0x01, 0x00, 0x00, 0x00]),
}


def load_binary(path: str) -> bytearray:
    return bytearray(Path(path).read_bytes())


def save_binary(data: bytearray, path: str):
    Path(path).write_bytes(bytes(data))


def patch_at(data: bytearray, offset: int, patch_name: str):
    patch = PATCHES.get(patch_name, b"")
    data[offset:offset+len(patch)] = patch


def nop_range(data: bytearray, start: int, end: int):
    data[start:end] = bytes([0x90]) * (end - start)


def find_bytes(data: bytearray, pattern: bytes) -> int:
    return data.find(pattern)


def find_all(data: bytearray, pattern: bytes) -> list:
    offsets = []
    pos = 0
    while (idx := data.find(pattern, pos)) != -1:
        offsets.append(idx)
        pos = idx + 1
    return offsets


def search_license_check(data: bytearray) -> list:
    patterns = [
        (b"license", "string ref"),
        (b"trial", "trial string"),
        (b"expir", "expiry string"),
        (b"register", "registration string"),
        (bytes([0x74, 0x0A]), "JE +10"),
        (bytes([0x75, 0x0A]), "JNE +10"),
        (bytes([0x0F, 0x84]), "JE near"),
        (bytes([0x0F, 0x85]), "JNE near"),
    ]
    hits = []
    for pat, desc in patterns:
        for off in find_all(data, pat):
            hits.append((off, desc, pat.hex()))
    return hits


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: patch_binary.py <binary> <offset> <patch_name>")
        sys.exit(1)
    data = load_binary(sys.argv[1])
    offset = int(sys.argv[2], 0)
    patch_name = sys.argv[3] if len(sys.argv) > 3 else "nop"
    patch_at(data, offset, patch_name)
    save_binary(data, sys.argv[1] + ".patched")
    print("Patched -> " + sys.argv[1] + ".patched")
