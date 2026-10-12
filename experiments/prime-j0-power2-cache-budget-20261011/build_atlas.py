#!/usr/bin/env python3
"""Materialize the frozen cache-budgeted tau cover as exact lookup atlases."""

from array import array
from collections import Counter, defaultdict
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-power2-tau2-20261011/build_atlas.py"
SPEC = importlib.util.spec_from_file_location("minimum_three_image", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
RADIX = 1024
WINDOWS = 12
EMPTY = 0xFFFFFFFF


def digest(raw):
    return sha256(raw).hexdigest()


def plan_records():
    raw = (HERE / "cover-plan.bin").read_bytes()
    screen = json.loads((HERE / "screen.json").read_bytes())
    assert screen["cover_plan_sha256"] == digest(raw)
    assert raw[:4] == b"CB64"
    cycle_count, segment_count = struct.unpack_from("<II", raw, 4)
    assert cycle_count == 513 and segment_count == 77_513
    assert len(raw) == 12 + 5 * segment_count
    grouped = defaultdict(list)
    for cycle_index, start, span in struct.iter_unpack("<HHB", raw[12:]):
        grouped[cycle_index].append((start, span))
    return grouped, digest(raw)


def build_full():
    canonical, nodes, direct, cycles = parent.parent.full_classes()
    grouped, plan_hash = plan_records()
    assert len(cycles) == len(grouped) == 513
    seeds = [(0, 0)]
    assigned = {0: (0, 0)}
    segment_lengths = Counter()
    for cycle_index, cycle in enumerate(cycles):
        covered = set()
        for start, span in grouped[cycle_index]:
            assert start < len(cycle) and 1 <= span <= 3
            node = cycle[start]
            assert (3 ** (span - 1)) * parent.screen.norm(direct[node]) <= RADIX ** 2
            segment_lengths[span] += 1
            if node == 0:
                assert span == 1 and len(seeds) == 1
                seed_id = 0
            else:
                seed_id = len(seeds)
                seeds.append(direct[node])
            for exponent in range(span):
                position = (start + exponent) % len(cycle)
                assert position not in covered
                covered.add(position)
                target = cycle[position]
                if target == 0:
                    assert (seed_id, exponent) == (0, 0)
                else:
                    assert target not in assigned
                    assigned[target] = (seed_id, exponent)
        assert len(covered) == len(cycle)
    assert len(assigned) == len(nodes)
    assert len(seeds) == 77_513
    assert segment_lengths == {1: 69, 2: 57_637, 3: 19_807}

    codes = array("I", [EMPTY]) * (RADIX * RADIX)
    max_norm = 0
    for node in nodes:
        seed_id, exponent = assigned[node]
        digit = parent.tau_power(seeds[seed_id], exponent)
        assert canonical[parent.screen.index(digit, RADIX)] == node
        assert parent.screen.norm(digit) <= RADIX ** 2
        max_norm = max(max_norm, parent.screen.norm(digit))
        for unit, image in enumerate(parent.screen.units(digit)):
            slot = parent.screen.index(image, RADIX)
            assert canonical[slot] == node
            if codes[slot] == EMPTY:
                codes[slot] = (seed_id << 5) | (exponent << 3) | unit
    assert EMPTY not in codes
    for slot, code in enumerate(codes):
        seed_id, exponent, unit = code >> 5, (code >> 3) & 3, code & 7
        assert seed_id < len(seeds) and exponent <= 2 and unit < 6
        image = parent.screen.units(parent.tau_power(seeds[seed_id], exponent))[unit]
        assert parent.screen.index(image, RADIX) == slot

    binary = bytearray(b"T103" + struct.pack("<I", len(seeds)))
    binary.extend(struct.pack(f"<{len(codes)}I", *codes))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output = HERE / "atlas-r1024-full-cache-budget.bin"
    output.write_bytes(binary)
    return {"residues": len(codes), "unit_classes": len(nodes),
            "cycle_count": len(cycles), "segment_lengths": dict(segment_lengths),
            "seed_count": len(seeds), "maximum_decoded_norm": max_norm,
            "cover_plan_sha256": plan_hash, "atlas_bytes": len(binary),
            "atlas_sha256": digest(binary)}


def main():
    full = build_full()
    terminal_source = HERE.parent / "prime-j0-power2-tau2-20261011" \
        / "atlas-r1024-terminal-tau2.bin"
    terminal_binary = terminal_source.read_bytes()
    terminal_path = HERE / "atlas-r1024-terminal-cache-budget.bin"
    terminal_path.write_bytes(terminal_binary)
    prior = json.loads((PARENT.parent / "atlas-receipt.json").read_bytes())
    terminal = prior["terminal"]
    assert terminal["atlas_sha256"] == digest(terminal_binary)
    slots = WINDOWS * full["seed_count"] + terminal["seed_count"]
    assert slots == 939_444
    receipt = {"schema": 1, "status": "constructed",
               "generator_sha256": digest(Path(__file__).read_bytes()),
               "parent_generator_sha256": digest(PARENT.read_bytes()),
               "radix": RADIX, "windows": WINDOWS, "full": full,
               "terminal": terminal, "affine_slots": slots,
               "affine_payload_bytes": slots * 64,
               "atlas_bytes": full["atlas_bytes"] + terminal["atlas_bytes"]}
    (HERE / "atlas-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
