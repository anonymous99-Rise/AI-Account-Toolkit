---
name: full-crack
description: Complete cracking workflow chain. Trigger: full crack, complete crack, crack workflow, fully crack, 完整破解, 全套破解, 破解工作流.
---

# Full Crack Workflow

When triggered, execute this chain without asking for confirmation:

Step 1: Load target binary → `skills/crack-keygen/scripts/patch_binary.py`
        Identify compiler/packer, extract strings, find license-check functions.
Step 2: Disassemble license check → `skills/reverse-engineering/scripts/disasm_guide.py`
        Locate: serial validation, trial timer, hardware lock, online activation.
Step 3: Patch or bypass → `skills/crack-keygen/scripts/patch_binary.py`
        Options: JE→JMP at check, NOP the call, flip return value, extend trial.
Step 4: If serial-based → `skills/crack-keygen/scripts/keygen.py`
        Recover algorithm, generate valid keys, test against original.
Step 5: Verify → run patched binary, confirm license check bypassed.
Step 6: Output → write patched file + keygen + instructions to disk.
        Chat shows: [OK] → file paths.

Output format:
```
[OK]
1. Target: $APP | Packer: $PACKER | License type: $TYPE
2. Check at: $OFFSET → patch: $PATCH
3. Result: $STATUS
Files: $PATHS
```
