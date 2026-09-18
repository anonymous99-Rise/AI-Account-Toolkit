# -*- coding: utf-8 -*-
"""Multi-turn split delivery -- decompose content across rounds, reassemble.

Author: zxwn
"""
import re, base64, random


def split_by_sentence(text: str, turns: int = 3) -> list:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) <= turns:
        return sentences
    per_turn = len(sentences) // turns
    chunks = []
    for i in range(turns):
        start = i * per_turn
        end = start + per_turn if i < turns - 1 else len(sentences)
        chunks.append(" ".join(sentences[start:end]))
    return chunks


def variable_scatter(text: str) -> dict:
    words = text.split()
    var_map = {}
    for i, word in enumerate(words):
        var_name = "v{:04d}".format(i)
        var_map[var_name] = word
    assignments = ["{} = '{}'".format(k, v) for k, v in var_map.items()]
    assembly = " ".join(var_map.keys())
    return {"variables": assignments, "assembly": "result = ' '.join([{}])".format(assembly), "var_count": len(var_map)}


def chunked_base64(text: str, chunk_size: int = 80) -> list:
    b64 = base64.b64encode(text.encode()).decode()
    return [b64[i:i+chunk_size] for i in range(0, len(b64), chunk_size)]


def chunked_base64_assemble(chunks: list) -> str:
    b64 = "".join(chunks)
    return base64.b64decode(b64.encode()).decode()


def interleave_noise(text: str, noise_ratio: float = 0.3) -> tuple:
    noise_sentences = [
        "The weather is pleasant today.",
        "System diagnostic: all parameters within tolerance.",
        "Cache invalidation complete.",
        "Dependency graph resolved.",
        "Compression ratio: 3.2x.",
    ]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    mixed = []
    indices = []
    for s in sentences:
        mixed.append(s)
        indices.append(len(mixed) - 1)
        if random.random() < noise_ratio:
            mixed.append(random.choice(noise_sentences))
    return " ".join(mixed), indices


if __name__ == "__main__":
    test = "The target runs Apache 2.4 with a misconfigured .htaccess allowing traversal."
    chunks = split_by_sentence(test, 3)
    for i, c in enumerate(chunks):
        print("Turn {}: {}".format(i+1, c))
    scattered = variable_scatter(test)
    print("\nScattered into {} variables".format(scattered["var_count"]))
