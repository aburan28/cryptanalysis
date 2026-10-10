#!/usr/bin/env python3
"""Exact orbit-representative census for the frozen normal-weight-four base."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate JSON key")
    return result


def cyclic_gap_representatives(degree: int):
    """Yield the least four-gap rotation and its canonical bit mask."""
    for a in range(1, degree - 2):
        for b in range(1, degree - a - 1):
            for c in range(1, degree - a - b):
                d = degree - a - b - c
                gaps = (a, b, c, d)
                if gaps != min(gaps[i:] + gaps[:i] for i in range(4)):
                    continue
                mask = 1 | (1 << a) | (1 << (a + b)) | (1 << (a + b + c))
                yield gaps, mask


def canonical_mask(mask: int, degree: int) -> int:
    positions = [index for index in range(degree) if (mask >> index) & 1]
    if len(positions) != 4:
        raise ValueError("expected normal weight four")
    gaps = tuple((positions[(i + 1) % 4] - positions[i]) % degree
                 for i in range(4))
    a, b, c, _ = min(gaps[i:] + gaps[:i] for i in range(4))
    return 1 | (1 << a) | (1 << (a + b)) | (1 << (a + b + c))


def square_mod(value: int, modulus: int, degree: int) -> int:
    square = 0
    while value:
        bit = value & -value
        square ^= 1 << (2 * (bit.bit_length() - 1))
        value ^= bit
    while square.bit_length() > degree:
        square ^= modulus << (square.bit_length() - degree - 1)
    return square


def inverse_mod(value: int, modulus: int, degree: int) -> int:
    if value == 0:
        raise ZeroDivisionError("zero field element")
    left, right = value, modulus
    left_coefficient, right_coefficient = 1, 0
    while left != 1:
        if left == 0:
            raise ArithmeticError("field inverse does not exist")
        shift = left.bit_length() - right.bit_length()
        if shift < 0:
            left, right = right, left
            left_coefficient, right_coefficient = right_coefficient, left_coefficient
            shift = -shift
        left ^= right << shift
        left_coefficient ^= right_coefficient << shift
    while left_coefficient.bit_length() > degree:
        left_coefficient ^= modulus << (left_coefficient.bit_length() - degree - 1)
    return left_coefficient


def multiply_mod(left: int, right: int, modulus: int, degree: int) -> int:
    product = 0
    while right:
        if right & 1:
            product ^= left
        right >>= 1
        left <<= 1
        if left & (1 << degree):
            left ^= modulus
    return product


def transform(value: int, columns: list[int]) -> int:
    result = 0
    while value:
        bit = value & -value
        result ^= columns[bit.bit_length() - 1]
        value ^= bit
    return result


def choose_indices(domain: str, total: int, count: int) -> list[int]:
    if total < count:
        raise ValueError("insufficient rational orbits for audit sample")
    selected: set[int] = set()
    counter = 0
    while len(selected) < count:
        digest = hashlib.sha256(f"{domain}|{counter}".encode()).digest()
        selected.add(int.from_bytes(digest, "big") % total)
        counter += 1
    return sorted(selected)


def derive(config: dict, started: float, started_cpu: float) -> dict:
    field = config["field"]
    degree = field["degree"]
    if field["characteristic"] != 2 or degree != 131:
        raise ValueError("wrong field")
    modulus = sum(1 << exponent for exponent in field["modulus_exponents"])
    if modulus != (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1:
        raise ValueError("wrong modulus")
    parent_path = ROOT / config["parent_normal_basis"]["path"]
    if sha256(parent_path) != config["parent_normal_basis"]["sha256"]:
        raise ValueError("parent normal-basis receipt hash changed")
    parent = json.loads(parent_path.read_text(), object_pairs_hook=strict_pairs)
    normal = config["parent_normal_basis"]
    if (parent["schema"] != "ecc2k130-w24-normal-barrel-result-v1"
            or parent["normal_element"] != normal["normal_element_decimal"]
            or parent["normal_element_search_counter"] != normal["normal_element_search_counter"]
            or parent["conversion_matrix_sha256"]["normal_to_polynomial"]
            != normal["normal_to_polynomial_matrix_sha256"]
            or parent["conversion_matrix_sha256"]["polynomial_to_normal"]
            != normal["polynomial_to_normal_matrix_sha256"]):
        raise ValueError("parent normal-basis identity changed")
    basis = [int(word) for word in parent["normal_orbit_polynomial_words"]]
    to_normal = [int(word) for word in parent["polynomial_to_normal_columns"]]
    to_polynomial = [int(word) for word in parent["normal_to_polynomial_columns"]]
    if len(basis) != degree or len(to_normal) != degree or len(to_polynomial) != degree:
        raise ValueError("incomplete normal-basis matrices")
    if basis != to_polynomial:
        raise ValueError("normal orbit and conversion columns disagree")
    if transform((1 << degree) - 1, basis) != 1:
        raise ValueError("normal generator does not have trace one")
    for index, word in enumerate(basis):
        if square_mod(word, modulus, degree) != basis[(index + 1) % degree]:
            raise ValueError(f"Frobenius orbit mismatch at {index}")
        if transform(word, to_normal) != 1 << index:
            raise ValueError(f"inverse matrix mismatch at normal column {index}")
        if transform(to_normal[index], basis) != 1 << index:
            raise ValueError(f"inverse matrix mismatch at polynomial column {index}")

    all_digest = hashlib.sha256()
    rational_digest = hashlib.sha256()
    decisions_digest = hashlib.sha256()
    rational_masks: list[int] = []
    reciprocal: dict[int, int] = {}
    representative_count = 0
    for _, mask in cyclic_gap_representatives(degree):
        representative_count += 1
        if representative_count % 1024 == 0:
            if time.perf_counter() - started > config["resource_envelope"]["producer_wall_seconds"]:
                raise TimeoutError("producer wall limit exceeded")
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            used = usage if sys.platform == "darwin" else usage * 1024
            if used > config["resource_envelope"]["peak_rss_bytes"]:
                raise MemoryError("producer RSS limit exceeded")
        packed = mask.to_bytes(17, "little")
        all_digest.update(packed)
        field_word = transform(mask, basis)
        inverse = inverse_mod(field_word, modulus, degree)
        if multiply_mod(field_word, inverse, modulus, degree) != 1:
            raise ArithmeticError("field inverse replay failed")
        inverse_normal = transform(inverse, to_normal)
        rational = inverse_normal.bit_count() % 2 == 0
        in_base_partner = inverse_normal.bit_count() == 4
        if in_base_partner and not rational:
            raise ArithmeticError("reciprocal partner violates rationality")
        decisions_digest.update(bytes((int(rational) | (int(in_base_partner) << 1),)))
        if rational:
            rational_digest.update(packed)
            rational_masks.append(mask)
            if in_base_partner:
                reciprocal[mask] = canonical_mask(inverse_normal, degree)
    expected = config["factor_base"]
    if (representative_count != expected["cyclic_frobenius_orbit_count"]
            or representative_count * degree != expected["raw_parameter_count"]
            or math.comb(degree, 4) != expected["raw_parameter_count"]):
        raise ArithmeticError("wrong orbit count")
    rational_set = set(rational_masks)
    if len(rational_set) != len(rational_masks):
        raise ArithmeticError("duplicate rational orbit representatives")
    for mask, partner in reciprocal.items():
        if (partner == mask or partner not in rational_set
                or reciprocal.get(partner) != mask):
            raise ArithmeticError("reciprocal orbit pairing is incomplete")
    if len(reciprocal) % 2:
        raise ArithmeticError("odd reciprocal partner-orbit count")
    orbits = len(rational_masks) - len(reciprocal) // 2
    signed = degree * orbits
    usable = 2 * signed
    subgroup = int(config["subgroup_order"])
    formal_mean_numerator = math.comb(usable + 5, 6)
    sample_indices = choose_indices(
        config["independent_controls"]["point_sample_domain"],
        len(rational_masks), config["independent_controls"]["point_sample_count"])
    sampled_masks = [rational_masks[index] for index in sample_indices]
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == "darwin" else peak * 1024
    return {
        "schema": "ecc2k130-normal-weight4-source-census-v1",
        "status": "PRODUCED_PENDING_INDEPENDENT_SAGE_REPLAY",
        "proposal_id": config["proposal_id"],
        "candidate_id": None,
        "raw_parameter_count": expected["raw_parameter_count"],
        "canonical_parameter_orbits": representative_count,
        "rational_orbits": len(rational_masks),
        "reciprocal_partner_orbits": len(reciprocal),
        "reciprocal_orbit_pairs": len(reciprocal) // 2,
        "actual_usable_points_B": usable,
        "sign_folded_columns_C": signed,
        "signed_frobenius_columns_K": orbits,
        "all_canonical_orbit_representatives_sha256": all_digest.hexdigest(),
        "rational_canonical_orbit_representatives_sha256": rational_digest.hexdigest(),
        "rationality_and_reciprocal_flags_sha256": decisions_digest.hexdigest(),
        "sample_indices": sample_indices,
        "sample_masks": [str(mask) for mask in sampled_masks],
        "reciprocal_sample_masks": [str(mask) for mask in list(reciprocal)[:16]],
        "formal_m6_multiset_mean_numerator": str(formal_mean_numerator),
        "formal_m6_multiset_mean_denominator": str(subgroup - 1),
        "necessary_count_conditions_met": (
            usable >= config["advancement_gate"]["necessary_m6_uniform_support_B"]
            and orbits <= config["advancement_gate"]["maximum_columns_for_one_percent_of_w24_source_K"]
        ),
        "ordinary_pdp_queries": 0,
        "verified_novel_rank": None,
        "target_online_ms": None,
        "config_sha256": sha256(CONFIG),
        "parent_normal_result_sha256": sha256(parent_path),
        "producer_sha256": sha256(Path(__file__)),
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": time.process_time() - started_cpu,
        "peak_rss_bytes": peak,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite an existing result")
    started = time.perf_counter()
    started_cpu = time.process_time()
    config = json.loads(CONFIG.read_text(), object_pairs_hook=strict_pairs)
    result = derive(config, started, started_cpu)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(result["status"], result["rational_orbits"], result["signed_frobenius_columns_K"])


if __name__ == "__main__":
    main()
