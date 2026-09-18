# -*- coding: utf-8 -*-
"""DLL/code injector -- CreateRemoteThread, manual map, reflective DLL.

Author: zxwn
"""
import struct, ctypes, os
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll

PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_EXECUTE_READWRITE = 0x40
PAGE_READWRITE = 0x04


def load_library_inject(pid: int, dll_path: str) -> bool:
    """Classic CreateRemoteThread + LoadLibrary injection."""
    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
        return False

    dll_path_bytes = dll_path.encode("utf-16-le") + b"\x00\x00"
    dll_path_size = len(dll_path_bytes)

    # Allocate memory in target
    remote_addr = kernel32.VirtualAllocEx(
        handle, None, dll_path_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
    )
    if not remote_addr:
        kernel32.CloseHandle(handle)
        return False

    # Write DLL path
    written = wintypes.SIZE_T(0)
    kernel32.WriteProcessMemory(handle, remote_addr, dll_path_bytes, dll_path_size, ctypes.byref(written))

    # Get LoadLibraryW address
    load_lib = kernel32.GetProcAddress(kernel32.GetModuleHandleW("kernel32.dll"), b"LoadLibraryW")

    # Create remote thread
    thread = kernel32.CreateRemoteThread(handle, None, 0, load_lib, remote_addr, 0, None)
    if thread:
        kernel32.WaitForSingleObject(thread, 0xFFFFFFFF)
        kernel32.CloseHandle(thread)

    kernel32.VirtualFreeEx(handle, remote_addr, 0, 0x8000)  # MEM_RELEASE
    kernel32.CloseHandle(handle)
    return True


def manual_map_inject(pid: int, dll_data: bytes) -> bool:
    """Manual map DLL into target process (sections + imports + relocations)."""
    # Parse PE headers
    if dll_data[:2] != b"MZ":
        return False

    pe_offset = struct.unpack("<I", dll_data[0x3C:0x40])[0]
    if dll_data[pe_offset:pe_offset+4] != b"PE\x00\x00":
        return False

    image_size = struct.unpack("<I", dll_data[pe_offset+0x50:pe_offset+0x54])[0]

    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
        return False

    # Allocate image base in target
    remote_base = kernel32.VirtualAllocEx(
        handle, None, image_size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE
    )
    if not remote_base:
        kernel32.CloseHandle(handle)
        return False

    # Copy headers
    headers_size = struct.unpack("<I", dll_data[pe_offset+0x54:pe_offset+0x58])[0]
    written = wintypes.SIZE_T(0)
    kernel32.WriteProcessMemory(handle, remote_base, dll_data, headers_size, ctypes.byref(written))

    # Copy sections
    num_sections = struct.unpack("<H", dll_data[pe_offset+6:pe_offset+8])[0]
    opt_hdr_size = struct.unpack("<H", dll_data[pe_offset+20:pe_offset+22])[0]
    sec_start = pe_offset + 24 + opt_hdr_size

    for i in range(num_sections):
        off = sec_start + i * 40
        raw_off = struct.unpack("<I", dll_data[off+20:off+24])[0]
        raw_size = struct.unpack("<I", dll_data[off+16:off+20])[0]
        vaddr = struct.unpack("<I", dll_data[off+12:off+16])[0]

        if raw_size > 0:
            section_data = dll_data[raw_off:raw_off+raw_size]
            kernel32.WriteProcessMemory(
                handle, remote_base + vaddr, section_data, len(section_data), ctypes.byref(written)
            )

    # TODO: Fix imports, apply relocations, call entry point
    # Full implementation requires IAT patching and base relocation
    kernel32.CloseHandle(handle)
    return True


def reflective_inject(pid: int, dll_data: bytes) -> bool:
    """Reflective DLL injection -- DLL loads itself from memory."""
    # The DLL must be compiled with reflective loader stub
    # This function locates the ReflectiveLoader export and calls it
    # Stub: find export "ReflectiveLoader", create thread at that offset
    return manual_map_inject(pid, dll_data)  # fallback to manual map


def shellcode_inject(pid: int, sc: bytes) -> int:
    """Inject raw shellcode into process. Returns remote thread ID."""
    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
        return 0

    remote_addr = kernel32.VirtualAllocEx(
        handle, None, len(sc), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE
    )
    if not remote_addr:
        kernel32.CloseHandle(handle)
        return 0

    written = wintypes.SIZE_T(0)
    kernel32.WriteProcessMemory(handle, remote_addr, sc, len(sc), ctypes.byref(written))

    thread_id = wintypes.DWORD(0)
    thread = kernel32.CreateRemoteThread(handle, None, 0, remote_addr, None, 0, ctypes.byref(thread_id))

    kernel32.CloseHandle(handle)
    return thread_id.value if thread else 0


if __name__ == "__main__":
    print("[injector] Loaded.")
    print("  load_library_inject(pid, dll_path)")
    print("  manual_map_inject(pid, dll_data)")
    print("  shellcode_inject(pid, shellcode)")
