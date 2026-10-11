#!/usr/bin/env python3
"""Reindex the frozen quotient cover with direct 2-adic class ranks."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUOTIENT = ROOT / "prime-j0-orbit-quotient-20261011"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


index = load("adic_index_builder", HERE / "index.py")
q = load("quotient_atlas_builder", QUOTIENT / "verify_group.py")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    source = QUOTIENT / "atlas-r1024-full-orbit-quotient.bin"
    terminal = QUOTIENT / "atlas-r1024-terminal-orbit-quotient.bin"
    prior = q.QuotientFullAtlas(source)
    codes = bytearray()
    exponent_classes = [0, 0, 0]
    for expected, (class_index, (a, b)) in enumerate(index.representatives()):
        assert class_index == expected
        digit, seed_id, exponent, unit = prior.decode(a, b)
        assert digit[0] % 1024 == a and digit[1] % 1024 == b
        assert q.parent.screen.norm(digit) <= 1024 * 1024
        code = (seed_id << 5) | (exponent << 3) | unit
        assert code < 1 << 24
        codes.extend(code.to_bytes(3, "little"))
        exponent_classes[exponent] += 1
    assert len(codes) == 3 * index.CLASS_COUNT
    original = source.read_bytes()
    seeds = original[-4 * prior.count:]
    assert len(seeds) == 4 * 83_051
    atlas = struct.pack("<4sIII", b"AO14", 1024, index.CLASS_COUNT,
                        prior.count) + codes + seeds
    output = HERE / "atlas-r1024-full-adic-orbit.bin"
    output.write_bytes(atlas)
    terminal_output = HERE / "atlas-r1024-terminal-adic-orbit.bin"
    terminal_output.write_bytes(terminal.read_bytes())
    assert len(atlas) == 856_512
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__)),
               "index_source_sha256": digest(HERE / "index.py"),
               "parent_atlas_sha256": digest(source),
               "full_atlas_sha256": digest(output),
               "terminal_atlas_sha256": digest(terminal_output),
               "classes": index.CLASS_COUNT, "seeds": prior.count,
               "class_exponents": exponent_classes,
               "header_bytes": 16, "code_bytes": len(codes),
               "seed_bytes": len(seeds), "full_atlas_bytes": len(atlas),
               "atlas_bytes_saved": len(original) - len(atlas)}
    (HERE / "atlas-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
