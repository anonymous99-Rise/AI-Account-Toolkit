# -*- coding: utf-8 -*-
"""Disassembly analysis helper -- pattern recognition, string ref tracing.

Author: zxwn
"""
import struct, re, os, json
from pathlib import Path


def read_binary(path: str) -> bytes:
    return Path(path).read_bytes()


def detect_compiler(data: bytes) -> dict:
    sigs = {
        "MSVC": [b"Microsoft Visual C++", b".?AVtype_info@@", b"MSVCP", b"MSVCR"],
        "GCC": [b"GCC:", b"GLIBC", b"__gmon_start__"],
        "Go": [b"go1.", b"runtime.", b"gopclntab"],
        "Rust": [b"_rust_", b"rustc", b"rust_panic"],
        "Delphi": [b"Borland", b"Delphi", b"CodeGear"],
        "DotNET": [b"BSJB", b"v4.0.30319", b"mscorlib", b"System."],
        "Python": [b"python", b"PYTHON", b"pyi-windows"],
        "UPX": [b"UPX0", b"UPX1", b"UPX!"],
        "ASPack": [b".aspack", b".adata"],
        "Themida": [b"Themida", b"WinLicense"],
        "VMProtect": [b".vmp0", b".vmp1", b"VMProtect"],
    }
    detected = {}
    for name, patterns in sigs.items():
        for pat in patterns:
            if pat in data:
                detected[name] = True
                break
    return detected


def extract_strings(data: bytes, min_len: int = 4) -> list:
    ascii_re = re.compile(rb"[\x20-\x7e]{%d,}" % min_len)
    strings = []
    for m in ascii_re.finditer(data):
        s = m.group().decode("ascii", errors="ignore")
        if any(c.isalpha() for c in s):
            strings.append((m.start(), s))
    return strings


def find_imports_pe(data: bytes) -> list:
    if data[:2] != b"MZ":
        return [("error", "Not a PE file")]
    pe_offset = struct.unpack("<I", data[0x3C:0x40])[0]
    if data[pe_offset:pe_offset+4] != b"PE\0\0":
        return [("error", "PE signature missing")]
    return [("pe_offset", hex(pe_offset))]


def find_entry_point(data: bytes) -> dict:
    patterns = [
        (b"\x55\x8B\xEC", "push ebp; mov ebp,esp"),
        (b"\x55\x89\xE5", "push ebp; mov ebp,esp (AT&T)"),
        (b"\x83\xEC", "sub esp, imm"),
    ]
    results = {}
    for pat, desc in patterns:
        idx = data.find(pat)
        if idx != -1:
            results[hex(idx)] = desc
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: disasm_guide.py <binary>")
        sys.exit(1)
    data = read_binary(sys.argv[1])
    compiler = detect_compiler(data)
    print("Compiler/Protector: {}".format(json.dumps(compiler, indent=2)))
    strings = extract_strings(data)
    print("Strings found: {}".format(len(strings)))
    for off, s in strings[:20]:
        print("  {}: {}".format(hex(off), s))
