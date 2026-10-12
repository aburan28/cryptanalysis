#!/usr/bin/env python3
"""Independently verify the swapped cover and its priority assignment."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-dual-orbit-20261011/verify_cover.py"
SPEC = importlib.util.spec_from_file_location("orbit_swap_independent", SOURCE)
independent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(independent)


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    raw = (HERE / "cover-swapped-rho0.bin").read_bytes()
    screen = json.loads((HERE / "screen.json").read_bytes())
    magic, radix, classes, seed_count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, seed_count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 15)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * seed_count
    assert digest(raw) == screen["cover_swapped_sha256"]
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    assert len(set(seeds)) == seed_count and seeds[0] == (0, 0)
    canonical, nodes = independent.orbit_partition()
    assert len(nodes) == classes
    node_index = {node: i for i, node in enumerate(nodes)}
    best = [None] * classes
    tau_covered = bytearray(classes)
    for seed_id, seed in enumerate(seeds):
        for map_id in range(4):
            image = independent.action(seed, map_id)
            value = independent.norm(image)
            if value > independent.SIZE:
                continue
            target = node_index[canonical[independent.residue(image)]]
            tau_covered[target] |= map_id < 3
            candidate = ((map_id == 3, value, map_id, seed_id), seed_id, map_id)
            if best[target] is None or candidate < best[target]:
                best[target] = candidate
    assert all(entry is not None for entry in best)
    used = set()
    residues = 0
    rho_assignments = 0
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
        rho_assignments += map_id == 3
        used.add(seed_id)
    assert residues == independent.SIZE and len(used) == seed_count
    assert rho_assignments == screen["final_rho_only_classes"] == \
        sum(not value for value in tau_covered)
    result = {"schema": 1, "status": "passed",
              "classes": classes, "residues": residues,
              "seed_count": seed_count, "used_seed_count": len(used),
              "rho_assignments": rho_assignments,
              "cover_sha256": digest(raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "independent_actions_sha256": digest(SOURCE.read_bytes())}
    (HERE / "cover-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
