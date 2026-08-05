# -*- coding: utf-8 -*-
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = "/data/compose/grok-register-camoufox"

def test_no_live_path_in_key_modules():
    for rel in [
        "webui/blacklist_ops.py",
        "webui/blacklist_store.py",
        "webui/monitor.py",
        "webui/process_utils.py",
        "webui/recovery_ops.py",
        "run_batch_headless.py",
        "run_until_100.py",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert FORBIDDEN not in text, rel

if __name__ == "__main__":
    test_no_live_path_in_key_modules()
    print("OK no live hardcode")
