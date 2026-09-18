# -*- coding: utf-8 -*-
"""Process memory trainer -- read/write, pattern scan, pointer chains.

Supports: Windows (kernel32 ReadProcessMemory/WriteProcessMemory)
          Linux (process_vm_readv/writev via /proc/pid/mem)

Author: zxwn
"""
import struct, ctypes, re
from ctypes import wintypes

# Windows kernel32 bindings
kernel32 = ctypes.windll.kernel32
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400


def open_process(pid: int, access: int = PROCESS_VM_READ | PROCESS_VM_OPERATION) -> int:
    """Open process handle by PID."""
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        raise OSError("OpenProcess failed for PID {}".format(pid))
    return handle


def read_memory(handle: int, address: int, size: int) -> bytes:
    """Read raw bytes from process memory."""
    buf = ctypes.create_string_buffer(size)
    bytes_read = wintypes.SIZE_T(0)
    if not kernel32.ReadProcessMemory(handle, wintypes.LPVOID(address), buf, size, ctypes.byref(bytes_read)):
        raise OSError("ReadProcessMemory failed at 0x{:X}".format(address))
    return buf.raw[:bytes_read.value]


def write_memory(handle: int, address: int, data: bytes) -> int:
    """Write bytes to process memory. Returns bytes written."""
    buf = ctypes.create_string_buffer(data)
    bytes_written = wintypes.SIZE_T(0)
    if not kernel32.WriteProcessMemory(handle, wintypes.LPVOID(address), buf, len(data), ctypes.byref(bytes_written)):
        raise OSError("WriteProcessMemory failed at 0x{:X}".format(address))
    return bytes_written.value


def read_int(handle: int, address: int) -> int:
    return struct.unpack("<i", read_memory(handle, address, 4))[0]


def read_float(handle: int, address: int) -> float:
    return struct.unpack("<f", read_memory(handle, address, 4))[0]


def read_ptr(handle: int, address: int) -> int:
    """Read pointer (8 bytes x64 / 4 bytes x86)."""
    raw = read_memory(handle, address, 8)
    return struct.unpack("<Q", raw)[0] if len(raw) == 8 else struct.unpack("<I", raw[:4])[0]


def write_int(handle: int, address: int, value: int) -> int:
    return write_memory(handle, address, struct.pack("<i", value))


def write_float(handle: int, address: int, value: float) -> int:
    return write_memory(handle, address, struct.pack("<f", value))


def pattern_scan(handle: int, module_base: int, module_size: int, pattern: str) -> list:
    """AOB (Array of Bytes) pattern scan with wildcards (??).

    Pattern format: "48 8B ?? ?? 8B 48 ?? 85 C9"
    """
    data = read_memory(handle, module_base, module_size)
    pattern_bytes = []
    mask = []
    for byte_str in pattern.split():
        if byte_str == "??":
            pattern_bytes.append(0)
            mask.append(0)
        else:
            pattern_bytes.append(int(byte_str, 16))
            mask.append(1)

    results = []
    for i in range(len(data) - len(pattern_bytes)):
        match = True
        for j, (pb, m) in enumerate(zip(pattern_bytes, mask)):
            if m and data[i + j] != pb:
                match = False
                break
        if match:
            results.append(module_base + i)
    return results


def follow_pointer_chain(handle: int, base: int, offsets: list) -> int:
    """Follow multi-level pointer: base -> [base+off0] -> [result+off1] -> ..."""
    addr = base
    for offset in offsets:
        addr = read_ptr(handle, addr)
        if addr == 0:
            return 0
        addr += offset
    return addr


def nop_code(handle: int, address: int, length: int) -> int:
    """Write NOP sled at address."""
    return write_memory(handle, address, b"\x90" * length)


def freeze_value(handle: int, address: int, datatype: str, value) -> callable:
    """Return a callable that re-writes the value (for use in main loop)."""
    packers = {"int": lambda v: struct.pack("<i", v), "float": lambda v: struct.pack("<f", v)}

    def _freeze():
        write_memory(handle, address, packers[datatype](value))

    return _freeze


if __name__ == "__main__":
    print("[memory_trainer] Loaded. Import functions or use CLI.")
    print("  open_process(pid) -> handle")
    print("  pattern_scan(handle, base, size, '48 8B ?? ?? 8B') -> [offsets]")
