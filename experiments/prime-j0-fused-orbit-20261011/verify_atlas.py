#!/usr/bin/env python3
"""Exhaustively verify fused orbit records against independent digits."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ADIC = ROOT / "prime-j0-adic-orbit-20261011"
SPEC = importlib.util.spec_from_file_location("adic_fused_control", ADIC / "verify_group.py")
adic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adic)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def tau(pair):
    a, b = pair
    return -3 * b, a + 3 * b


def omega(pair):
    a, b = pair
    return a + 3 * b, -a - 2 * b


def apply_unit(pair, unit):
    for _ in range(unit // 2):
        pair = omega(pair)
    return (-pair[0], -pair[1]) if unit & 1 else pair


def inverse_transform(pair, transform):
    power = (3 - transform // 2) % 3
    return apply_unit(pair, 2 * power + (transform & 1))


def norm(pair):
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def main():
    path = HERE / "atlas-r1024-full-fused-orbit.bin"
    raw = path.read_bytes()
    magic, radix, classes, seeds = struct.unpack_from("<4sIII", raw)
    assert (magic, radix, classes, seeds) == (b"FO18", 1024, 174_764, 83_051)
    seed_start = 16 + 8 * classes
    assert len(raw) == seed_start + 4 * seeds == 1_730_332
    old_path = ADIC / "atlas-r1024-full-adic-orbit.bin"
    old = adic.AdicFullAtlas(old_path)
    old_terminal = ADIC / "atlas-r1024-terminal-adic-orbit.bin"
    terminal = HERE / "atlas-r1024-terminal-fused-orbit.bin"
    assert terminal.read_bytes() == old_terminal.read_bytes()
    for class_index, (a, b) in adic.index.representatives():
        code, da, db = struct.unpack_from("<Ihh", raw, 16 + 8 * class_index)
        seed, exponent, canonical_unit = code >> 5, (code >> 3) & 3, code & 7
        assert seed < seeds and exponent < 3 and canonical_unit < 6
        tau_digit = struct.unpack_from("<hh", raw, seed_start + 4 * seed)
        for _ in range(exponent):
            tau_digit = tau(tau_digit)
        assert apply_unit(tau_digit, canonical_unit) == (da, db)
        assert (da % radix, db % radix) == (a, b)
    differences = Counter()
    exponent_residues = Counter()
    maximum_norm = 0
    for a in range(radix):
        for b in range(radix):
            class_index, transform = adic.index.canonicalize(a, b)
            code, da, db = struct.unpack_from("<Ihh", raw, 16 + 8 * class_index)
            seed, exponent, canonical_unit = code >> 5, (code >> 3) & 3, code & 7
            unit = 2 * ((canonical_unit // 2 - transform // 2) % 3) \
                + ((canonical_unit & 1) ^ (transform & 1))
            digit = inverse_transform((da, db), transform)
            assert (digit[0] % radix, digit[1] % radix) == (a, b)
            value = norm(digit)
            assert value <= radix * radix
            maximum_norm = max(maximum_norm, value)
            exponent_residues[exponent] += 1
            old_digit, old_seed, old_exponent, old_unit = old.decode(a, b)
            differences["digit"] += digit != old_digit
            differences["seed"] += seed != old_seed
            differences["exponent"] += exponent != old_exponent
            differences["unit"] += unit != old_unit
    assert set(differences.values()) == {0}
    assert exponent_residues[2] == 64_674
    receipt = {"schema": 1, "status": "passed",
               "residues": radix * radix, "classes": classes,
               "maximum_digit_norm": maximum_norm,
               "exponent_residues": dict(exponent_residues),
               "differences_from_direct_index": dict(differences),
               "full_atlas_sha256": digest(path),
               "terminal_atlas_sha256": digest(terminal),
               "parent_atlas_sha256": digest(old_path),
               "verifier_sha256": digest(Path(__file__))}
    (HERE / "atlas-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
