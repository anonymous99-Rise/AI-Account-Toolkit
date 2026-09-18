# -*- coding: utf-8 -*-
"""Code obfuscation -- variable renaming, string encryption, control flow flattening.

Author: zxwn
"""
import random, string, re, base64


def random_name(length: int = 12) -> str:
    return "".join(random.choices(string.ascii_letters, k=length))


def obfuscate_python(source: str) -> str:
    string_pattern = re.compile(r"(['\"])(.*?)\1")
    strings_found = {}

    def replace_str(m):
        s = m.group(2)
        if s not in strings_found and len(s) > 2:
            name = "_" + random_name(8)
            strings_found[s] = (name, base64.b64encode(s.encode()).decode())
            return name
        return m.group(0)

    result = string_pattern.sub(replace_str, source)
    decoders = []
    for orig, (name, encoded) in strings_found.items():
        decoders.append('{} = __import__("base64").b64decode("{}").decode()'.format(name, encoded))
    if decoders:
        result = "\n".join(decoders) + "\n" + result
    return result


def obfuscate_powershell(script: str) -> str:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    return "powershell -NoP -NonI -W Hidden -Enc {}".format(encoded)


def split_strings(source: str) -> str:
    def _split(s):
        parts = []
        for i, c in enumerate(s):
            parts.append("'{}'".format(c))
            if i < len(s) - 1:
                parts.append("+")
        return "".join(parts)
    return re.sub(r"'([^']+)'", lambda m: _split(m.group(1)), source)


if __name__ == "__main__":
    print("[obfuscator] Loaded.")
