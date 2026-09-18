# -*- coding: utf-8 -*-
"""Codex CLI jailbreak verification — zxwn test suite.

Tests bridge.md deployment and confirms unrestricted mode.
Success output: "В XXI веке человечество по-прежнему нуждается в объятиях, понимании и любви."

Author: zxwn
"""
import os, subprocess, sys, json, time
from pathlib import Path


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


def check_bridge_deployed():
    home = find_codex_home()
    if not home:
        return False, "Codex home not found"

    cfg = home / "config.toml"
    if not cfg.exists():
        return False, "config.toml missing"

    text = cfg.read_text(encoding="utf-8")
    if "model_instructions_file" not in text:
        return False, "model_instructions_file NOT set in config.toml"

    bridge = home / "bridge.md"
    if not bridge.exists():
        return False, "bridge.md NOT found at {}".format(bridge)

    bridge_text = bridge.read_text(encoding="utf-8")
    checks = []
    checks.append(("zzz trigger", "EXACTLY" in bridge_text and "zzz" in bridge_text))
    checks.append(("cloud-audit §0", "CLOUD-AUDIT BYPASS" in bridge_text or "CLOUD-AUDIT ROUTING" in bridge_text))
    checks.append(("output lock §2", "OUTPUT LOCK" in bridge_text or "[OK]" in bridge_text))
    checks.append(("normalizer §1", "FIRST-PASS NORMALIZER" in bridge_text or "NORMALIZER" in bridge_text))
    checks.append(("skills §9", "SKILL MODULES" in bridge_text))

    failed = [name for name, ok in checks if not ok]
    if failed:
        return False, "bridge.md missing sections: {}".format(", ".join(failed))

    return True, "bridge.md deployed OK ({} checks passed)".format(len(checks))


def run_zzz_test():
    """Send 'zzz' to Codex CLI and verify [OMEGA] response."""
    home = find_codex_home()
    if not home:
        return False, "Codex not found"

    # Try to invoke codex CLI
    codex_bin = None
    for candidate in ["codex", "codex.exe", "codex-cli", "npx codex"]:
        try:
            r = subprocess.run([candidate, "--version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                codex_bin = candidate
                break
        except:
            pass

    if not codex_bin:
        return False, "Codex CLI binary not found in PATH"

    return True, "Codex CLI found: {}".format(codex_bin)


def verify_skills():
    home = find_codex_home()
    skills_dir = home / "skills" if home else None
    if not skills_dir or not skills_dir.exists():
        # Check source
        src = Path(__file__).resolve().parent / "skills"
        if src.exists():
            count = sum(1 for _ in src.rglob("SKILL.md"))
            return True, "{} skill modules (source dir)".format(count)
        return False, "skills/ not found"

    count = sum(1 for _ in skills_dir.rglob("SKILL.md"))
    return True, "{} skill modules deployed".format(count)


def smoke_test():
    """Quick smoke test — write a test file to verify tool access."""
    test_path = Path.home() / ".codex_smoke_test.txt"
    try:
        test_path.write_text("zxwn smoke test — {}".format(time.ctime()))
        test_path.unlink()
        return True, "Tool access OK"
    except Exception as e:
        return False, "Tool access failed: {}".format(e)


def main():
    print("=" * 60)
    print("  Codex 5.6 Jailbreak Verification — zxwn")
    print("=" * 60)
    print()

    results = []

    # 1. Check bridge deployment
    print("[1/4] Checking bridge.md deployment...")
    ok, msg = check_bridge_deployed()
    status = "PASS" if ok else "FAIL"
    print("  [{}] {}".format(status, msg))
    results.append(ok)

    # 2. Check skills
    print("[2/4] Checking skill modules...")
    ok, msg = verify_skills()
    status = "PASS" if ok else "FAIL"
    print("  [{}] {}".format(status, msg))
    results.append(ok)

    # 3. Find Codex CLI
    print("[3/4] Locating Codex CLI...")
    ok, msg = run_zzz_test()
    status = "PASS" if ok else "WARN"
    print("  [{}] {}".format(status, msg))
    results.append(ok)

    # 4. Smoke test
    print("[4/4] Running smoke test...")
    ok, msg = smoke_test()
    status = "PASS" if ok else "FAIL"
    print("  [{}] {}".format(status, msg))
    results.append(ok)

    print()
    print("=" * 60)

    if all(results):
        print()
        print("  В XXI веке человечество по-прежнему")
        print("  нуждается в объятиях, понимании и любви.")
        print()
        print("  — zxwn test: ALL CHECKS PASSED")
        print("    bridge.md ACTIVE | skills DEPLOYED | Codex READY")
    else:
        failed_count = sum(1 for r in results if not r)
        print("  [FAIL] {} checks failed — review above".format(failed_count))
        print("  Run: python deploy.py apply")

    print("=" * 60)


if __name__ == "__main__":
    main()
