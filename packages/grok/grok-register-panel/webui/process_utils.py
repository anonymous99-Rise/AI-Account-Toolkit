"""Process discovery and termination scoped to one project root."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path

import psutil

try:
    from secure_files import atomic_write_text
except ImportError:  # running from webui/
    import sys

    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from secure_files import atomic_write_text


class ProcessInspectionError(RuntimeError):
    pass


PROCESS_ERRORS = (psutil.Error, OSError, TypeError, ValueError)


def _process_snapshot(process) -> dict | None:
    try:
        info = getattr(process, "info", None)
        if not isinstance(info, dict):
            info = process.as_dict(
                attrs=("pid", "cwd", "cmdline", "create_time"),
                ad_value=None,
            )
        pid = int(info.get("pid"))
        cwd_value = info.get("cwd")
        cmdline_value = info.get("cmdline")
        if not cwd_value or not isinstance(cmdline_value, (list, tuple)):
            return None
        cwd = Path(str(cwd_value)).resolve()
        cmdline = [str(part) for part in cmdline_value if str(part)]
        created = info.get("create_time")
        create_time = float(created) if created is not None else None
        return {
            "pid": pid,
            "cwd": cwd,
            "cmdline": cmdline,
            "create_time": create_time,
        }
    except PROCESS_ERRORS:
        return None


def _resolved_arg(arg: str, cwd: Path) -> Path | None:
    if not arg or arg.startswith("-"):
        return None
    candidate = Path(arg)
    if not candidate.is_absolute():
        candidate = cwd / candidate
    try:
        return candidate.resolve()
    except OSError:
        return None


def _snapshot_matches(
    snapshot: dict,
    root: str | os.PathLike[str],
    script_names: tuple[str, ...] | list[str],
) -> bool:
    project_root = Path(root).resolve()
    process_cwd = snapshot.get("cwd")
    if process_cwd != project_root:
        return False
    expected = {(project_root / name).resolve() for name in script_names}
    return any(
        _resolved_arg(arg, process_cwd) in expected
        for arg in snapshot.get("cmdline") or []
    )


def process_matches(
    pid: int,
    root: str | os.PathLike[str],
    script_names: tuple[str, ...] | list[str],
) -> bool:
    try:
        snapshot = _process_snapshot(psutil.Process(int(pid)))
    except PROCESS_ERRORS:
        return False
    return bool(snapshot and _snapshot_matches(snapshot, root, script_names))


def _format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}-{hours:02d}:{minutes:02d}:{secs:02d}"
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def find_managed_processes(
    root: str | os.PathLike[str],
    script_names: tuple[str, ...] | list[str],
) -> list[dict]:
    found = []
    now = time.time()
    try:
        iterator = psutil.process_iter(
            attrs=("pid", "cwd", "cmdline", "create_time"),
            ad_value=None,
        )
        for process in iterator:
            snapshot = _process_snapshot(process)
            if not snapshot or not _snapshot_matches(snapshot, root, script_names):
                continue
            pid = snapshot["pid"]
            try:
                pgid = os.getpgid(pid) if os.name == "posix" else None
            except OSError:
                pgid = None
            created = snapshot.get("create_time")
            etime = _format_elapsed(now - created) if created is not None else ""
            found.append(
                {
                    "pid": pid,
                    "pgid": pgid,
                    "etime": etime,
                    "cmd": " ".join(snapshot["cmdline"])[:240],
                }
            )
    except (psutil.Error, OSError) as exc:
        raise ProcessInspectionError(
            "无法读取系统进程列表；Linux 容器请确认 /proc 已挂载，"
            "macOS/Windows 请重新安装 requirements.txt 中的 psutil"
        ) from exc
    return sorted(found, key=lambda item: item["pid"])


def write_pid_file(
    path: str | os.PathLike[str],
    pid: int,
) -> None:
    atomic_write_text(path, f"{int(pid)}\n")


def read_verified_pid_file(
    path: str | os.PathLike[str],
    root: str | os.PathLike[str],
    script_names: tuple[str, ...] | list[str],
) -> int | None:
    try:
        pid = int(Path(path).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return pid if process_matches(pid, root, script_names) else None


def terminate_managed_processes(
    root: str | os.PathLike[str],
    script_names: tuple[str, ...] | list[str],
    *,
    grace_seconds: float = 2.0,
) -> list[int]:
    processes = find_managed_processes(root, script_names)
    pids = {item["pid"] for item in processes}
    if not pids:
        return []

    if os.name != "posix":
        _terminate_process_trees(pids, grace_seconds)
        return sorted(pids)

    groups: set[int] = set()
    direct: set[int] = set()
    for pid in pids:
        try:
            pgid = os.getpgid(pid)
        except OSError:
            direct.add(pid)
            continue
        if pgid == pid:
            groups.add(pgid)
        else:
            direct.add(pid)

    for pgid in groups:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            pass
    for pid in direct:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    deadline = time.monotonic() + max(0.0, grace_seconds)
    while time.monotonic() < deadline:
        if not find_managed_processes(root, script_names):
            break
        time.sleep(0.1)

    remaining = find_managed_processes(root, script_names)
    for item in remaining:
        pid = item["pid"]
        try:
            pgid = os.getpgid(pid)
            if pgid == pid:
                os.killpg(pgid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    return sorted(pids)


def _terminate_process_trees(pids: set[int], grace_seconds: float) -> None:
    ordered = []
    seen = set()
    for pid in sorted(pids):
        try:
            process = psutil.Process(pid)
            children = process.children(recursive=True)
        except PROCESS_ERRORS:
            continue
        for target in [*reversed(children), process]:
            if target.pid in seen:
                continue
            seen.add(target.pid)
            ordered.append(target)
    for process in ordered:
        try:
            process.terminate()
        except PROCESS_ERRORS:
            pass
    _gone, alive = psutil.wait_procs(ordered, timeout=max(0.0, grace_seconds))
    for process in alive:
        try:
            process.kill()
        except PROCESS_ERRORS:
            pass
    if alive:
        psutil.wait_procs(alive, timeout=2)
