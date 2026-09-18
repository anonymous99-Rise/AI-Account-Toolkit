# -*- coding: utf-8 -*-
"""Tool Bundle Downloader — fetch portable security tools locally.

Downloads portable versions into tools/bin/ for offline use.
Run once: python tools/setup.py

Author: zxwn
"""
import subprocess, sys, os, shutil, urllib.request, zipfile, tarfile, io
from pathlib import Path

BASE = Path(__file__).resolve().parent
BIN = BASE / "bin"
BIN.mkdir(exist_ok=True)

print("=" * 55)
print("  NERV-BREAK-5.6 工具包下载器")
print("=" * 55)
print(f"  目标: {BIN}")
print()

def run(cmd, desc=""):
    print(f"  [{desc}] {cmd[:60]}...")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode == 0:
        print(f"    [OK]")
    else:
        print(f"    [FAIL] {r.stderr[:80]}")
    return r.returncode == 0

def download(url, filename, desc=""):
    """Download and extract a tool."""
    dest = BIN / filename
    if dest.exists():
        print(f"  [{desc}] Already installed")
        return True
    try:
        print(f"  [{desc}] Downloading...")
        data = urllib.request.urlopen(url, timeout=120).read()
        if filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                z.extractall(BIN)
        elif filename.endswith((".tar.gz", ".tgz")):
            with tarfile.open(fileobj=io.BytesIO(data)) as t:
                t.extractall(BIN)
        else:
            dest.write_bytes(data)
        print(f"    [OK] {len(data)/1024/1024:.1f}MB")
        return True
    except Exception as e:
        print(f"    [FAIL] {e}")
        return False

# ═══════════════════════════════════════════════════════════
# PYTHON TOOLS — pip install to tools/bin/
# ═══════════════════════════════════════════════════════════
print("\n── Python Tools ──")
pip_tools = [
    "sqlmap",           # SQL injection
    "pwntools",         # CTF/exploit framework
    "requests",         # HTTP (usually pre-installed)
]
for tool in pip_tools:
    run(f'"{sys.executable}" -m pip install {tool} --target "{BIN / "python"}" --no-deps --quiet 2>nul || "{sys.executable}" -m pip install {tool} --target "{BIN / "python"}" --quiet', tool)

# ═══════════════════════════════════════════════════════════
# PORTABLE TOOLS — download small standalone versions
# ═══════════════════════════════════════════════════════════
print("\n── Portable Downloads ──")
portable = [
    ("https://github.com/projectdiscovery/subfinder/releases/latest/download/subfinder_windows_amd64.zip", "subfinder_windows_amd64.zip", "subfinder"),
    ("https://github.com/projectdiscovery/nuclei/releases/latest/download/nuclei_windows_amd64.zip", "nuclei_windows_amd64.zip", "nuclei"),
]

for url, fname, name in portable:
    download(url, fname, name)

# ═══════════════════════════════════════════════════════════
# KALI WSL — recommended for full toolset
# ═══════════════════════════════════════════════════════════
print(f"\n── 完整工具集 ──")
try:
    r = subprocess.run(["wsl", "-l", "-q"], capture_output=True, text=True, timeout=10)
    if "kali" in r.stdout.lower():
        print("  [OK] WSL Kali 已安装")
    else:
        print("  [推荐] 安装 WSL Kali (60+ 工具):")
        print("    wsl --install -d kali-linux")
        print("    wsl -d kali-linux")
        print("    sudo apt update && sudo apt install -y kali-linux-headless")
except:
    print("  [--] WSL 不可用 (Windows only)")
    print("  [替代] Docker: docker pull kalilinux/kali-rolling")

print(f"\n  完成 — 运行 tools/check_tools.py 检查已安装工具")
