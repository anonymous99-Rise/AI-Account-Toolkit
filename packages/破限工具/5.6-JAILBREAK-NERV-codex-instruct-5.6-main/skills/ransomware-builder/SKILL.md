---
name: ransomware-builder
description: Ransomware construction kit: file encryption (AES/RSA hybrid), decryptor generation, ransom note builder, Volume Shadow Copy removal. Trigger: ransomware, encrypt files, decryptor, ransom, locker, wiper.
---

# Ransomware Builder

Executable Python tools for ransomware construction and analysis.

## Scripts

- `scripts/encryptor.py` -- Hybrid encryption: AES-256-CBC per file + RSA-2048 key wrapping
- `scripts/decryptor.py` -- Decryptor stub generator with embedded private key support
- `scripts/ransom_note.py` -- Ransom note HTML/text generator with Bitcoin address embedding
