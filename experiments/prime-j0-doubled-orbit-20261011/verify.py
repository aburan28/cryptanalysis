#!/usr/bin/env python3
"""Independently verify norm-four assignment and every radix residue."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "prime-j0-cycle-compression-20261011/cover-cycle-compressed.bin"
SOURCE = HERE.parent / "prime-j0-dual-orbit-20261011/verify_cover.py"
SPEC = importlib.util.spec_from_file_location("doubled_orbit_independent", SOURCE)
independent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(independent)


def digest(raw):
    return sha256(raw).hexdigest()


def parse(raw, mask):
    magic, radix, classes, count, actual_mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, actual_mask) == \
        (b"LP21", 1024, 174_764, 67_338, mask)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    codes = struct.unpack_from(f"<{classes}I", raw, 20)
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    assert seeds[0] == (0, 0) and len(set(seeds)) == count
    return codes, seeds


def main():
    old_raw = BASE.read_bytes()
    new_raw = (HERE / "cover-doubled.bin").read_bytes()
    old, seeds = parse(old_raw, 15)
    new, new_seeds = parse(new_raw, 31)
    assert new_seeds == seeds
    screen_raw = (HERE / "screen.json").read_bytes()
    screen = json.loads(screen_raw)
    assert screen["status"] == "constructed"
    assert digest(old_raw) == screen["base_cover_sha256"]
    assert digest(new_raw) == screen["cover_sha256"]
    assert digest((HERE / "construct.py").read_bytes()) == \
        screen["source_sha256"]
    canonical, nodes = independent.orbit_partition()
    assert len(nodes) == 174_764
    node_index = {node: index for index, node in enumerate(nodes)}
    rho_classes = {index for index, code in enumerate(old)
                   if code & 15 == 3}
    assert len(rho_classes) == screen["rho_before"] == 6_094
    best = {}
    eligible = 0
    for seed_id, (a, b) in enumerate(seeds):
        digit = (a + a, b + b)
        value = independent.norm(digit)
        if value > independent.SIZE:
            continue
        eligible += 1
        target = node_index[canonical[independent.residue(digit)]]
        if target not in rho_classes:
            continue
        key = (value, seed_id)
        if target not in best or key < best[target]:
            best[target] = key
    assert eligible == screen["eligible_selected_seeds"]
    assert len(best) == screen["double_assignments"] == 1_416
    counts = Counter()
    residues = 0
    for index, node in enumerate(nodes):
        code = new[index]
        seed_id, map_id = code >> 4, code & 15
        assert seed_id < len(seeds) and 0 <= map_id <= 4
        expected = ((best[index][1] << 4) | 4) if index in best else old[index]
        assert code == expected
        seed = seeds[seed_id]
        digit = (seed[0] + seed[0], seed[1] + seed[1]) \
            if map_id == 4 else independent.action(seed, map_id)
        assert independent.norm(digit) <= independent.SIZE
        actual = {independent.residue(image)
                  for image in independent.unit_images(digit)}
        wanted = {independent.residue(image)
                  for image in independent.unit_images(divmod(node, 1024))}
        assert actual == wanted
        assert all(canonical[residue] == node for residue in actual)
        residues += len(actual)
        counts[map_id] += 1
    assert residues == independent.SIZE == 1_048_576
    assert counts[3] == screen["rho_after"] == 4_678
    assert dict(sorted(counts.items())) == \
        {int(key): value for key, value in screen["map_counts"].items()}
    receipt = {"schema": 1, "status": "passed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "independent_actions_sha256": digest(SOURCE.read_bytes()),
               "base_cover_sha256": digest(old_raw),
               "cover_sha256": digest(new_raw),
               "screen_sha256": digest(screen_raw),
               "seed_count": len(seeds), "class_count": len(nodes),
               "double_assignments": counts[4],
               "rho_assignments": counts[3],
               "residues_checked": residues}
    (HERE / "check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
