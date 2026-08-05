#!/usr/bin/env python3
from __future__ import annotations
import os, sys, time, json
from pathlib import Path
from secure_files import atomic_write_json
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
for k in ("http_proxy","https_proxy","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","all_proxy"):
    os.environ.pop(k, None)
print(f"[env] DISPLAY={os.environ.get('DISPLAY')!r}", flush=True)
print(f"[env] time={time.strftime('%F %T')}", flush=True)
import connectivity
import grok_register_ttk as app
from webui.security_utils import redact_proxy
connectivity.has_blocking_xai_failure = lambda results: False
count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
workers = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("REGISTER_WORKERS", "2") or 2)
workers = max(1, min(workers, 8, count))
cfg_path = ROOT / "config.json"
cfg = json.loads(cfg_path.read_text())
cfg["register_count"] = count
cfg["register_workers"] = workers
atomic_write_json(cfg_path, cfg)
app.load_config()
app._wire_runtime_modules()
print(f"[smoke] count={count} workers={workers} proxy={redact_proxy(app.config.get('proxy'))} cpa={app.config.get('cpa_auth_dir')}", flush=True)
app.run_registration_cli(count)
print("[smoke] finished", flush=True)
