#!/usr/bin/env python3
"""Exact two-bucket tau covers for six radix-512 and eight radix-640 windows."""

from array import array
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCE = PARENT / "prime-j0-tau-power16-20261010/screen.py"
spec = importlib.util.spec_from_file_location("tau_power16_screen", SOURCE)
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)

RADIX = 640
BOUNDS = (640, 391)
WIDTH9_ATLAS = PARENT / "prime-j0-bound-budget15-20261010/atlas-w9.bin"
WIDTHS = (512,) * 6 + (RADIX,) * 8
DIGIT_BOUNDS = (512,) * 6 + (RADIX,) * 7 + (391,)
EMPTY = 0xFFFFFFFF


def modulus_receipt():
    product = 1
    weighted = 0
    for radix, bound in zip(WIDTHS, DIGIT_BOUNDS):
        weighted += bound * product
        product *= radix
    margin = 3 * (product - weighted) ** 2 - screen.ORDER
    assert product > weighted and margin > 0
    assert 3 * (product - weighted - product // RADIX) ** 2 <= screen.ORDER
    return {"radices": list(WIDTHS), "digit_bounds": list(DIGIT_BOUNDS),
            "radix_product": str(product), "weighted_digit_bound": str(weighted),
            "termination_margin": str(margin),
            "final_bound_is_maximal_for_this_norm_test": True}


def residue_classes():
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
    assert EMPTY not in canonical
    assert len(nodes) == (size + 8) // 6 == 68_268

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
    visited = set()
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
    assert sum(map(len, cycles)) == len(nodes)
    return canonical, nodes, direct, cycles


def build_cover(bound, canonical, nodes, direct, cycles):
    seeds = [(0, 0)]
    assigned = {0: (0, 0)}
    eligible_count = 0
    segments = Counter()
    for cycle in cycles:
        eligibility = [3 * screen.norm(direct[node]) <= bound * bound
                       for node in cycle]
        eligible_count += sum(eligibility)
        for start, length in screen.cycle_plan(cycle, eligibility):
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
    assert len(assigned) == len(nodes)
    assert len(seeds) == sum(segments.values())
    codes = array("I", [EMPTY]) * (RADIX * RADIX)
    max_norm = 0
    for node in nodes:
        seed_id, exponent = assigned[node]
        seed = seeds[seed_id]
        digit = seed if exponent == 0 else screen.tau(seed)
        assert canonical[screen.index(digit, RADIX)] == node
        max_norm = max(max_norm, screen.norm(digit))
        assert screen.norm(digit) <= bound * bound
        for unit_code, image in enumerate(screen.units(digit)):
            slot = screen.index(image, RADIX)
            assert canonical[slot] == node
            if codes[slot] == EMPTY:
                codes[slot] = (seed_id << 4) | (exponent << 3) | unit_code
    assert EMPTY not in codes
    for residue, code in enumerate(codes):
        digit, _ = screen.digit_from_code(code, seeds)
        assert screen.index(digit, RADIX) == residue
        assert screen.norm(digit) <= bound * bound

    output = HERE / f"atlas-r640-d{bound}.bin"
    binary = bytearray(b"T640" + struct.pack("<I", len(seeds)))
    binary.extend(struct.pack(f"<{len(codes)}I", *codes))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output.write_bytes(binary)
    return {"radix": RADIX, "bound": bound, "residues": len(codes),
            "unit_classes": len(nodes), "eligible_classes": eligible_count,
            "segment_lengths": dict(segments), "seed_count": len(seeds),
            "maximum_decoded_norm": max_norm, "atlas_bytes": len(binary),
            "atlas_sha256": sha256(binary).hexdigest()}


def main():
    assert RADIX % 3 != 0
    arithmetic = modulus_receipt()
    canonical, nodes, direct, cycles = residue_classes()
    atlases = {str(bound): build_cover(bound, canonical, nodes, direct, cycles)
               for bound in BOUNDS}
    assert atlases["640"]["eligible_classes"] == len(nodes)
    point_slots = 6 * 21_847 + 7 * atlases["640"]["seed_count"]
    point_slots += atlases["391"]["seed_count"]
    receipt = {"schema": 1, **arithmetic, "atlas_generator_sha256":
               sha256(Path(__file__).read_bytes()).hexdigest(),
               "source_screen_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
               "prior_width9_atlas_sha256": sha256(WIDTH9_ATLAS.read_bytes()).hexdigest(),
               "cycle_lengths": dict(Counter(map(len, cycles))),
               "atlases": atlases, "point_slots": point_slots,
               "point_payload_bytes": 64 * point_slots}
    (HERE / "atlas-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
