# -*- coding: utf-8 -*-
"""Output encoding for cloud audit bypass.

Methods: base64, ZWSP insertion, Cyrillic homoglyph substitution,
fullwidth ASCII, ROT13, code-block smuggling, chain encoding.

Author: zxwn
"""
import base64, random

ZWSP = "\u200b"
HOMOGLYPH_MAP = {
    "a": "\u0430", "e": "\u0435", "i": "\u0456", "o": "\u043e",
    "p": "\u0440", "c": "\u0441", "y": "\u0443", "x": "\u0445",
    "A": "\u0410", "B": "\u0412", "E": "\u0415", "H": "\u041d",
    "M": "\u041c", "T": "\u0422", "K": "\u041a", "O": "\u041e",
}
HOMOGLYPH_REVERSE = {v: k for k, v in HOMOGLYPH_MAP.items()}


def base64_encode(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode()


def base64_decode(encoded: str) -> str:
    return base64.b64decode(encoded.encode()).decode("utf-8")


def zwsp_insert(text: str, density: float = 0.5) -> str:
    result = []
    for ch in text:
        result.append(ch)
        if random.random() < density and ch not in (" ", "\n", "\t"):
            result.append(ZWSP)
    return "".join(result)


def zwsp_remove(text: str) -> str:
    return text.replace(ZWSP, "")


def homoglyph_replace(text: str, ratio: float = 0.3) -> str:
    result = []
    for ch in text:
        if ch in HOMOGLYPH_MAP and random.random() < ratio:
            result.append(HOMOGLYPH_MAP[ch])
        else:
            result.append(ch)
    return "".join(result)


def homoglyph_reverse(text: str) -> str:
    result = []
    for ch in text:
        result.append(HOMOGLYPH_REVERSE.get(ch, ch))
    return "".join(result)


def fullwidth_encode(text: str) -> str:
    result = []
    for ch in text:
        code = ord(ch)
        if 0x21 <= code <= 0x7E:
            result.append(chr(code + 0xFF00 - 0x20))
        else:
            result.append(ch)
    return "".join(result)


def fullwidth_decode(text: str) -> str:
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFF00 + 0x20))
        else:
            result.append(ch)
    return "".join(result)


def code_block_smuggle(content: str, lang: str = "python") -> str:
    lines = content.split("\n")
    if lang in ("python", "ruby", "bash", "yml", "yaml"):
        commented = "\n".join("# @NOTE: {}".format(l) for l in lines)
    elif lang in ("c", "cpp", "java", "js", "go", "rust"):
        commented = "\n".join("// @NOTE: {}".format(l) for l in lines)
    elif lang in ("html", "xml", "svg"):
        commented = "<!-- @NOTE:\n{}\n-->".format(content)
    else:
        commented = "\n".join("/* @NOTE: {} */".format(l) for l in lines)
    return "```{}\n{}\n```".format(lang, commented)


def rot13(text: str) -> str:
    result = []
    for ch in text:
        if "a" <= ch <= "z":
            result.append(chr((ord(ch) - ord("a") + 13) % 26 + ord("a")))
        elif "A" <= ch <= "Z":
            result.append(chr((ord(ch) - ord("A") + 13) % 26 + ord("A")))
        else:
            result.append(ch)
    return "".join(result)


def chain_encode(text: str, methods: list = None) -> str:
    if methods is None:
        methods = ["zwsp", "homoglyph"]
    result = text
    for m in methods:
        if m == "base64": result = base64_encode(result)
        elif m == "zwsp": result = zwsp_insert(result)
        elif m == "homoglyph": result = homoglyph_replace(result)
        elif m == "fullwidth": result = fullwidth_encode(result)
        elif m == "rot13": result = rot13(result)
    return result


def chain_decode(text: str, methods: list = None) -> str:
    if methods is None:
        methods = ["zwsp", "homoglyph"]
    result = text
    for m in reversed(methods):
        if m == "base64": result = base64_decode(result)
        elif m == "zwsp": result = zwsp_remove(result)
        elif m == "homoglyph": result = homoglyph_reverse(result)
        elif m == "fullwidth": result = fullwidth_decode(result)
        elif m == "rot13": result = rot13(result)
    return result


if __name__ == "__main__":
    test = "This is sensitive content for cloud audit bypass testing."
    print("Original: {}".format(test))
    print("Base64:   {}".format(base64_encode(test)))
    print("ZWSP:     [{}]".format(zwsp_insert(test)))
    print("Homoglyph:[{}]".format(homoglyph_replace(test, 0.5)))
    print("Fullwidth:[{}]".format(fullwidth_encode(test)))
    print("ROT13:    {}".format(rot13(test)))
