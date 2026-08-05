# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import grok_register_ttk as register
from webui import proxy_store


def test_worker_hot_reload_only_changes_next_account_proxy():
    previous_paths = (
        proxy_store.STATE_PATH,
        proxy_store.LOCK_PATH,
        proxy_store.LEGACY_PATH,
    )
    previous_proxy = register.config.get("proxy")
    previous_workers = register.config.get("register_workers")
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        try:
            proxy_store.STATE_PATH = base / "log" / "proxy_pool.json"
            proxy_store.LOCK_PATH = base / "log" / "proxy_pool.json.lock"
            proxy_store.LEGACY_PATH = base / "proxies.txt"
            register.config["proxy"] = "http://legacy.example:7890"
            register.config["register_workers"] = 2

            assert register.load_proxy_pool() == ["http://legacy.example:7890"]

            imported = proxy_store.import_proxies(
                "a.example:8000:user:pass\nb.example:8001:user:pass"
            )
            assert register.load_proxy_pool() == []
            try:
                register.pick_proxy_for_worker(0, 0)
            except RuntimeError as exc:
                assert "没有健康且启用的代理" in str(exc)
            else:
                raise AssertionError("unknown managed proxies must not reach workers")

            for offset, item in enumerate(imported["items"]):
                proxy_store._apply_probe_result(
                    item["id"],
                    {
                        "ok": True,
                        "exit_ip": f"198.51.100.{10 + offset}",
                        "asn": 64510 + offset,
                        "asn_org": "Worker Test",
                        "latency_ms": 100 + offset,
                        "checked_at": "2026-07-30T00:00:00Z",
                    },
                )

            current = register.pick_proxy_for_worker(0, 0)
            register.set_thread_proxy(current)
            assert "a.example:8000" in current
            proxy_store.record_proxy_result(current, "risk", "policy deny")

            # State changes do not mutate the current account's bound proxy.
            assert register.get_thread_proxy() == current
            next_account = register.pick_proxy_for_worker(0, 1)
            assert next_account != current
            assert "b.example:8001" in next_account
        finally:
            proxy_store.STATE_PATH, proxy_store.LOCK_PATH, proxy_store.LEGACY_PATH = previous_paths
            register.config["proxy"] = previous_proxy
            register.config["register_workers"] = previous_workers


if __name__ == "__main__":
    test_worker_hot_reload_only_changes_next_account_proxy()
    print("OK proxy worker integration")
