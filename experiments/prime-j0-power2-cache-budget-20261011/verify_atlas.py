#!/usr/bin/env python3
"""Independently decode every cache-budgeted residue and terminal pair."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "prime-j0-power2-tau2-20261011/verify_atlas.py"
SPEC = importlib.util.spec_from_file_location("independent_three_image", REFERENCE)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
RADIX = 1024


def digest(raw):
    return sha256(raw).hexdigest()


def full():
    raw = (HERE / "atlas-r1024-full-cache-budget.bin").read_bytes()
    assert raw[:4] == b"T103"
    seed_count = struct.unpack_from("<I", raw, 4)[0]
    assert seed_count == 77_513
    count = RADIX * RADIX
    assert len(raw) == 8 + 4 * count + 4 * seed_count
    codes = struct.unpack_from(f"<{count}I", raw, 8)
    seeds = list(struct.iter_unpack("<hh", raw[8 + 4 * count:]))
    assert len(seeds) == seed_count and seeds[0] == (0, 0)
    assert len(set(seeds)) == seed_count

    used = set()
    exponent_counts = Counter()
    max_norm = 0
    for slot, code in enumerate(codes):
        digit, seed_id, exponent = reference.decode(code, seeds)
        assert reference.residue(digit) == slot
        value = reference.norm(digit)
        assert value <= count
        max_norm = max(max_norm, value)
        used.add(seed_id)
        exponent_counts[exponent] += 1
    assert used == set(range(seed_count))
    assert exponent_counts[2] == 118_842
    for seed in seeds:
        slot = min(reference.residue(image) for image in reference.units(seed))
        assert seed == reference.nearest_wide_search(slot)
    return {"atlas_sha256": digest(raw), "atlas_bytes": len(raw),
            "residues": count, "seed_count": seed_count,
            "exponent_residues": dict(exponent_counts),
            "maximum_decoded_norm": max_norm}


def terminal():
    raw = (HERE / "atlas-r1024-terminal-cache-budget.bin").read_bytes()
    prior = (HERE.parent / "prime-j0-power2-tau2-20261011"
             / "atlas-r1024-terminal-tau2.bin").read_bytes()
    assert raw == prior
    magic, bound, b_min, b_max, seed_count, pair_count, reserved = \
        struct.unpack_from("<4sHhhIIH", raw)
    assert magic == b"R103" and bound == 149 and reserved == 0
    assert seed_count == 9_288
    pairs, expected_rows = reference.enumerate_disk()
    assert len(pairs) == pair_count
    assert (b_min, b_max) == (expected_rows[0][0], expected_rows[-1][0])
    rows = [struct.unpack_from("<hHI", raw, 20 + 8 * index)
            for index in range(len(expected_rows))]
    assert rows == [(a_min, length, offset)
                    for _, a_min, length, offset in expected_rows]
    code_start = 20 + 8 * len(rows)
    seed_start = code_start + 4 * pair_count
    assert len(raw) == seed_start + 4 * seed_count
    codes = struct.unpack_from(f"<{pair_count}I", raw, code_start)
    seeds = list(struct.iter_unpack("<hh", raw[seed_start:]))
    used = set()
    for pair, code in zip(pairs, codes):
        digit, seed_id, _ = reference.decode(code, seeds)
        assert digit == pair
        used.add(seed_id)
    assert used == set(range(seed_count))
    return {"atlas_sha256": digest(raw), "atlas_bytes": len(raw),
            "pairs": pair_count, "seed_count": seed_count}


def main():
    construction = json.loads((HERE / "atlas-receipt.json").read_bytes())
    screening = json.loads((HERE / "screen.json").read_bytes())
    checked_plan = json.loads((HERE / "independent-check.json").read_bytes())
    assert checked_plan["status"] == "passed"
    checked_full = full()
    checked_terminal = terminal()
    assert checked_full["atlas_sha256"] == construction["full"]["atlas_sha256"]
    assert checked_terminal["atlas_sha256"] == construction["terminal"]["atlas_sha256"]
    assert checked_full["exponent_residues"][2] == \
        screening["budgeted_exponent_two_residues"]
    assert construction["affine_slots"] == \
        12 * checked_full["seed_count"] + checked_terminal["seed_count"]
    receipt = {"schema": 1, "status": "passed", "full": checked_full,
               "terminal": checked_terminal,
               "verifier_sha256": digest(Path(__file__).read_bytes()),
               "reference_verifier_sha256": digest(REFERENCE.read_bytes())}
    output = HERE / "atlas-independent-check.json"
    if output.exists():
        assert json.loads(output.read_text()) == receipt
    else:
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
