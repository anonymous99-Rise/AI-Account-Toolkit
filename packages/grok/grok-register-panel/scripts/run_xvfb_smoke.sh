#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COUNT="${1:-1}"
mkdir -p log accounts
TS=$(date +%Y%m%d-%H%M%S)
LOG="log/xvfb-smoke-${TS}.log"
echo "[run] xvfb-run smoke count=${COUNT} log=${LOG}"
/usr/bin/xvfb-run -a -s "-screen 0 1920x1080x24" \
  ./.venv/bin/python -u run_xvfb_smoke.py "${COUNT}" 2>&1 | tee "${LOG}"
echo "[run] wrote ${LOG}"
