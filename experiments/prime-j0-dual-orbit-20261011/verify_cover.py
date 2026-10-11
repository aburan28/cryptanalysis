#!/usr/bin/env python3
"""Independently audit every six-unit residue orbit in the dual covers."""

from array import array
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
RADIX = 1024
SIZE = RADIX * RADIX
EMPTY = 0xFFFFFFFF
MODES = (("tau", 3), ("tau_rho", 6), ("tau_rho_both", 9))
MAP_NAMES = ("one", "tau", "tau2", "rho", "tau_rho", "tau2_rho",
             "rho_bar", "tau_rho_bar", "tau2_rho_bar")


def digest(raw):
    return sha256(raw).hexdigest()


def norm(pair):
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def omega(pair):
    a, b = pair
    return a + 3 * b, -a - 2 * b


def unit_images(pair):
    result = []
    for _ in range(3):
        result.extend((pair, (-pair[0], -pair[1])))
        pair = omega(pair)
    return result


def residue(pair):
    return pair[0] % RADIX * RADIX + pair[1] % RADIX


def tau(pair):
    a, b = pair
    return -3 * b, a + 3 * b


def degree_seven(pair, conjugate):
    a, b = pair
    return (4 * a + 3 * b, b - a) if conjugate else (a - 3 * b, a + 4 * b)


def action(pair, map_id):
    branch, power = divmod(map_id, 3)
    if branch:
        pair = degree_seven(pair, branch == 2)
    for _ in range(power):
        pair = tau(pair)
    return pair


def orbit_partition():
    canonical = array("I", [EMPTY]) * SIZE
    nodes = []
    for slot in range(SIZE):
        if canonical[slot] != EMPTY:
            continue
        orbit = {residue(image) for image in unit_images(divmod(slot, RADIX))}
        assert min(orbit) == slot
        for member in orbit:
            assert canonical[member] in (EMPTY, slot)
            canonical[member] = slot
        nodes.append(slot)
    assert len(nodes) == 174_764 and EMPTY not in canonical
    return canonical, nodes


def check_mode(name, limit, expected, canonical, nodes):
    raw = (HERE / f"cover-{name}.bin").read_bytes()
    magic, radix, classes, seed_count, map_count = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, map_count) == (b"DO19", RADIX, len(nodes), limit)
    seed_start = 20 + 4 * classes
    assert len(raw) == seed_start + 4 * seed_count
    seeds = list(struct.iter_unpack("<hh", raw[seed_start:]))
    assert len(seeds) == seed_count and seeds[0] == (0, 0)
    assert len(set(seeds)) == seed_count
    used = set()
    map_uses = Counter()
    residues_checked = 0
    maximum_norm = 0
    for index, node in enumerate(nodes):
        code = struct.unpack_from("<I", raw, 20 + 4 * index)[0]
        seed_id, map_id = code >> 4, code & 15
        assert seed_id < seed_count and map_id < limit
        used.add(seed_id)
        mapped = action(seeds[seed_id], map_id)
        value = norm(mapped)
        assert value <= RADIX * RADIX
        maximum_norm = max(maximum_norm, value)
        actual_orbit = {residue(image) for image in unit_images(mapped)}
        expected_orbit = {residue(image)
                          for image in unit_images(divmod(node, RADIX))}
        assert actual_orbit == expected_orbit, (name, index)
        assert all(canonical[slot] == node for slot in actual_orbit)
        residues_checked += len(actual_orbit)
        map_uses[MAP_NAMES[map_id]] += 1
    assert used == set(range(seed_count))
    assert residues_checked == SIZE
    assert expected["seed_count"] == seed_count
    assert expected["full_atlas_sha256"] == digest(raw)
    assert expected["full_atlas_bytes"] == len(raw)
    assert expected["map_uses"] == dict(sorted(map_uses.items()))
    assert expected["affine_slots"] == 12 * seed_count + 9_288
    return {"mode": name, "status": "passed", "unit_classes": classes,
            "full_residues": residues_checked, "seed_count": seed_count,
            "maximum_digit_norm": maximum_norm,
            "map_uses": dict(sorted(map_uses.items())),
            "atlas_sha256": digest(raw)}


def main():
    for point in ((7, -5), (0, 1), (101, 37)):
        assert degree_seven(degree_seven(point, False), True) == \
            (7 * point[0], 7 * point[1])
        assert norm(degree_seven(point, False)) == 7 * norm(point)
        assert norm(degree_seven(point, True)) == 7 * norm(point)
    screen_receipt = json.loads((HERE / "screen.json").read_bytes())
    assert screen_receipt["source_sha256"] == digest((HERE / "screen.py").read_bytes())
    canonical, nodes = orbit_partition()
    results = []
    for name, limit in MODES:
        expected = next(row for row in screen_receipt["modes"]
                        if row["mode"] == name)
        results.append(check_mode(name, limit, expected, canonical, nodes))
    receipt = {"schema": 1, "status": "passed",
               "verifier_sha256": digest(Path(__file__).read_bytes()),
               "screen_receipt_sha256": digest((HERE / "screen.json").read_bytes()),
               "results": results}
    (HERE / "cover-check.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "passed", "full_residues_per_mode": SIZE,
                      "seed_counts": {row["mode"]: row["seed_count"]
                                      for row in results}}, sort_keys=True))


if __name__ == "__main__":
    main()
