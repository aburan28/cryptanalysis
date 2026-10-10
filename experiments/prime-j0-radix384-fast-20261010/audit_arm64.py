#!/usr/bin/env python3
"""Count reciprocal-multiply instructions before the first orbit lookup."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess

NAMES = ("multiply_u256_radix384", "multiply_u256_radix384_fast")


def count(binary, symbols, name):
    matches = [line.split()[-1] for line in symbols.splitlines()
               if "unit_orbit_windows" in line and name + "17h" in line]
    if len(matches) != 1:
        raise ValueError(f"expected one symbol for {name}: {matches}")
    asm = subprocess.check_output(
        ["otool", "-tvV", "-p", matches[0], str(binary)], text=True
    )
    if "OrbitAtlas13digit_residue" not in asm:
        raise ValueError(f"orbit lookup absent from {name}")
    first = asm.split("OrbitAtlas13digit_residue", 1)[0]
    return {op: len(re.findall(r"\t" + op + r"\t", first))
            for op in ("umulh", "umull", "smull", "udiv")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("this audit targets the physical macOS ARM64 build")
    binary = args.binary.resolve(strict=True)
    symbols = subprocess.check_output(["nm", str(binary)], text=True)
    counts = {name: count(binary, symbols, name) for name in NAMES}
    assert counts[NAMES[0]]["umulh"] + counts[NAMES[0]]["umull"] == 12
    assert counts[NAMES[1]]["umulh"] + counts[NAMES[1]]["umull"] == 4
    assert counts[NAMES[0]]["udiv"] == counts[NAMES[1]]["udiv"] == 0
    print(json.dumps({
        "schema": 1,
        "method": "instructions before first OrbitAtlas::digit_residue call",
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "machine": platform.machine(),
        "counts": counts,
        "timing_class": "static_assembly_only",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
