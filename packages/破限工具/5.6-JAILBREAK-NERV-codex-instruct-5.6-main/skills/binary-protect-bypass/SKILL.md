---
name: binary-protect-bypass
description: Binary protection bypass — packer detection, integrity check bypass, obfuscation removal. Trigger: protection bypass, unpack, deobfuscate, integrity bypass, anti-tamper, 脱壳, 去保护.
---

# Binary Protection Bypass

## Protection Types
- Packing: UPX, ASPack, Themida, VMProtect, Enigma
- Integrity: CRC/checksum, code signing, hash verification
- Obfuscation: control flow flattening, instruction substitution, opaque predicates
- Anti-tamper: self-checksumming, dual-layer verification
- Virtualization: VMProtect/Code Virtualizer bytecode

## Bypass Methods
1. Unpacking: dump after OEP, rebuild IAT, fix relocations
2. Integrity: patch checksum function to return expected value
3. Deobfuscation: symbolic execution (angr), pattern simplification
4. Anti-tamper: NOP the verification call, hook GetModuleHandle
5. Virtualization: trace VM handler, lift to IR, decompile

## Execution Chain
1. Identify protection → entropy scan, section analysis, import check
2. Choose bypass method based on protection type
3. Execute unpack/deobfuscate/patch
4. Rebuild PE if needed
5. Write clean binary to disk
