#!/usr/bin/env bash
# Local single-account smoke from package root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -d .venv ]]; then
  echo "missing .venv in $ROOT — create with: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if [[ ! -f config.json ]]; then
  echo "missing config.json — copy config.example.json and fill secrets"
  exit 1
fi

echo "=== 1) proxy probe ==="
PROXY=$(python3 -c "import json; print(json.load(open('config.json')).get('proxy',''))")
PROXY_DISPLAY=$(PROXY="$PROXY" python3 -c "import os; from webui.security_utils import redact_proxy; print(redact_proxy(os.environ.get('PROXY','')))")
echo "config.proxy=$PROXY_DISPLAY"
if [[ -n "$PROXY" ]]; then
  ip=$(curl -s -m 8 -x "$PROXY" https://api.ipify.org || true)
  echo "exit_ip=$ip"
fi

echo "=== 2) ready ==="
echo "Run a single register via: python -u run_batch_headless.py 1 1"
