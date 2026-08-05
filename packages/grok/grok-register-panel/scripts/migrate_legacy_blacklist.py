#!/usr/bin/env python3
"""Migrate source-embedded blacklist entries into runtime JSON state."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    os.environ["BLACKLIST_STATE_FILE"] = str(args.state.resolve())

    from webui.blacklist_store import import_legacy_source

    result = import_legacy_source(args.source)
    print(f"migrated {result.get('count', 0)} ASN entries to {args.state}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
