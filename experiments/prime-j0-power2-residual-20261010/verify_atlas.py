#!/usr/bin/env python3
"""Independently replay every full residue and terminal integer pair."""

from array import array
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
RADIX = 1024
BOUND = 149
EMPTY = 0xFFFFFFFF


def digest(raw):
    return sha256(raw).hexdigest()


def norm(pair):
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def omega(pair):
    a, b = pair
    return a + 3 * b, -a - 2 * b


def tau(pair):
    a, b = pair
    return -3 * b, a + 3 * b


def units(pair):
    out = []
    for _ in range(3):
        out.extend((pair, (-pair[0], -pair[1])))
        pair = omega(pair)
    return out


def residue(pair):
    return pair[0] % RADIX * RADIX + pair[1] % RADIX


def nearest_wide_search(slot):
    a, b = divmod(slot, RADIX)
    return min((norm((a + i * RADIX, b + j * RADIX)),
                a + i * RADIX, b + j * RADIX)
               for i in range(-2, 2) for j in range(-2, 2))[1:]


def decode(code, seeds):
    seed_id, exponent, unit = code >> 4, (code >> 3) & 1, code & 7
    assert seed_id < len(seeds) and unit < 6
    seed = seeds[seed_id]
    return units(seed if exponent == 0 else tau(seed))[unit], seed_id, exponent


def verify_full():
    binary = (HERE / "atlas-r1024-full.bin").read_bytes()
    assert binary[:4] == b"T102"
    seed_count = struct.unpack_from("<I", binary, 4)[0]
    size = RADIX * RADIX
    assert len(binary) == 8 + 4 * size + 4 * seed_count
    codes = struct.unpack_from(f"<{size}I", binary, 8)
    seeds = list(struct.iter_unpack("<hh", binary[8 + 4 * size:]))
    assert len(seeds) == seed_count and seeds[0] == (0, 0)

    canonical = array("I", [EMPTY]) * size
    nodes = []
    for slot in range(size):
        if canonical[slot] != EMPTY:
            continue
        orbit = [residue(image) for image in units(divmod(slot, RADIX))]
        assert min(orbit) == slot
        for member in orbit:
            assert canonical[member] in (EMPTY, slot)
            canonical[member] = slot
        nodes.append(slot)
    assert EMPTY not in canonical

    used = set()
    maximum_norm = 0
    for slot, code in enumerate(codes):
        digit, seed_id, _ = decode(code, seeds)
        assert residue(digit) == slot
        value = norm(digit)
        assert value <= RADIX * RADIX
        maximum_norm = max(maximum_norm, value)
        used.add(seed_id)
    assert used == set(range(seed_count))

    successor = {}
    incoming = Counter()
    for node in nodes:
        direct = nearest_wide_search(node)
        successor[node] = canonical[residue(tau(direct))]
        incoming[successor[node]] += 1
    assert set(successor.values()) == set(nodes)
    assert all(incoming[node] == 1 for node in nodes)
    for seed in seeds:
        source_class = canonical[residue(seed)]
        assert seed == nearest_wide_search(source_class)
    seen = set()
    lengths = Counter()
    minimum_seeds = 0
    for origin in nodes:
        if origin in seen:
            continue
        current = origin
        length = 0
        while current not in seen:
            seen.add(current)
            current = successor[current]
            length += 1
        assert current == origin
        lengths[length] += 1
        minimum_seeds += (length + 1) // 2
    assert len(seen) == len(nodes) and minimum_seeds == seed_count
    return {"atlas_sha256": digest(binary), "residues": size,
            "unit_classes": len(nodes), "cycle_lengths": dict(lengths),
            "minimum_seed_count": minimum_seeds,
            "maximum_decoded_norm": maximum_norm, "atlas_bytes": len(binary)}


def enumerate_disk():
    pairs = []
    rows = []
    for b in range(-2 * BOUND, 2 * BOUND + 1):
        valid = [(a, b) for a in range(-2 * BOUND, 2 * BOUND + 1)
                 if norm((a, b)) < BOUND * BOUND]
        if valid:
            assert len(valid) == valid[-1][0] - valid[0][0] + 1
            rows.append((b, valid[0][0], len(valid), len(pairs)))
            pairs.extend(valid)
    return pairs, rows


def verify_terminal():
    binary = (HERE / "atlas-r1024-terminal.bin").read_bytes()
    magic, bound, b_min, b_max, seed_count, pair_count, reserved = \
        struct.unpack_from("<4sHhhIIH", binary)
    assert magic == b"R102" and bound == BOUND and reserved == 0
    pairs, expected_rows = enumerate_disk()
    assert pair_count == len(pairs)
    assert (b_min, b_max) == (expected_rows[0][0], expected_rows[-1][0])
    rows = [struct.unpack_from("<hHI", binary, 20 + 8 * index)
            for index in range(len(expected_rows))]
    assert [(a_min, length, offset) for a_min, length, offset in rows] == [
        (a_min, length, offset) for _, a_min, length, offset in expected_rows]
    code_start = 20 + 8 * len(rows)
    seed_start = code_start + 4 * pair_count
    assert len(binary) == seed_start + 4 * seed_count
    codes = struct.unpack_from(f"<{pair_count}I", binary, code_start)
    seeds = list(struct.iter_unpack("<hh", binary[seed_start:]))
    assert len(seeds) == seed_count and seeds[0] == (0, 0)

    used = set()
    for pair, code in zip(pairs, codes):
        digit, seed_id, _ = decode(code, seeds)
        assert digit == pair
        used.add(seed_id)
    assert used == set(range(seed_count))

    canonical = lambda pair: min(units(pair))
    classes = {canonical(pair) for pair in pairs}
    assert all(canonical(seed) == seed for seed in seeds)
    successor = {node: (canonical(tau(node))
                        if 3 * norm(node) < BOUND * BOUND else None)
                 for node in classes}
    assert all(target is None or target in classes
               for target in successor.values())
    incoming = Counter(target for node, target in successor.items()
                       if node != (0, 0) and target is not None)
    assert all(count == 1 for count in incoming.values())
    seen = {(0, 0)}
    lengths = Counter()
    minimum_seeds = 1
    for root in sorted(classes):
        if root == (0, 0) or incoming[root]:
            continue
        current = root
        length = 0
        while current is not None:
            assert current not in seen
            seen.add(current)
            current = successor[current]
            length += 1
        lengths[length] += 1
        minimum_seeds += (length + 1) // 2
    assert seen == classes and minimum_seeds == seed_count
    return {"atlas_sha256": digest(binary), "pairs": pair_count,
            "unit_classes": len(classes), "chain_lengths": dict(lengths),
            "minimum_seed_count": minimum_seeds,
            "maximum_pair_norm": max(map(norm, pairs)),
            "row_count": len(rows), "atlas_bytes": len(binary)}


def main():
    generated = json.loads((HERE / "atlas-receipt.json").read_text())
    full = verify_full()
    terminal = verify_terminal()
    assert generated["full"]["atlas_sha256"] == full["atlas_sha256"]
    assert generated["terminal"]["atlas_sha256"] == terminal["atlas_sha256"]
    assert generated["full"]["seed_count"] == full["minimum_seed_count"]
    assert generated["terminal"]["seed_count"] == terminal["minimum_seed_count"]
    assert generated["point_slots"] == 12 * full["minimum_seed_count"] \
        + terminal["minimum_seed_count"]
    receipt = {"schema": 1, "status": "passed", "full": full,
               "terminal": terminal,
               "verifier_sha256": digest(Path(__file__).read_bytes())}
    receipt = json.loads(json.dumps(receipt, sort_keys=True))
    path = HERE / "independent-check.json"
    if path.exists():
        assert json.loads(path.read_text()) == receipt
    else:
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
