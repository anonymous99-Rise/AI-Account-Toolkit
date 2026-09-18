# -*- coding: utf-8 -*-
"""License bypass utilities -- Android/iOS/SQLite DB patcher, trial reset.

Author: zxwn
"""
import sqlite3, plistlib, struct, os
from pathlib import Path
from datetime import datetime, timedelta


def patch_android_prefs(db_path: str, table: str = "license") -> dict:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    result = {"tables_found": tables}
    for t in tables:
        try:
            cur.execute("SELECT * FROM {} LIMIT 1".format(t))
            cols = [d[0] for d in cur.description]
            result[t] = {"columns": cols}
        except:
            pass
        for col in cols:
            if any(kw in col.lower() for kw in ["expir", "valid", "trial", "license", "pro", "premium"]):
                cur.execute("UPDATE {} SET {} = ?".format(t, col), ("9999-12-31",))
                result.setdefault("patched", []).append("{}.{}".format(t, col))
    conn.commit()
    conn.close()
    return result


def patch_ios_plist(plist_path: str) -> dict:
    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    patched = []
    stack = [(data, "root")]
    while stack:
        obj, path = stack.pop()
        if isinstance(obj, dict):
            for k, v in obj.items():
                if any(kw in k.lower() for kw in ["expir", "trial", "license", "pro", "unlock"]):
                    if isinstance(v, (bool, int)):
                        obj[k] = True if isinstance(v, bool) else 999999
                        patched.append("{}.{}".format(path, k))
                    elif isinstance(v, str) and v.isdigit():
                        obj[k] = "99999999"
                        patched.append("{}.{}".format(path, k))
                stack.append((v, "{}.{}".format(path, k)))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                stack.append((item, "{}[{}]".format(path, i)))
    out_path = plist_path + ".patched"
    with open(out_path, "wb") as f:
        plistlib.dump(data, f)
    return {"patched_keys": patched, "output": out_path}


def reset_trial_registry() -> list:
    import winreg
    found = []
    for hive, base in [
        (winreg.HKEY_CURRENT_USER, r"Software"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software"),
    ]:
        try:
            key = winreg.OpenKey(hive, base)
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(key, i)
                    if any(kw in sub.lower() for kw in ["trial", "license", "expir"]):
                        found.append("{}\\{}".format("HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM", sub))
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except:
            pass
    return found


def generate_fake_license_file(product: str, features: list, days: int = 365) -> str:
    exp = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")
    return """[License]
Product={}
Expiry={}
Features={}
Signature={}
""".format(product, exp, ",".join(features), os.urandom(16).hex().upper())


if __name__ == "__main__":
    print("[license_bypass] Loaded.")
