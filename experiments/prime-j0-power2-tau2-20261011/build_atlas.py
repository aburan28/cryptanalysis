#!/usr/bin/env python3
"""Construct minimum three-tau-image covers for radix-1024 and the terminal disk."""

from array import array
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-power2-residual-20261010/build_atlas.py"
SPEC = importlib.util.spec_from_file_location("power2_parent_atlas", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
screen = parent.screen

RADIX = 1024
WINDOWS = 12
BOUND = 149
EMPTY = 0xFFFFFFFF


def digest(raw):
    return sha256(raw).hexdigest()


def tau_power(pair, exponent):
    for _ in range(exponent):
        pair = screen.tau(pair)
    return pair


def minimum_cycle_segments(cycle, direct):
    """Return a minimum admissible cyclic partition and its seed count."""
    length = len(cycle)
    eligible_three = [9 * screen.norm(direct[node]) <= RADIX * RADIX
                      for node in cycle]
    best = None
    for backward in range(min(3, length)):
        origin = (-backward) % length
        costs = [length + 1] * (length + 1)
        previous = [None] * (length + 1)
        costs[0] = 0
        for offset in range(length):
            if costs[offset] > length:
                continue
            node_index = (origin + offset) % length
            for span in (3, 2, 1):
                endpoint = offset + span
                if endpoint > length or span == 3 and not eligible_three[node_index]:
                    continue
                cost = costs[offset] + 1
                if cost < costs[endpoint]:
                    costs[endpoint] = cost
                    previous[endpoint] = (offset, span)
        assert costs[length] <= length
        segments = []
        endpoint = length
        while endpoint:
            offset, span = previous[endpoint]
            segments.append(((origin + offset) % length, span))
            endpoint = offset
        segments.reverse()
        candidate = (costs[length], backward, segments)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    return best[2]


def build_full():
    canonical, nodes, direct, cycles = parent.full_classes()
    seeds = [(0, 0)]
    assigned = {0: (0, 0)}
    segment_lengths = Counter()
    eligible_three = 0
    theoretical_floor = 0
    for cycle in cycles:
        eligible_three += sum(9 * screen.norm(direct[node]) <= RADIX * RADIX
                              for node in cycle)
        theoretical_floor += (len(cycle) + 2) // 3
        for start, span in minimum_cycle_segments(cycle, direct):
            segment_lengths[span] += 1
            node = cycle[start]
            if node == 0:
                assert span == 1 and assigned[node] == (0, 0)
                continue
            seed_id = len(seeds)
            seeds.append(direct[node])
            for exponent in range(span):
                covered = cycle[(start + exponent) % len(cycle)]
                assert covered not in assigned
                assigned[covered] = (seed_id, exponent)
    assert len(assigned) == len(nodes)
    assert len(seeds) == sum(segment_lengths.values()) == 73_417

    codes = array("I", [EMPTY]) * (RADIX * RADIX)
    maximum_norm = 0
    for node in nodes:
        seed_id, exponent = assigned[node]
        digit = tau_power(seeds[seed_id], exponent)
        assert canonical[screen.index(digit, RADIX)] == node
        assert screen.norm(digit) <= RADIX * RADIX
        maximum_norm = max(maximum_norm, screen.norm(digit))
        for unit_code, image in enumerate(screen.units(digit)):
            slot = screen.index(image, RADIX)
            assert canonical[slot] == node
            if codes[slot] == EMPTY:
                codes[slot] = (seed_id << 5) | (exponent << 3) | unit_code
    assert EMPTY not in codes
    for residue, code in enumerate(codes):
        seed_id, exponent, unit_code = code >> 5, (code >> 3) & 3, code & 7
        assert exponent <= 2 and unit_code < 6 and seed_id < len(seeds)
        digit = screen.units(tau_power(seeds[seed_id], exponent))[unit_code]
        assert screen.index(digit, RADIX) == residue
        assert screen.norm(digit) <= RADIX * RADIX

    binary = bytearray(b"T103" + struct.pack("<I", len(seeds)))
    binary.extend(struct.pack(f"<{len(codes)}I", *codes))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output = HERE / "atlas-r1024-full-tau2.bin"
    output.write_bytes(binary)
    return {"residues": len(codes), "unit_classes": len(nodes),
            "cycle_count": len(cycles), "eligible_three_classes": eligible_three,
            "unconstrained_three_image_floor": theoretical_floor,
            "segment_lengths": dict(segment_lengths), "seed_count": len(seeds),
            "maximum_decoded_norm": maximum_norm,
            "atlas_bytes": len(binary), "atlas_sha256": digest(binary)}


def build_terminal():
    pairs, rows = parent.terminal_pairs()
    canonical = lambda pair: min(screen.units(pair))
    classes = {canonical(pair) for pair in pairs}
    assert len(classes) == 13_421
    successor = {node: (canonical(screen.tau(node))
                        if 3 * screen.norm(node) < BOUND * BOUND
                        else None) for node in classes}
    incoming = Counter(target for node, target in successor.items()
                       if node != (0, 0) and target is not None)
    assert all(count == 1 for count in incoming.values())
    seen = {(0, 0)}
    seeds = [(0, 0)]
    assigned = {(0, 0): (0, 0)}
    chain_lengths = Counter()
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
        chain_lengths[len(chain)] += 1
        for start in range(0, len(chain), 3):
            seed_id = len(seeds)
            seeds.append(chain[start])
            for exponent in range(min(3, len(chain) - start)):
                node = chain[start + exponent]
                assert canonical(tau_power(seeds[seed_id], exponent)) == node
                assigned[node] = (seed_id, exponent)
    assert seen == classes and len(assigned) == len(classes)
    assert len(seeds) == 1 + sum(count * ((length + 2) // 3)
                                  for length, count in chain_lengths.items())
    assert len(seeds) == 9_288

    codes = []
    for pair in pairs:
        seed_id, exponent = assigned[canonical(pair)]
        digit = tau_power(seeds[seed_id], exponent)
        images = screen.units(digit)
        assert pair in images
        code = (seed_id << 5) | (exponent << 3) | images.index(pair)
        codes.append(code)

    binary = bytearray(struct.pack("<4sHhhIIH", b"R103", BOUND,
                                   rows[0][0], rows[-1][0], len(seeds),
                                   len(pairs), 0))
    for _, a_min, length, offset in rows:
        binary.extend(struct.pack("<hHI", a_min, length, offset))
    binary.extend(struct.pack(f"<{len(codes)}I", *codes))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output = HERE / "atlas-r1024-terminal-tau2.bin"
    output.write_bytes(binary)
    return {"pairs": len(pairs), "unit_classes": len(classes),
            "row_count": len(rows), "b_min": rows[0][0], "b_max": rows[-1][0],
            "chain_lengths": dict(chain_lengths), "seed_count": len(seeds),
            "atlas_bytes": len(binary), "atlas_sha256": digest(binary)}


def main():
    full = build_full()
    terminal = build_terminal()
    slots = WINDOWS * full["seed_count"] + terminal["seed_count"]
    assert slots == 890_292
    receipt = {"schema": 1, "status": "constructed",
               "generator_sha256": digest(Path(__file__).read_bytes()),
               "parent_generator_sha256": digest(PARENT.read_bytes()),
               "screen_sha256": digest(parent.SOURCE.read_bytes()),
               "radix": RADIX, "windows": WINDOWS,
               "full": full, "terminal": terminal,
               "affine_slots": slots, "affine_payload_bytes": slots * 64,
               "atlas_bytes": full["atlas_bytes"] + terminal["atlas_bytes"]}
    path = HERE / "atlas-receipt.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
