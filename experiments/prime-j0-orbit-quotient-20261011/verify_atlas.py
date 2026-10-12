#!/usr/bin/env python3
"""Independently decode the quotient atlas for every full and terminal input."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "prime-j0-power2-tau2-20261011/verify_atlas.py"
SPEC = importlib.util.spec_from_file_location("independent_eisenstein", REFERENCE)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
RADIX = 1_024
SIZE = RADIX * RADIX


def digest(raw):
    return sha256(raw).hexdigest()


def full():
    raw = (HERE / "atlas-r1024-full-orbit-quotient.bin").read_bytes()
    magic, radix, classes, seeds_count, word_count = struct.unpack_from(
        "<4sIIII", raw)
    assert (magic, radix, classes, seeds_count, word_count) == (
        b"OQ13", RADIX, 174_764, 83_051, SIZE // 64)
    mask_start = 20
    rank_start = mask_start + 8 * word_count
    code_start = rank_start + 4 * (word_count + 1)
    seed_start = code_start + 3 * classes
    assert len(raw) == seed_start + 4 * seeds_count
    words = struct.unpack_from(f"<{word_count}Q", raw, mask_start)
    prefix = struct.unpack_from(f"<{word_count + 1}I", raw, rank_start)
    codes = memoryview(raw)[code_start:seed_start]
    seeds = list(struct.iter_unpack("<hh", raw[seed_start:]))
    assert len(seeds) == seeds_count and seeds[0] == (0, 0)
    assert len(set(seeds)) == seeds_count
    assert prefix[0] == 0 and prefix[-1] == classes
    for index, word in enumerate(words):
        assert prefix[index + 1] == prefix[index] + word.bit_count()

    canonical_classes = 0
    used = set()
    exponent_residues = Counter()
    maximum_norm = 0
    for slot in range(SIZE):
        pair = divmod(slot, RADIX)
        orbit_slots = [reference.residue(image)
                       for image in reference.units(pair)]
        canonical = min(orbit_slots)
        transform = orbit_slots.index(canonical)
        word_index, bit = divmod(slot, 64)
        is_canonical = bool(words[word_index] & (1 << bit))
        assert is_canonical == (slot == canonical)
        canonical_classes += is_canonical

        word_index, bit = divmod(canonical, 64)
        assert words[word_index] & (1 << bit)
        dense_index = prefix[word_index] + (
            words[word_index] & ((1 << bit) - 1)).bit_count()
        assert dense_index < classes
        code = int.from_bytes(codes[3 * dense_index:3 * dense_index + 3], "little")
        seed_id, exponent, canonical_unit = code >> 5, (code >> 3) & 3, code & 7
        assert seed_id < seeds_count and exponent <= 2 and canonical_unit < 6
        unit = 2 * ((canonical_unit // 2 - transform // 2) % 3) \
            + ((canonical_unit & 1) ^ (transform & 1))
        digit = seeds[seed_id]
        for _ in range(exponent):
            digit = reference.tau(digit)
        digit = reference.units(digit)[unit]
        assert reference.residue(digit) == slot
        value = reference.norm(digit)
        assert value <= SIZE
        maximum_norm = max(maximum_norm, value)
        used.add(seed_id)
        exponent_residues[exponent] += 1

    assert canonical_classes == classes and used == set(range(seeds_count))
    assert exponent_residues == {0: 498_298, 1: 485_604, 2: 64_674}
    for seed in seeds:
        canonical = min(reference.residue(image)
                        for image in reference.units(seed))
        assert seed == reference.nearest_wide_search(canonical)
    return {"atlas_sha256": digest(raw), "atlas_bytes": len(raw),
            "residues": SIZE, "unit_classes": classes,
            "seed_count": seeds_count, "rank_entries": len(prefix),
            "exponent_residues": dict(exponent_residues),
            "maximum_decoded_norm": maximum_norm}


def terminal():
    raw = (HERE / "atlas-r1024-terminal-orbit-quotient.bin").read_bytes()
    parent = (HERE.parent / "prime-j0-power2-tau2-20261011"
              / "atlas-r1024-terminal-tau2.bin").read_bytes()
    assert raw == parent
    magic, bound, b_min, b_max, seed_count, pair_count, reserved = \
        struct.unpack_from("<4sHhhIIH", raw)
    assert magic == b"R103" and bound == 149 and reserved == 0
    pairs, expected_rows = reference.enumerate_disk()
    assert pair_count == len(pairs) == 80_521
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
    assert used == set(range(seed_count)) and seed_count == 9_288
    return {"atlas_sha256": digest(raw), "atlas_bytes": len(raw),
            "pairs": pair_count, "seed_count": seed_count}


def main():
    generated = json.loads((HERE / "atlas-receipt.json").read_bytes())
    checked_full = full()
    checked_terminal = terminal()
    assert generated["full"]["atlas_sha256"] == checked_full["atlas_sha256"]
    assert generated["terminal"]["atlas_sha256"] == checked_terminal["atlas_sha256"]
    assert generated["full"]["exponent_residues"] == {
        str(key): value for key, value in checked_full["exponent_residues"].items()}
    receipt = {"schema": 1, "status": "passed",
               "full": checked_full, "terminal": checked_terminal,
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
