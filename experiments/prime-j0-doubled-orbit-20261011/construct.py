#!/usr/bin/env python3
"""Add norm-four doubling offers to the frozen fixed-memory scalar cover."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "prime-j0-cycle-compression-20261011/cover-cycle-compressed.bin"
SOURCE = HERE.parent / "prime-j0-dual-orbit-20261011/screen.py"
SPEC = importlib.util.spec_from_file_location("doubled_orbit_source", SOURCE)
dual = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dual)
RADIX = 1024
CLASSES = 174_764
SEEDS = 67_338
DOUBLE_MAP = 4


def digest(raw):
    return sha256(raw).hexdigest()


def load(raw):
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", RADIX, CLASSES, SEEDS, 15)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    assigned = list(struct.unpack_from(f"<{classes}I", raw, 20))
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    assert seeds[0] == (0, 0) and len(set(seeds)) == count
    return assigned, seeds


def main():
    old_raw = BASE.read_bytes()
    assigned, seeds = load(old_raw)
    canonical, nodes, _, _ = dual.parent.full_classes()
    assert len(nodes) == CLASSES
    node_index = {node: index for index, node in enumerate(nodes)}
    rho_classes = {index for index, code in enumerate(assigned)
                   if code & 15 == 3}
    assert len(rho_classes) == 6_094
    best = {}
    eligible = 0
    for seed_id, (a, b) in enumerate(seeds):
        digit = (2 * a, 2 * b)
        value = dual.screen.norm(digit)
        if value > RADIX * RADIX:
            continue
        eligible += 1
        target = node_index[canonical[dual.screen.index(digit, RADIX)]]
        if target not in rho_classes:
            continue
        key = (value, seed_id)
        if target not in best or key < best[target]:
            best[target] = key
    assert len(best) == 1_416
    updated = assigned.copy()
    for target, (_, seed_id) in best.items():
        updated[target] = (seed_id << 4) | DOUBLE_MAP
    output = bytearray(struct.pack("<4sIIII", b"LP21", RADIX,
                                   CLASSES, SEEDS, 31))
    output.extend(struct.pack(f"<{CLASSES}I", *updated))
    for pair in seeds:
        output.extend(struct.pack("<hh", *pair))
    output = bytes(output)
    assert len(output) == len(old_raw)
    assert all((new == old) == (index not in best)
               for index, (old, new) in enumerate(zip(assigned, updated)))
    (HERE / "cover-doubled.bin").write_bytes(output)
    counts = dict(sorted(Counter(code & 15 for code in updated).items()))
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "base_cover_sha256": digest(old_raw),
               "cover_sha256": digest(output),
               "seed_count": SEEDS, "class_count": CLASSES,
               "eligible_selected_seeds": eligible,
               "double_assignments": len(best),
               "rho_before": len(rho_classes),
               "rho_after": counts[3],
               "map_counts": counts,
               "cover_bytes": len(output)}
    (HERE / "screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
