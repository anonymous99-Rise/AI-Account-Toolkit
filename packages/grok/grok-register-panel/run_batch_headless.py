#!/usr/bin/env python3
from pathlib import Path
import os

os.chdir(str(Path(__file__).resolve().parent))

import json
import sys
import time
import types

from batch_supervisor import (
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_MAX_RESTARTS,
    run_supervisor,
)
from secure_files import atomic_write_json, ensure_private_dir


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "log"


def _install_tkinter_stub() -> None:
    try:
        import tkinter  # noqa: F401
        return
    except ImportError:
        pass

    tk = types.ModuleType("tkinter")

    class _NullWidget:
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    for name in ("Tk", "StringVar", "IntVar", "BooleanVar"):
        setattr(tk, name, _NullWidget)
    tk.END = "end"
    tk.DISABLED = "disabled"
    tk.NORMAL = "normal"
    tk.LEFT = "left"
    tk.RIGHT = "right"
    tk.BOTH = "both"
    tk.X = "x"
    tk.Y = "y"
    tk.W = "w"
    tk.E = "e"
    tk.N = "n"
    tk.S = "s"

    ttk_module = types.ModuleType("tkinter.ttk")
    for name in (
        "Frame",
        "Label",
        "Button",
        "Entry",
        "Combobox",
        "Spinbox",
        "Checkbutton",
        "Notebook",
        "Style",
        "Scrollbar",
        "Treeview",
    ):
        setattr(ttk_module, name, _NullWidget)
    scrolled_text = types.ModuleType("tkinter.scrolledtext")
    scrolled_text.ScrolledText = _NullWidget
    messagebox = types.ModuleType("tkinter.messagebox")
    messagebox.showinfo = lambda *args, **kwargs: None
    messagebox.showerror = messagebox.showinfo
    messagebox.showwarning = messagebox.showinfo
    messagebox.askyesno = messagebox.showinfo
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.ttk"] = ttk_module
    sys.modules["tkinter.scrolledtext"] = scrolled_text
    sys.modules["tkinter.messagebox"] = messagebox


def _redact_proxy(url: object) -> str:
    text = str(url or "")
    if "://" in text and "@" in text.split("://", 1)[-1]:
        scheme, rest = text.split("://", 1)
        _credentials, host = rest.rsplit("@", 1)
        return f"{scheme}://***@{host}"
    return text


def _run_child(count: int, workers: int) -> int:
    _install_tkinter_stub()
    sys.path.insert(0, str(ROOT))
    for key in (
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "all_proxy",
    ):
        os.environ.pop(key, None)

    import connectivity
    import grok_register_ttk as app

    connectivity.has_blocking_xai_failure = lambda _results: False
    config_path = ROOT / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["register_count"] = count
    config["register_workers"] = workers
    atomic_write_json(config_path, config)
    print(
        f"[env] DISPLAY={os.environ.get('DISPLAY')!r} time={time.strftime('%F %T')}",
        flush=True,
    )
    app.load_config()
    app._wire_runtime_modules()
    print(
        f"[batch] count={count} workers={workers} proxy={_redact_proxy(app.config.get('proxy'))}",
        flush=True,
    )
    app.run_registration_cli(count)
    print("[batch] finished", flush=True)
    return 0


def _child_command(remaining: int, workers: int) -> list[str]:
    return [
        sys.executable,
        "-u",
        str(ROOT / "run_batch_headless.py"),
        "--batch-child",
        str(remaining),
        str(workers),
    ]


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    child_mode = bool(args and args[0] == "--batch-child")
    if child_mode:
        args.pop(0)
    count = int(args[0]) if args else 9
    workers = int(args[1]) if len(args) > 1 else 3
    count = max(1, count)
    workers = max(1, min(workers, 24, count))
    if child_mode:
        return _run_child(count, workers)

    ensure_private_dir(LOG_DIR)
    progress_file = LOG_DIR / f".batch-progress-{os.getpid()}.json"
    idle_timeout = _env_int(
        "GROK_BATCH_IDLE_TIMEOUT",
        DEFAULT_IDLE_TIMEOUT,
        60,
    )
    max_restarts = _env_int(
        "GROK_BATCH_MAX_RESTARTS",
        DEFAULT_MAX_RESTARTS,
        0,
    )
    return run_supervisor(
        count,
        workers,
        _child_command,
        progress_file=progress_file,
        idle_timeout=idle_timeout,
        max_restarts=max_restarts,
    )


if __name__ == "__main__":
    raise SystemExit(main())
