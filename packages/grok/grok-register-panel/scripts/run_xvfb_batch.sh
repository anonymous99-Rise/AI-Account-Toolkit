#!/usr/bin/env bash
# Batch entry: Xvfb + dual workers (register_workers=2 in config.json)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COUNT="${1:-10}"
# update count only
python3 - "$COUNT" <<'PY'
import json
import sys
from pathlib import Path
from secure_files import atomic_write_json
p=Path("config.json")
c=json.loads(p.read_text())
c["register_count"]=int(sys.argv[1])
c["register_workers"]=2
atomic_write_json(p, c)
print("batch count", c["register_count"], "workers", c["register_workers"])
PY
exec ./scripts/run_xvfb_smoke.sh "$COUNT"
