#!/usr/bin/env python3
"""Independently audit priority digits over all radix-1024 residues."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-dual-orbit-20261011/verify_cover.py"
SPEC = importlib.util.spec_from_file_location("cycle_cover_independent", SOURCE)
independent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(independent)
VERSIONS = (("pruned", 68_743), ("exchanged", 67_338),
            ("refined", 67_338))


def digest(raw):
    return sha256(raw).hexdigest()


def check(name, expected_count, canonical, nodes, node_index):
    raw = (HERE / f"cover-cycle-{name}.bin").read_bytes()
    receipt_name = {"pruned": "prune-screen.json",
                    "exchanged": "exchange-screen.json",
                    "refined": "refine-screen.json"}[name]
    receipt = json.loads((HERE / receipt_name).read_bytes())
    assert digest(raw) == receipt["cover_sha256"]
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, expected_count, 15)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    assert seeds[0] == (0, 0) and len(set(seeds)) == count
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
            key = (map_id == 3, value, map_id, seed_id)
            if best[target] is None or key < best[target][0]:
                best[target] = (key, seed_id, map_id)
    assert all(best)
    used = set()
    map_counts = Counter()
    residues = 0
    for index, node in enumerate(nodes):
        code = struct.unpack_from("<I", raw, 20 + 4 * index)[0]
        seed_id, map_id = code >> 4, code & 15
        assert (seed_id, map_id) == best[index][1:]
        image = independent.action(seeds[seed_id], map_id)
        actual = {independent.residue(value)
                  for value in independent.unit_images(image)}
        expected = {independent.residue(value)
                    for value in independent.unit_images(divmod(node, radix))}
        assert actual == expected
        assert all(canonical[value] == node for value in actual)
        residues += len(actual)
        used.add(seed_id)
        map_counts[map_id] += 1
    assert residues == independent.SIZE and len(used) == count
    assert map_counts[3] == sum(not value for value in tau_covered)
    assert map_counts[3] == receipt["rho_only_classes"] if name == "pruned" \
        else map_counts[3] == receipt["final_rho_only_classes"]
    assert dict(sorted(map_counts.items())) == \
        {int(key): value for key, value in receipt["assigned_maps"].items()}
    return {"name": name, "seed_count": count, "classes": classes,
            "residues": residues, "rho_only_classes": map_counts[3],
            "cover_sha256": digest(raw)}


def main():
    canonical, nodes = independent.orbit_partition()
    node_index = {node: i for i, node in enumerate(nodes)}
    results = [check(name, count, canonical, nodes, node_index)
               for name, count in VERSIONS]
    bound = json.loads((HERE.parent /
                        "prime-j0-tau-bound-20261011/exact-check.json").read_bytes())
    assert bound["status"] == "passed"
    assert bound["rho_only_class_lower_bound_at_budget"] == 6_079
    assert results[-1]["rho_only_classes"] >= 6_079
    result = {"schema": 1, "status": "passed", "covers": results,
              "exact_lower_bound": 6_079,
              "refined_gap": results[-1]["rho_only_classes"] - 6_079,
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "independent_actions_sha256": digest(SOURCE.read_bytes())}
    (HERE / "cover-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
