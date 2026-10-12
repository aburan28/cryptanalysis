#!/usr/bin/env python3
"""Encode direct orbit classes as aligned code plus canonical digit."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ADIC = ROOT / "prime-j0-adic-orbit-20261011"
SPEC = importlib.util.spec_from_file_location("adic_fused_source", ADIC / "verify_group.py")
adic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adic)
CLASSES = 174_764
SEEDS = 83_051


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    source = ADIC / "atlas-r1024-full-adic-orbit.bin"
    terminal = ADIC / "atlas-r1024-terminal-adic-orbit.bin"
    old = adic.AdicFullAtlas(source)
    records = bytearray()
    low = [0, 0]
    high = [0, 0]
    for expected, (class_index, (a, b)) in enumerate(adic.index.representatives()):
        assert class_index == expected
        digit, seed_id, exponent, unit = old.decode(a, b)
        assert -32768 <= digit[0] <= 32767
        assert -32768 <= digit[1] <= 32767
        code = (seed_id << 5) | (exponent << 3) | unit
        assert code < 1 << 22
        records.extend(struct.pack("<Ihh", code, *digit))
        for axis in range(2):
            low[axis] = min(low[axis], digit[axis])
            high[axis] = max(high[axis], digit[axis])
    assert len(records) == 8 * CLASSES
    old_raw = source.read_bytes()
    seeds = old_raw[-4 * SEEDS:]
    assert len(seeds) == 4 * SEEDS
    raw = struct.pack("<4sIII", b"FO18", 1024, CLASSES, SEEDS) \
        + records + seeds
    output = HERE / "atlas-r1024-full-fused-orbit.bin"
    output.write_bytes(raw)
    terminal_output = HERE / "atlas-r1024-terminal-fused-orbit.bin"
    terminal_output.write_bytes(terminal.read_bytes())
    assert len(raw) == 1_730_332
    prior_native_bytes = 65_596_552
    projected = prior_native_bytes + 5 * CLASSES
    assert projected == 66_470_372 < 64 * 1024 * 1024
    receipt = {"schema": 1, "status": "constructed",
               "generator_sha256": digest(Path(__file__)),
               "parent_atlas_sha256": digest(source),
               "full_atlas_sha256": digest(output),
               "terminal_atlas_sha256": digest(terminal_output),
               "record_bytes": 8, "classes": CLASSES, "seeds": SEEDS,
               "canonical_digit_min": low,
               "canonical_digit_max": high,
               "full_atlas_bytes": len(raw),
               "projected_retained_bytes": projected,
               "reported_cache_bytes": 64 * 1024 * 1024,
               "nominal_cache_headroom_bytes": 64 * 1024 * 1024 - projected}
    (HERE / "atlas-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
