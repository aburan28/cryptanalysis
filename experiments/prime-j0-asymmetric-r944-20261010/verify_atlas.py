#!/usr/bin/env python3
"""Independent binary-atlas, cycle-cover, and termination verifier."""

from array import array
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
R = 944
SIZE = R * R
EMPTY = 0xFFFFFFFF
ORDER = int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16)


def norm(z):
    a, b = z
    return a * a + 3 * a * b + 3 * b * b


def omega(z):
    a, b = z
    return a + 3 * b, -a - 2 * b


def tau(z):
    a, b = z
    return -3 * b, a + 3 * b


def unit(z, code):
    for _ in range(code // 2):
        z = omega(z)
    return (-z[0], -z[1]) if code & 1 else z


def slot(z):
    return z[0] % R * R + z[1] % R


def nearest(z):
    a, b = z
    u, v = a + b, -b
    fu, fv = u // R, v // R
    candidates = []
    for m in (fu, fu + 1):
        for n in (fv, fv + 1):
            x, y = u - m * R, v - n * R
            d = (x + y, -y)
            candidates.append((norm(d), *d))
    return min(candidates)[1:]


def path_matching(edges):
    prev2 = prev1 = 0
    for edge in edges:
        current = max(prev1, prev2 + 1 if edge else prev1)
        prev2, prev1 = prev1, current
    return prev1


def cycle_matching(edges):
    if len(edges) == 1:
        return 0
    best = path_matching(edges[:-1])
    if edges[-1]:
        best = max(best, 1 + path_matching(edges[1:-2]))
    return best


def classes_and_cycles():
    canonical = array("I", [EMPTY]) * SIZE
    nodes = []
    for residue in range(SIZE):
        if canonical[residue] != EMPTY:
            continue
        z = divmod(residue, R)
        orbit = [slot(unit(z, code)) for code in range(6)]
        assert min(orbit) == residue
        for member in orbit:
            assert canonical[member] in (EMPTY, residue)
            canonical[member] = residue
        nodes.append(residue)
    assert len(nodes) == 148_524 and EMPTY not in canonical

    direct_norm = {}
    successor = {}
    for node in nodes:
        digit = nearest(divmod(node, R))
        assert slot(digit) == node
        direct_norm[node] = norm(digit)
        successor[node] = canonical[slot(tau(digit))]
    assert set(successor.values()) == set(nodes)
    visited = set()
    cycles = []
    for origin in nodes:
        if origin in visited:
            continue
        cycle = []
        current = origin
        while current not in visited:
            visited.add(current)
            cycle.append(current)
            current = successor[current]
        assert current == origin
        cycles.append(cycle)
    assert len(visited) == len(nodes)
    return direct_norm, cycles


def verify_binary(bound, expected, direct_norm, cycles):
    raw = (HERE / f"atlas-r944-d{bound}.bin").read_bytes()
    assert raw[:4] == b"T944"
    count = struct.unpack_from("<I", raw, 4)[0]
    assert len(raw) == 8 + 4 * SIZE + 4 * count
    assert count == expected["seed_count"]
    seeds = memoryview(raw)[8 + 4 * SIZE:]
    assert struct.unpack_from("<hh", seeds, 0) == (0, 0)
    maximum = 0
    for residue in range(SIZE):
        code = struct.unpack_from("<I", raw, 8 + 4 * residue)[0]
        seed_id, exponent, unit_code = code >> 4, (code >> 3) & 1, code & 7
        assert seed_id < count and unit_code < 6
        seed = struct.unpack_from("<hh", seeds, 4 * seed_id)
        digit = unit(tau(seed) if exponent else seed, unit_code)
        assert slot(digit) == residue
        value = norm(digit)
        assert value <= bound * bound
        maximum = max(maximum, value)
    assert maximum == expected["maximum_decoded_norm"]
    assert sha256(raw).hexdigest() == expected["atlas_sha256"]

    minimum = 0
    eligible = 0
    for cycle in cycles:
        edges = [3 * direct_norm[node] <= bound * bound for node in cycle]
        eligible += sum(edges)
        minimum += len(cycle) - cycle_matching(edges)
    assert minimum == count
    assert eligible == expected["eligible_classes"]
    return {"bound": bound, "seed_count": count, "minimum_seed_count": minimum,
            "eligible_classes": eligible, "maximum_decoded_norm": maximum,
            "atlas_sha256": sha256(raw).hexdigest(), "atlas_bytes": len(raw)}


def main():
    record = json.loads((HERE / "atlas-receipt.json").read_bytes())
    assert sha256((HERE / "build_atlas.py").read_bytes()).hexdigest() == record[
        "atlas_generator_sha256"]
    assert record["radices"] == [R] * 13
    assert record["digit_bounds"] == [R] * 12 + [550]
    product = R ** 13
    weighted = sum(R * R ** i for i in range(12)) + 550 * R ** 12
    margin = 3 * (product - weighted) ** 2 - ORDER
    assert margin > 0
    assert 3 * (product - weighted - R ** 12) ** 2 <= ORDER
    assert record["radix_product"] == str(product)
    assert record["weighted_digit_bound"] == str(weighted)
    assert record["termination_margin"] == str(margin)
    direct_norm, cycles = classes_and_cycles()
    assert dict(Counter(map(len, cycles))) == {
        int(k): v for k, v in record["cycle_lengths"].items()}
    checks = {str(bound): verify_binary(bound, record["atlases"][str(bound)],
                                        direct_norm, cycles) for bound in (R, 550)}
    point_slots = 12 * checks[str(R)]["seed_count"] + checks["550"]["seed_count"]
    assert point_slots == record["point_slots"] == 993_953
    assert 64 * point_slots == record["point_payload_bytes"]
    output = {"schema": 1, "status": "passed", "radix": R,
              "residues_checked_per_atlas": SIZE, "unit_classes": len(direct_norm),
              "tau_cycles": len(cycles), "point_slots": point_slots,
              "point_payload_bytes": 64 * point_slots,
              "termination_margin": str(margin), "atlases": checks,
              "verifier_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE / "independent-check.json").write_text(json.dumps(output, indent=2,
                                                     sort_keys=True) + "\n")
    print(json.dumps(output, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
