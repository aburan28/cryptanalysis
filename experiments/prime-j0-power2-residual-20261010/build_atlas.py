#!/usr/bin/env python3
"""Construct shift-window and exact terminal-residual tau atlases."""

from array import array
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-tau-power16-20261010/screen.py"
spec = importlib.util.spec_from_file_location("tau_power16_screen", SOURCE)
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)

RADIX = 1024
WINDOWS = 12
TERMINAL_BOUND = 149
EMPTY = 0xFFFFFFFF


def digest(raw):
    return sha256(raw).hexdigest()


def arithmetic_receipt():
    product = RADIX ** WINDOWS
    weighted = sum(RADIX ** (i + 1) for i in range(WINDOWS))
    margin = 3 * (TERMINAL_BOUND * product - weighted) ** 2 - screen.ORDER
    previous_margin = 3 * ((TERMINAL_BOUND - 1) * product - weighted) ** 2 - screen.ORDER
    assert TERMINAL_BOUND * product > weighted
    assert margin > 0 and previous_margin <= 0
    return {"radix_product": str(product),
            "weighted_digit_bound": str(weighted),
            "termination_margin": str(margin),
            "previous_bound_margin": str(previous_margin),
            "terminal_bound_exclusive": TERMINAL_BOUND}


def full_classes():
    size = RADIX * RADIX
    canonical = array("I", [EMPTY]) * size
    nodes = []
    for residue in range(size):
        if canonical[residue] != EMPTY:
            continue
        orbit = [screen.index(pair, RADIX)
                 for pair in screen.units(divmod(residue, RADIX))]
        assert min(orbit) == residue
        for member in orbit:
            assert canonical[member] in (EMPTY, residue)
            canonical[member] = residue
        nodes.append(residue)
    assert EMPTY not in canonical and len(nodes) == 174_764

    direct = {}
    successor = {}
    incoming = Counter()
    for node in nodes:
        digit = screen.nearest_digit(divmod(node, RADIX), RADIX)
        target = canonical[screen.index(screen.tau(digit), RADIX)]
        direct[node] = digit
        successor[node] = target
        incoming[target] += 1
    assert set(successor.values()) == set(nodes)
    assert all(incoming[node] == 1 for node in nodes)

    cycles = []
    seen = set()
    for origin in nodes:
        if origin in seen:
            continue
        cycle = []
        current = origin
        while current not in seen:
            seen.add(current)
            cycle.append(current)
            current = successor[current]
        assert current == origin
        cycles.append(cycle)
    assert len(seen) == len(nodes) and len(cycles) == 513
    return canonical, nodes, direct, cycles


def build_full(canonical, nodes, direct, cycles):
    seeds = [(0, 0)]
    assigned = {0: (0, 0)}
    segments = Counter()
    eligible_count = 0
    for cycle in cycles:
        eligible = [3 * screen.norm(direct[node]) <= RADIX * RADIX
                    for node in cycle]
        eligible_count += sum(eligible)
        for start, length in screen.cycle_plan(cycle, eligible):
            segments[length] += 1
            node = cycle[start]
            if node == 0:
                assert length == 1 and assigned[node] == (0, 0)
                continue
            seed_id = len(seeds)
            seeds.append(direct[node])
            for exponent in range(length):
                covered = cycle[(start + exponent) % len(cycle)]
                assert covered not in assigned
                assigned[covered] = (seed_id, exponent)
    assert eligible_count == len(nodes)
    assert len(assigned) == len(nodes)
    assert len(seeds) == sum(segments.values()) == 87_383

    codes = array("I", [EMPTY]) * (RADIX * RADIX)
    maximum_norm = 0
    for node in nodes:
        seed_id, exponent = assigned[node]
        seed = seeds[seed_id]
        digit = seed if exponent == 0 else screen.tau(seed)
        assert canonical[screen.index(digit, RADIX)] == node
        maximum_norm = max(maximum_norm, screen.norm(digit))
        assert screen.norm(digit) <= RADIX * RADIX
        for unit_code, image in enumerate(screen.units(digit)):
            slot = screen.index(image, RADIX)
            assert canonical[slot] == node
            if codes[slot] == EMPTY:
                codes[slot] = (seed_id << 4) | (exponent << 3) | unit_code
    assert EMPTY not in codes
    for residue, code in enumerate(codes):
        digit, _ = screen.digit_from_code(code, seeds)
        assert screen.index(digit, RADIX) == residue
        assert screen.norm(digit) <= RADIX * RADIX

    binary = bytearray(b"T102" + struct.pack("<I", len(seeds)))
    binary.extend(struct.pack(f"<{len(codes)}I", *codes))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output = HERE / "atlas-r1024-full.bin"
    output.write_bytes(binary)
    return {"residues": len(codes), "unit_classes": len(nodes),
            "cycle_lengths": dict(Counter(map(len, cycles))),
            "eligible_classes": eligible_count,
            "segment_lengths": dict(segments), "seed_count": len(seeds),
            "maximum_decoded_norm": maximum_norm,
            "atlas_bytes": len(binary), "atlas_sha256": digest(binary)}


def terminal_pairs():
    pairs = []
    rows = []
    for b in range(-2 * TERMINAL_BOUND, 2 * TERMINAL_BOUND + 1):
        valid = [(a, b) for a in range(-2 * TERMINAL_BOUND,
                                       2 * TERMINAL_BOUND + 1)
                 if screen.norm((a, b)) < TERMINAL_BOUND ** 2]
        if not valid:
            continue
        assert len(valid) == valid[-1][0] - valid[0][0] + 1
        rows.append((b, valid[0][0], len(valid), len(pairs)))
        pairs.extend(valid)
    assert len(pairs) == 80_521 and rows[0][0] == -172 and rows[-1][0] == 172
    assert max(screen.norm(pair) for pair in pairs) == 22_197
    return pairs, rows


def build_terminal():
    pairs, rows = terminal_pairs()
    canonical = lambda pair: min(screen.units(pair))
    classes = {canonical(pair) for pair in pairs}
    assert len(classes) == 13_421
    successor = {node: (canonical(screen.tau(node))
                        if 3 * screen.norm(node) < TERMINAL_BOUND ** 2
                        else None) for node in classes}
    assert all(target is None or target in classes
               for target in successor.values())
    incoming = Counter(target for node, target in successor.items()
                       if node != (0, 0) and target is not None)
    assert all(count == 1 for count in incoming.values())

    seen = {(0, 0)}
    seeds = [(0, 0)]
    assigned = {(0, 0): (0, 0)}
    chains = []
    for root in sorted(classes):
        if root == (0, 0) or incoming[root]:
            continue
        chain = []
        current = root
        while current is not None:
            assert current not in seen
            seen.add(current)
            chain.append(current)
            current = successor[current]
        chains.append(chain)
        for index in range(0, len(chain), 2):
            seed_id = len(seeds)
            seeds.append(chain[index])
            assigned[chain[index]] = (seed_id, 0)
            if index + 1 < len(chain):
                assert canonical(screen.tau(chain[index])) == chain[index + 1]
                assigned[chain[index + 1]] = (seed_id, 1)
    assert seen == classes and len(assigned) == len(classes)
    assert len(chains) == 8_943
    assert len(seeds) == 1 + sum((len(chain) + 1) // 2 for chain in chains)
    assert len(seeds) == 10_061

    codes = []
    for pair in pairs:
        seed_id, exponent = assigned[canonical(pair)]
        digit = seeds[seed_id] if exponent == 0 else screen.tau(seeds[seed_id])
        images = screen.units(digit)
        assert pair in images
        code = (seed_id << 4) | (exponent << 3) | images.index(pair)
        decoded, _ = screen.digit_from_code(code, seeds)
        assert decoded == pair
        codes.append(code)

    binary = bytearray(struct.pack("<4sHhhIIH", b"R102", TERMINAL_BOUND,
                                   rows[0][0], rows[-1][0], len(seeds),
                                   len(pairs), 0))
    for _, a_min, length, offset in rows:
        binary.extend(struct.pack("<hHI", a_min, length, offset))
    binary.extend(struct.pack(f"<{len(codes)}I", *codes))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output = HERE / "atlas-r1024-terminal.bin"
    output.write_bytes(binary)
    return {"pairs": len(pairs), "unit_classes": len(classes),
            "row_count": len(rows), "b_min": rows[0][0], "b_max": rows[-1][0],
            "chain_lengths": dict(Counter(map(len, chains))),
            "chain_count": len(chains), "seed_count": len(seeds),
            "maximum_pair_norm": max(screen.norm(pair) for pair in pairs),
            "atlas_bytes": len(binary), "atlas_sha256": digest(binary)}


def main():
    arithmetic = arithmetic_receipt()
    canonical, nodes, direct, cycles = full_classes()
    full = build_full(canonical, nodes, direct, cycles)
    terminal = build_terminal()
    slots = WINDOWS * full["seed_count"] + terminal["seed_count"]
    assert slots == 1_058_657
    receipt = {"schema": 1, "radix": RADIX, "full_windows": WINDOWS,
               **arithmetic, "full": full, "terminal": terminal,
               "point_slots": slots, "point_payload_bytes": 64 * slots,
               "retained_bytes": 64 * slots + full["atlas_bytes"]
               + terminal["atlas_bytes"] + 400,
               "generator_sha256": digest(Path(__file__).read_bytes()),
               "source_screen_sha256": digest(SOURCE.read_bytes())}
    (HERE / "atlas-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
