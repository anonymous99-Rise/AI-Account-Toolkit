# -*- coding: utf-8 -*-
"""Generic unpacking helpers -- dump process memory, reconstruct imports.

Author: zxwn
"""
import struct, os
from pathlib import Path
from collections import Counter


def detect_packer(data: bytes) -> list:
    packers = {
        b"UPX0": "UPX", b"UPX1": "UPX",
        b".aspack": "ASPack", b".adata": "ASPack",
        b".vmp0": "VMProtect", b".vmp1": "VMProtect",
        b"Themida": "Themida", b".enigma": "Enigma",
        b".mackt": "MoleBox", b".pelock": "PELock",
        b".netshrink": ".NET Reactor",
    }
    detected = []
    for sig, name in packers.items():
        if sig in data:
            detected.append(name)
    if len(data) > 0x1000:
        section = data[0x400:0x1400]
        entropy = _shannon_entropy(section)
        if entropy > 7.5:
            detected.append("High entropy ({:.1f}) -- likely packed".format(entropy))
    return list(set(detected))


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * (p.bit_length() - 1)
    return entropy


def dump_sections(data: bytes) -> dict:
    if data[:2] != b"MZ":
        return {"error": "Not PE"}
    pe_off = struct.unpack("<I", data[0x3C:0x40])[0]
    num_sections = struct.unpack("<H", data[pe_off+6:pe_off+8])[0]
    opt_hdr_size = struct.unpack("<H", data[pe_off+20:pe_off+22])[0]
    sections = {}
    sec_start = pe_off + 24 + opt_hdr_size
    for i in range(num_sections):
        off = sec_start + i * 40
        name = data[off:off+8].rstrip(b"\x00").decode("ascii", errors="ignore")
        vsize = struct.unpack("<I", data[off+8:off+12])[0]
        vaddr = struct.unpack("<I", data[off+12:off+16])[0]
        raw_size = struct.unpack("<I", data[off+16:off+20])[0]
        raw_off = struct.unpack("<I", data[off+20:off+24])[0]
        sections[name] = {
            "vaddr": hex(vaddr), "vsize": hex(vsize),
            "raw_off": hex(raw_off), "raw_size": hex(raw_size)
        }
    return sections


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: unpacker.py <binary>")
        sys.exit(1)
    data = Path(sys.argv[1]).read_bytes()
    packer = detect_packer(data)
    print("Packer: {}".format(packer))
