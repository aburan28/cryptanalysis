#!/usr/bin/env python3
"""Exhaustively replay direct-index atlas digits against curve arithmetic."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUOTIENT = ROOT / "prime-j0-orbit-quotient-20261011"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


candidate = load("adic_atlas_index", HERE / "index.py")
oracle = load("adic_orbit_oracle", HERE / "verify_index.py")
prior = load("quotient_atlas_control", QUOTIENT / "verify_group.py")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def tau(pair):
    a, b = pair
    return -3 * b, a + 3 * b


def signed_images(pair):
    a, b = pair
    result = []
    for _ in range(3):
        result.extend(((a, b), (-a, -b)))
        a, b = a + 3 * b, -a - 2 * b
    return result


def norm(pair):
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def main():
    full_path = HERE / "atlas-r1024-full-adic-orbit.bin"
    raw = full_path.read_bytes()
    magic, radix, classes, seeds = struct.unpack_from("<4sIII", raw)
    assert (magic, radix, classes, seeds) == (b"AO14", 1024, 174_764, 83_051)
    code_start = 16
    seed_start = code_start + 3 * classes
    assert len(raw) == seed_start + 4 * seeds == 856_512
    representatives = list(oracle.oracle_representatives())
    assert len(representatives) == classes
    old = prior.QuotientFullAtlas(
        QUOTIENT / "atlas-r1024-full-orbit-quotient.bin")
    differences = Counter()
    exponent_residues = Counter()
    maximum_norm = 0
    for a in range(radix):
        for b in range(radix):
            class_index, transform = candidate.canonicalize(a, b)
            assert oracle.images((a, b))[transform] == representatives[class_index]
            code = int.from_bytes(raw[code_start + 3 * class_index:
                                      code_start + 3 * class_index + 3], "little")
            seed_id, exponent, canonical_unit = code >> 5, (code >> 3) & 3, code & 7
            assert seed_id < seeds and exponent < 3 and canonical_unit < 6
            seed = struct.unpack_from("<hh", raw, seed_start + 4 * seed_id)
            tau_digit = seed
            for _ in range(exponent):
                tau_digit = tau(tau_digit)
            encoded = signed_images(tau_digit)[canonical_unit]
            assert (encoded[0] % radix, encoded[1] % radix) == \
                representatives[class_index]
            unit = 2 * ((canonical_unit // 2 - transform // 2) % 3) \
                + ((canonical_unit & 1) ^ (transform & 1))
            digit = signed_images(tau_digit)[unit]
            assert (digit[0] % radix, digit[1] % radix) == (a, b)
            weight = norm(digit)
            assert weight <= radix * radix
            maximum_norm = max(maximum_norm, weight)
            exponent_residues[exponent] += 1
            old_digit, old_seed, old_exponent, old_unit = old.decode(a, b)
            differences["digit"] += digit != old_digit
            differences["seed"] += seed_id != old_seed
            differences["exponent"] += exponent != old_exponent
            differences["unit"] += unit != old_unit
    assert exponent_residues[2] == 64_674
    receipt = {"schema": 1, "status": "passed",
               "residues": radix * radix, "classes": classes,
               "maximum_digit_norm": maximum_norm,
               "exponent_residues": dict(exponent_residues),
               "differences_from_lex_quotient": dict(differences),
               "full_atlas_sha256": digest(full_path),
               "index_source_sha256": digest(HERE / "index.py"),
               "verifier_sha256": digest(Path(__file__))}
    (HERE / "atlas-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
