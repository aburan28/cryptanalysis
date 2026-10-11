#!/usr/bin/env python3
"""Independently replay every residue class in the low-cost covers."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("independent_dual_cover", HERE / "verify_cover.py")
independent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(independent)
MODES = (("rho0", (0, 1, 2, 3)),
         ("rho0_bar0", (0, 1, 2, 3, 6)),
         ("rho0_bar012", (0, 1, 2, 3, 6, 7, 8)))


def digest(raw):
    return sha256(raw).hexdigest()


def check_mode(name, allowed, expected, canonical, nodes):
    raw = (HERE / f"cover-lowcost-{name}.bin").read_bytes()
    magic, radix, classes, seed_count, mask = struct.unpack_from("<4sIIII", raw)
    expected_mask = sum(1 << code for code in allowed)
    assert (magic, radix, classes, mask) == \
        (b"LC19", independent.RADIX, len(nodes), expected_mask)
    seed_start = 20 + 4 * classes
    assert len(raw) == seed_start + 4 * seed_count
    seeds = list(struct.iter_unpack("<hh", raw[seed_start:]))
    assert seeds[0] == (0, 0) and len(seeds) == len(set(seeds)) == seed_count
    map_uses = Counter()
    used = set()
    checked = 0
    maximum_norm = 0
    for index, node in enumerate(nodes):
        code = struct.unpack_from("<I", raw, 20 + 4 * index)[0]
        seed_id, map_id = code >> 4, code & 15
        assert seed_id < seed_count and map_id in allowed
        used.add(seed_id)
        mapped = independent.action(seeds[seed_id], map_id)
        value = independent.norm(mapped)
        assert value <= independent.SIZE
        maximum_norm = max(maximum_norm, value)
        actual = {independent.residue(image)
                  for image in independent.unit_images(mapped)}
        reference = {independent.residue(image)
                     for image in independent.unit_images(
                         divmod(node, independent.RADIX))}
        assert actual == reference, (name, index)
        assert all(canonical[slot] == node for slot in actual)
        checked += len(actual)
        map_uses[independent.MAP_NAMES[map_id]] += 1
    assert used == set(range(seed_count)) and checked == independent.SIZE
    assert seed_count == expected["seed_count"]
    assert digest(raw) == expected["full_atlas_sha256"]
    assert len(raw) == expected["full_atlas_bytes"]
    assert dict(sorted(map_uses.items())) == expected["map_uses"]
    return {"mode": name, "status": "passed", "full_residues": checked,
            "unit_classes": classes, "seed_count": seed_count,
            "maximum_digit_norm": maximum_norm,
            "atlas_sha256": digest(raw)}


def main():
    screen_raw = (HERE / "lowcost-screen.json").read_bytes()
    screen = json.loads(screen_raw)
    assert screen["source_sha256"] == digest((HERE / "screen_lowcost.py").read_bytes())
    assert screen["base_source_sha256"] == digest((HERE / "screen.py").read_bytes())
    canonical, nodes = independent.orbit_partition()
    results = []
    for name, allowed in MODES:
        expected = next(row for row in screen["modes"] if row["mode"] == name)
        results.append(check_mode(name, allowed, expected, canonical, nodes))
    receipt = {"schema": 1, "status": "passed",
               "verifier_sha256": digest(Path(__file__).read_bytes()),
               "independent_source_sha256": digest((HERE / "verify_cover.py").read_bytes()),
               "screen_receipt_sha256": digest(screen_raw),
               "results": results}
    (HERE / "lowcost-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "passed", "full_residues_per_mode": independent.SIZE,
                      "seed_counts": {row["mode"]: row["seed_count"]
                                      for row in results}}, sort_keys=True))


if __name__ == "__main__":
    main()
