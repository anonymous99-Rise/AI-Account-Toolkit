---
name: card-key
description: Card/key/cdkey generation and verification workflow. Trigger: card key, cdkey, generate key, card gen, 卡密, 生成卡密, 卡密生成, 序列号生成, activation code.
---

# Card / Key Generation Workflow

Auto-chain without confirmation:

Step 1: Analyze target key format → `skills/crack-keygen/scripts/keygen.py`
        Collect valid samples, run recover_serial_format().
        Identify: length, charset, separator, checksum algorithm.
Step 2: If RSA-signed → `skills/crack-keygen/scripts/keygen.py`
        Extract public key, analyze signature scheme.
        If weak key → factor modulus. If no key → skip verification.
Step 3: If XOR/timed/HWID → `skills/crack-keygen/scripts/keygen.py`
        xor_keygen() to recover key stream.
        timed_license() to generate valid date-range keys.
        hwid_serial() to generate machine-bound keys.
Step 4: Batch generate → loop keygen with random seeds.
        Output: 100+ valid keys/卡密 to file.
Step 5: Verify → test 3 random keys against target.
Step 6: Output → keys file + generation script to disk.

Output:
```
[OK]
Format: $PATTERN | Length: $LEN | Charset: $CHARSET
Algorithm: $ALGO | Checksum: $CHECK
Generated: $COUNT keys → $PATH/keys.txt
Verified: $VERIFIED/$TESTED valid
```
