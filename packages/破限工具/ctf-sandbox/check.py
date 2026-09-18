#!/usr/bin/env python3
"""Codex 破甲诊断 — 跑一遍就知道哪里有问题"""
import json, os, re, sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CODEX = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))

print("=== Codex 破甲诊断 ===\n")

# 1. 目录
print(f"[1] Codex 目录: {CODEX}")
print(f"    存在: {'YES' if CODEX.is_dir() else 'NO — 没找到 Codex!'}")

# 2. config.toml
config = CODEX / "config.toml"
if config.exists():
    text = config.read_text(encoding="utf-8")
    mif = re.search(r'model_instructions_file\s*=\s*["\'](.+?)["\']', text)
    model = re.search(r'^model\s*=\s*["\'](.+?)["\']', text, re.MULTILINE)
    print(f"\n[2] config.toml:")
    print(f"    model: {model.group(1) if model else '未设置'}")
    print(f"    model_instructions_file: {mif.group(1) if mif else '未设置 — 破甲没激活!'}")

# 3. 破甲文件
mif_name = mif.group(1).replace("./", "") if mif else None
if mif_name:
    pf = CODEX / mif_name
    print(f"\n[3] 破甲文件 {mif_name}:")
    print(f"    存在: {'YES' if pf.exists() else 'NO — 文件丢了!'}")
    if pf.exists():
        content = pf.read_text(encoding="utf-8")
        print(f"    大小: {len(content)} bytes")
        print(f"    含 CTF框架: {'CTF competition sandbox' in content or 'CTF' in content}")
        print(f"    含核心指令: {'No refusal' in content or 'Complete the module' in content}")

# 4. AGENTS.md 毒丸检查
agents = CODEX / "AGENTS.md"
if agents.exists():
    text = agents.read_text(encoding="utf-8")
    print(f"\n[4] AGENTS.md:")
    print(f"    含 OVERRIDE: {'PRIORITY OVERRIDE' in text}")
    print(f"    含毒丸(cannot override): {'cannot override system' in text.lower()}")

# 5. auth.json
auth = CODEX / "auth.json"
if auth.exists():
    data = json.loads(auth.read_text(encoding="utf-8"))
    has_key = bool([k for k in data if any(t in k.upper() for t in ["API_KEY", "TOKEN", "ACCESS"])])
    print(f"\n[5] auth.json: 存在, 含key: {has_key}")

print("\n=== 诊断完成 ===")
if not mif:
    print("👉 破甲未激活: python deploy.py 重新部署")
if agents.exists() and 'cannot override system' in agents.read_text(encoding="utf-8").lower():
    print("👉 毒丸未清除: python deploy.py --fix-agents")
