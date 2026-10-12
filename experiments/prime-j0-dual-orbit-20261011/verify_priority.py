#!/usr/bin/env python3
"""Independently verify priority assignments and complete residue coverage."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "priority_independent_actions", HERE / "verify_cover.py")
independent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(independent)


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    raw = (HERE / "cover-priority-rho0.bin").read_bytes()
    magic, radix, classes, seed_count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, seed_count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 0b1111)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * seed_count
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    canonical, nodes = independent.orbit_partition()
    assert len(nodes) == classes
    node_index = {node: i for i, node in enumerate(nodes)}
    best = [None] * classes
    for seed_id, seed in enumerate(seeds):
        for map_id in range(4):
            image = independent.action(seed, map_id)
            value = independent.norm(image)
            if value > independent.SIZE:
                continue
            target = node_index[canonical[independent.residue(image)]]
            candidate = ((map_id == 3, value, map_id, seed_id), seed_id, map_id)
            if best[target] is None or candidate < best[target]:
                best[target] = candidate
    assert all(entry is not None for entry in best)
    used = set()
    residues = 0
    for class_index, node in enumerate(nodes):
        code = struct.unpack_from("<I", raw, 20 + 4 * class_index)[0]
        seed_id, map_id = code >> 4, code & 15
        assert seed_id < seed_count and map_id < 4
        assert (seed_id, map_id) == best[class_index][1:]
        image = independent.action(seeds[seed_id], map_id)
        actual = {independent.residue(value)
                  for value in independent.unit_images(image)}
        expected = {independent.residue(value)
                    for value in independent.unit_images(divmod(node, radix))}
        assert actual == expected
        assert all(canonical[value] == node for value in actual)
        residues += len(actual)
        used.add(seed_id)
    assert residues == independent.SIZE and len(used) == seed_count
    screen = json.loads((HERE / "priority-screen.json").read_bytes())
    assert digest(raw) == screen["atlas_sha256"]
    assert screen["used_seed_count"] == len(used)
    receipt = {"schema": 1, "status": "passed", "classes": classes,
               "residues": residues, "seed_count": seed_count,
               "atlas_sha256": digest(raw),
               "verifier_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "priority-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
