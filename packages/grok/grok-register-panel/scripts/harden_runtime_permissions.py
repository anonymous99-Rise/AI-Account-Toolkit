#!/usr/bin/env python3
"""Apply owner-only permissions to runtime credentials and generated data."""

from __future__ import annotations

import argparse
from pathlib import Path


PRIVATE_DIRS = ("accounts", "cpa_auth", "grok2api_auth", "log")
PRIVATE_FILES = ("config.json", "proxies.txt", ".env.monitor")
PRIVATE_FILE_GLOBS = ("proxies*.txt", "stickies*.txt", "*.cache")


def chmod_if_regular(path: Path, mode: int) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    path.chmod(mode)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    changed_files = 0
    changed_dirs = 0

    for name in PRIVATE_DIRS:
        directory = root / name
        if directory.is_symlink():
            continue
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        changed_dirs += 1
        for path in directory.rglob("*"):
            if path.is_symlink():
                continue
            if path.is_dir():
                path.chmod(0o700)
                changed_dirs += 1
            elif chmod_if_regular(path, 0o600):
                changed_files += 1

    private_files = {root / name for name in PRIVATE_FILES}
    for pattern in PRIVATE_FILE_GLOBS:
        private_files.update(root.glob(pattern))
    for path in sorted(private_files):
        if path.name.endswith(".example.txt"):
            continue
        if chmod_if_regular(path, 0o600):
            changed_files += 1

    print(f"hardened {changed_dirs} directories and {changed_files} files under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
