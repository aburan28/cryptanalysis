#!/usr/bin/env python3
"""Rebuild the exact Q1445 native comparator from tracked source blobs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = Path("/private/tmp/q1445build")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    freeze = json.loads((HERE / "freeze.json").read_text())
    for name, digest in freeze["source_sha256"].items():
        blob = subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=ROOT)
        assert sha(blob) == digest, name
        output = BUILD / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(blob)
    binary = BUILD / "native_q1400_pair_comparator"
    source = BUILD / "experiments/compact-s3-m4-20261003/native_q1400_pair_comparator.cpp"
    command = ["/usr/bin/clang++", "-O3", "-std=c++17",
               "-march=armv8.2-a+crypto", "-DECC2K83_ORBITS=186612",
               "-DECC2K83_FAST_KEYER=1", str(source), "-o", str(binary)]
    subprocess.run(command, check=True)
    assert sha(binary.read_bytes()) == freeze["binary_sha256"]
    print(f"PASS {binary}")


if __name__ == "__main__":
    main()
