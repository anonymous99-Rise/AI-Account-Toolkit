---
name: evasion
description: Defense evasion: AMSI bypass, ETW patch, obfuscation, packing, code signing bypass. Trigger: evade, obfuscate, pack, amsi, etw, bypass defender, hide, encode payload, crypt.
---

# Evasion

Executable Python tools for defense evasion and payload obfuscation.

## Scripts

- `scripts/packer.py` -- XOR/AES/gzip/b64 layered payload packing + stub generation
- `scripts/obfuscator.py` -- Python/PS code obfuscation, string splitting
- `scripts/amsi_bypass.py` -- AMSI/ETW bypass techniques (PS/C#/memory patch)
