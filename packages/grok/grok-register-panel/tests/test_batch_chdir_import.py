# -*- coding: utf-8 -*-
"""Execute shipped run_batch_headless header: Path must exist before chdir."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "run_batch_headless.py"


def test_batch_header_chdir_no_nameerror():
    src_lines = BATCH.read_text(encoding="utf-8").splitlines()
    buf = []
    for ln in src_lines:
        buf.append(ln)
        if "os.chdir(str(Path(__file__).resolve().parent))" in ln:
            break
    else:
        raise AssertionError("chdir line not found")
    text = "\n".join(buf)
    assert text.find("from pathlib import Path") < text.find("os.chdir")
    ns = {"__file__": str(BATCH), "__name__": "__not_main__"}
    exec(compile(text, str(BATCH), "exec"), ns)
    assert Path(os.getcwd()).resolve() == ROOT.resolve()


if __name__ == "__main__":
    test_batch_header_chdir_no_nameerror()
    print("OK batch_chdir")
