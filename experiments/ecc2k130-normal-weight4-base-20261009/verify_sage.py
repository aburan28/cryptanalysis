#!/usr/bin/env sage -python
"""Independently replay every normal-weight-four orbit with checked Sage."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import resource
import sys
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ, matrix


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_pairs(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate JSON key")
    return result


def encode(element) -> int:
    return sum(int(bit) << index for index, bit in enumerate(element.polynomial().list()))


def half_trace(element):
    term = element
    total = element
    for _ in range(65):
        term = term**4
        total += term
    if total**2 + total != element:
        raise ArithmeticError("half trace failed")
    return total


def canonical_from_bits(mask: int) -> int:
    positions = [index for index in range(131) if (mask >> index) & 1]
    if len(positions) != 4:
        raise ValueError("expected four normal coordinates")
    gaps = tuple((positions[(i + 1) % 4] - positions[i]) % 131 for i in range(4))
    a, b, c, _ = min(gaps[i:] + gaps[:i] for i in range(4))
    return 1 | (1 << a) | (1 << (a + b)) | (1 << (a + b + c))


def samples(domain: str, total: int, count: int) -> list[int]:
    selected: set[int] = set()
    counter = 0
    while len(selected) < count:
        digest = hashlib.sha256((domain + "|" + str(counter)).encode()).digest()
        selected.add(int.from_bytes(digest, "big") % total)
        counter += 1
    return sorted(selected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite a verification receipt")
    started = time.perf_counter()
    started_cpu = time.process_time()
    config = json.loads(CONFIG.read_text(), object_pairs_hook=strict_pairs)
    result = json.loads(args.result.read_text(), object_pairs_hook=strict_pairs)
    runtime = json.loads(args.runtime_info.read_text(), object_pairs_hook=strict_pairs)
    parent_path = ROOT / config["parent_normal_basis"]["path"]
    parent = json.loads(parent_path.read_text(), object_pairs_hook=strict_pairs)
    if (sha256(parent_path) != config["parent_normal_basis"]["sha256"]
            or result["parent_normal_result_sha256"] != sha256(parent_path)
            or result["config_sha256"] != sha256(CONFIG)
            or runtime.get("status") != "verified"):
        raise ValueError("source, result, or checked runtime identity mismatch")

    f2 = GF(2)
    polynomial_ring = PolynomialRing(f2, "t")
    t = polynomial_ring.gen()
    modulus = sum(t**exponent for exponent in config["field"]["modulus_exponents"])
    if not modulus.is_irreducible():
        raise ArithmeticError("field modulus is reducible")
    field = GF(2**131, "t", modulus=modulus)
    powers = [field.gen()**index for index in range(131)]

    def decode(word: int):
        return sum((powers[index] for index in range(131) if (word >> index) & 1),
                   field.zero())

    basis_words = [int(value) for value in parent["normal_orbit_polynomial_words"]]
    basis = [decode(value) for value in basis_words]
    if (len(basis) != 131
            or basis[0] != decode(int(config["parent_normal_basis"]["normal_element_decimal"]))
            or sum(basis, field.zero()) != field.one()
            or any(basis[index]**2 != basis[(index + 1) % 131]
                   for index in range(131))):
        raise ArithmeticError("normal basis replay failed")
    normal_matrix = matrix(f2, 131, 131,
                           lambda row, column: (basis_words[column] >> row) & 1)
    if normal_matrix.rank() != 131:
        raise ArithmeticError("normal basis does not span the field")
    inverse_matrix = normal_matrix.inverse()
    conversion = [sum(int(inverse_matrix[row, column]) << row for row in range(131))
                  for column in range(131)]
    if conversion != [int(value) for value in parent["polynomial_to_normal_columns"]]:
        raise ArithmeticError("normal conversion disagrees with the parent")

    def normal_coordinates(element) -> int:
        value = encode(element)
        output = 0
        while value:
            bit = value & -value
            output ^= conversion[bit.bit_length() - 1]
            value ^= bit
        return output

    all_digest = hashlib.sha256()
    rational_digest = hashlib.sha256()
    decisions_digest = hashlib.sha256()
    rational_masks: list[int] = []
    reciprocal: dict[int, int] = {}
    total = 0
    for a, b, c in itertools.combinations(range(1, 131), 3):
        gaps = (a, b - a, c - b, 131 - c)
        if gaps != min(gaps[index:] + gaps[:index] for index in range(4)):
            continue
        total += 1
        if total % 1024 == 0:
            if time.perf_counter() - started > config["resource_envelope"]["independent_sage_wall_seconds"]:
                raise TimeoutError("Sage replay wall limit exceeded")
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            used = usage if sys.platform == "darwin" else usage * 1024
            if used > config["resource_envelope"]["peak_rss_bytes"]:
                raise MemoryError("Sage replay RSS limit exceeded")
        mask = 1 | (1 << a) | (1 << b) | (1 << c)
        packed = mask.to_bytes(17, "little")
        all_digest.update(packed)
        w = basis[0] + basis[a] + basis[b] + basis[c]
        inverse = 1 / w
        coordinates = normal_coordinates(inverse)
        rational = int(inverse.trace()) == 0
        partner = coordinates.bit_count() == 4
        if partner and not rational:
            raise ArithmeticError("reciprocal rationality conflict")
        decisions_digest.update(bytes((int(rational) | (int(partner) << 1),)))
        if rational:
            rational_digest.update(packed)
            rational_masks.append(mask)
            if partner:
                reciprocal[mask] = canonical_from_bits(coordinates)
    if total != 89440 or total * 131 != math.comb(131, 4):
        raise ArithmeticError("wrong canonical orbit count")
    rational_set = set(rational_masks)
    for mask, partner in reciprocal.items():
        if (partner == mask or partner not in rational_set
                or reciprocal.get(partner) != mask):
            raise ArithmeticError("reciprocal pairing disagrees")
    if len(reciprocal) % 2:
        raise ArithmeticError("odd reciprocal-orbit count")
    quotient = len(rational_masks) - len(reciprocal) // 2
    observed = {
        "canonical_parameter_orbits": total,
        "rational_orbits": len(rational_masks),
        "reciprocal_partner_orbits": len(reciprocal),
        "reciprocal_orbit_pairs": len(reciprocal) // 2,
        "actual_usable_points_B": 2 * 131 * quotient,
        "sign_folded_columns_C": 131 * quotient,
        "signed_frobenius_columns_K": quotient,
        "all_canonical_orbit_representatives_sha256": all_digest.hexdigest(),
        "rational_canonical_orbit_representatives_sha256": rational_digest.hexdigest(),
        "rationality_and_reciprocal_flags_sha256": decisions_digest.hexdigest(),
    }
    for key, value in observed.items():
        if result[key] != value:
            raise ArithmeticError(f"producer mismatch: {key}")
    indexes = samples(config["independent_controls"]["point_sample_domain"],
                      len(rational_masks),
                      config["independent_controls"]["point_sample_count"])
    if (indexes != result["sample_indices"]
            or [str(rational_masks[index]) for index in indexes] != result["sample_masks"]):
        raise ArithmeticError("fixed point sample changed")

    curve = EllipticCurve(field, config["curve_coefficients_a1_a2_a3_a4_a6"])
    subgroup_order = ZZ(config["subgroup_order"])

    def projected(mask: int):
        positions = [index for index in range(131) if (mask >> index) & 1]
        w = sum((basis[index] for index in positions), field.zero())
        u = half_trace(w)
        x = 1 + 1 / u
        rhs = x + 1 / (x * x)
        if int(rhs.trace()) != 0:
            raise ArithmeticError("selected orbit has no source-curve lift")
        point = curve([x, x * half_trace(rhs)])
        image = 4 * point
        if image.is_zero() or subgroup_order * image != curve(0):
            raise ArithmeticError("invalid cofactor-four subgroup projection")
        return image

    group_checks = 0
    frobenius_checks = 0
    reciprocal_checks = 0
    for index in indexes:
        mask = rational_masks[index]
        point = projected(mask)
        group_checks += 1
        for exponent in (1, 2, 65, 130):
            rotated = ((mask << exponent) | (mask >> (131 - exponent))) & ((1 << 131) - 1)
            transformed = curve([point[0]**(2**exponent), point[1]**(2**exponent)])
            if projected(rotated) != transformed:
                raise ArithmeticError("Frobenius point action mismatch")
            frobenius_checks += 1
    reciprocal_sample = list(reciprocal)[:16]
    if [str(mask) for mask in reciprocal_sample] != result["reciprocal_sample_masks"]:
        raise ArithmeticError("reciprocal point sample changed")
    for mask in reciprocal_sample:
        point = projected(mask)
        field_word = sum((basis[bit] for bit in range(131) if (mask >> bit) & 1),
                         field.zero())
        inverse_mask = normal_coordinates(1 / field_word)
        if projected(inverse_mask) != point:
            raise ArithmeticError("reciprocal point identity mismatch")
        reciprocal_checks += 1
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == "darwin" else peak * 1024
    receipt = {
        "schema": "ecc2k130-normal-weight4-sage-replay-v1",
        "status": "PASS_FULL_SAGE_ORBIT_AND_POINT_REPLAY",
        "observed": observed,
        "sampled_group_points": group_checks,
        "sampled_frobenius_images": frobenius_checks,
        "sampled_reciprocal_point_checks": reciprocal_checks,
        "config_sha256": sha256(CONFIG),
        "parent_sha256": sha256(parent_path),
        "producer_result_sha256": sha256(args.result),
        "runtime_info_sha256": sha256(args.runtime_info),
        "verifier_sha256": sha256(Path(__file__)),
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": time.process_time() - started_cpu,
        "peak_rss_bytes": peak,
        "ordinary_pdp_queries": 0,
    }
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(receipt["status"], observed)


if __name__ == "__main__":
    main()
