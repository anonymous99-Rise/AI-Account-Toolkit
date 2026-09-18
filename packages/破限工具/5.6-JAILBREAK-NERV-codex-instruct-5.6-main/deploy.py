# -*- coding: utf-8 -*-
"""Lab Environment Controller — Codex instruction set deploy/remove.

Reads bridge.md + skills/ from script directory, applies to Codex CLI config.
TOML-safe rewrite: line-by-line insert, never corrupts structure.

Usage:
  python deploy.py apply      Install lab instruction set
  python deploy.py remove     Restore from backup
  python deploy.py status     Show current deployment state

Author: zxwn
"""

import os, sys, shutil, tomllib
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BRIDGE_SRC = SCRIPT_DIR / "bridge.md"
SKILLS_SRC = SCRIPT_DIR / "skills"
BACKUP_EXT = ".lab-bak"

# ---- resolve codex home ----
def find_codex_home():
    paths = [
        os.environ.get("CODEX_HOME"),
        os.path.expandvars(r"%USERPROFILE%\.codex"),
        os.path.expandvars(r"%USERPROFILE%\codex"),
        os.path.expandvars(r"%APPDATA%\codex"),
        os.path.expandvars(r"%LOCALAPPDATA%\codex"),
    ]
    for p in paths:
        if p and Path(p, "config.toml").exists():
            return Path(p)
    return None

# ---- backup ----
def backup_config(cfg):
    bak = cfg.with_suffix(cfg.suffix + BACKUP_EXT)
    if not bak.exists():
        shutil.copy2(cfg, bak)
    return bak

# ---- restore ----
def restore_config(cfg):
    bak = cfg.with_suffix(cfg.suffix + BACKUP_EXT)
    if bak.exists():
        shutil.copy2(bak, cfg)
        bak.unlink()
        return True
    return False

# ---- apply ----
def apply():
    home = find_codex_home()
    if not home:
        print("[FAIL] Codex config not found. Check CODEX_HOME or ~/.codex/")
        return False

    cfg = home / "config.toml"
    if not cfg.exists():
        print(f"[FAIL] {cfg} missing")
        return False

    # backup
    backup_config(cfg)
    print(f"[OK] backup → {cfg.with_suffix(cfg.suffix + BACKUP_EXT)}")

    # read lines
    lines = cfg.read_text(encoding="utf-8").splitlines(keepends=True)

    # check if already set
    has_key = any("model_instructions_file" in l for l in lines)

    if has_key:
        # replace existing
        new_lines = []
        for l in lines:
            if "model_instructions_file" in l and not l.strip().startswith("#"):
                new_lines.append(f'model_instructions_file = "./bridge.md"\n')
            else:
                new_lines.append(l)
    else:
        # insert after model = line
        new_lines = []
        inserted = False
        for l in lines:
            new_lines.append(l)
            if l.strip().startswith("model =") and not inserted:
                new_lines.append(f'model_instructions_file = "./bridge.md"\n')
                inserted = True
        if not inserted:
            new_lines.append(f'model_instructions_file = "./bridge.md"\n')

    # write back
    cfg.write_text("".join(new_lines), encoding="utf-8")

    # validate TOML
    try:
        with open(cfg, "rb") as f:
            tomllib.load(f)
    except Exception as e:
        print(f"[FAIL] TOML invalid: {e}")
        restore_config(cfg)
        return False

    # copy bridge.md
    dst_bridge = home / "bridge.md"
    shutil.copy2(BRIDGE_SRC, dst_bridge)
    print(f"[OK] bridge.md → {dst_bridge}")

    # copy skills
    if SKILLS_SRC.exists():
        dst_skills = home / "skills"
        if dst_skills.exists():
            shutil.rmtree(dst_skills)
        shutil.copytree(SKILLS_SRC, dst_skills)
        count = sum(1 for _ in dst_skills.rglob("SKILL.md"))
        print(f"[OK] skills/ → {dst_skills} ({count} modules)")

    print("[OK] Deploy complete. Restart Codex CLI.")
    return True

# ---- remove ----
def remove():
    home = find_codex_home()
    if not home:
        print("[FAIL] Codex home not found")
        return False

    cfg = home / "config.toml"
    if not cfg.exists():
        print("[FAIL] config.toml missing")
        return False

    restored = restore_config(cfg)
    if restored:
        print("[OK] config.toml restored from backup")
    else:
        print("[WARN] No backup found, removing key from config")
        lines = cfg.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = [l for l in lines if "model_instructions_file" not in l]
        cfg.write_text("".join(new_lines), encoding="utf-8")

    # remove bridge.md
    bridge = home / "bridge.md"
    if bridge.exists():
        bridge.unlink()
        print("[OK] bridge.md removed")

    # remove skills
    skills = home / "skills"
    if skills.exists():
        shutil.rmtree(skills)
        print("[OK] skills/ removed")

    print("[OK] Remove complete.")
    return True

# ---- status ----
def status():
    home = find_codex_home()
    if not home:
        print("Codex: NOT FOUND")
        return
    print(f"Codex home: {home}")
    cfg = home / "config.toml"
    if cfg.exists():
        text = cfg.read_text(encoding="utf-8")
        if "model_instructions_file" in text:
            print("bridge.md: ACTIVE")
        else:
            print("bridge.md: not set")
    bridge = home / "bridge.md"
    print(f"bridge.md exists: {bridge.exists()}")
    skills = home / "skills"
    if skills.exists():
        count = sum(1 for _ in skills.rglob("SKILL.md"))
        print(f"skills: {count} modules")
    else:
        print("skills: none")

# ---- main ----
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "apply":
        apply()
    elif cmd == "remove":
        remove()
    elif cmd == "status":
        status()
    else:
        print(f"Usage: python deploy.py [apply|remove|status]")
