#!/usr/bin/env python3
"""Reassign fixed rho0 seeds by map cost, then digit norm."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("priority_dual_cover", HERE / "screen.py")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
SOURCE = HERE / "cover-lowcost-rho0.bin"
OUTPUT = HERE / "cover-priority-rho0.bin"
RECEIPT = HERE / "priority-screen.json"


def digest(raw):
    return sha256(raw).hexdigest()


def score(seed, map_id, seed_id):
    return (map_id == 3, base.screen.norm(base.mapped(seed, map_id)),
            map_id, seed_id)


def main():
    raw = SOURCE.read_bytes()
    magic, radix, classes, seed_count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, seed_count, mask) == \
        (b"LC19", 1024, 174_764, 67_338, 0b1111)
    seed_start = 20 + 4 * classes
    assert len(raw) == seed_start + 4 * seed_count
    seed_bytes = raw[seed_start:]
    seeds = list(struct.iter_unpack("<hh", seed_bytes))
    assert seeds[0] == (0, 0)
    canonical, nodes, _, _ = base.parent.full_classes()
    node_index = {node: index for index, node in enumerate(nodes)}
    best = [None] * classes
    options = [0] * classes
    for seed_id, seed in enumerate(seeds):
        for target, map_id in base.offers_for_seed(seed, canonical, node_index):
            if map_id >= 4:
                continue
            options[target] += 1
            candidate = (score(seed, map_id, seed_id), seed_id, map_id)
            if best[target] is None or candidate < best[target]:
                best[target] = candidate
    assert all(entry is not None for entry in best)
    assignments = [(seed_id, map_id) for _, seed_id, map_id in best]
    assert assignments[nodes.index(0)] == (0, 0)
    used = {seed_id for seed_id, _ in assignments}
    counts = Counter(base.MAP_NAMES[map_id] for _, map_id in assignments)
    old_rho = sum((struct.unpack_from("<I", raw, 20 + 4 * i)[0] & 15) == 3
                  for i in range(classes))
    packed = bytearray(struct.pack("<4sIIII", b"LP21", radix, classes,
                                   seed_count, mask))
    for seed_id, map_id in assignments:
        packed.extend(struct.pack("<I", seed_id << 4 | map_id))
    packed.extend(seed_bytes)
    OUTPUT.write_bytes(packed)
    panel = base.replay_panel(assignments, seeds, nodes, canonical)
    receipt = {"schema": 1, "status": "screened", "policy": "tau_first_then_norm",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "source_cover_sha256": digest(raw),
               "atlas_sha256": digest(packed),
               "atlas_bytes": len(packed), "seed_count": seed_count,
               "used_seed_count": len(used),
               "unit_classes": classes, "multiple_option_classes": sum(x > 1 for x in options),
               "old_rho_classes": old_rho,
               "map_class_counts": dict(sorted(counts.items())),
               "design_panel": panel}
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"seed_count": seed_count, "used_seed_count": len(used),
                      "old_rho_classes": old_rho,
                      "new_rho_classes": counts["rho"],
                      "active_branch_cases": panel["active_branch_cases"],
                      "terminal_bound_failures": panel["terminal_bound_failures"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
