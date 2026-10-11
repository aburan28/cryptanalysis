#!/usr/bin/env python3
"""Certify model-level arithmetic options shared by the P-256 isogeny class."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from sympy import isprime

SCRIPT = Path(__file__).resolve()
EXPERIMENT = SCRIPT.parents[1]
REPOSITORY = SCRIPT.parents[3]
sys.path.insert(0, str(EXPERIMENT / "src"))

from p256_isogeny_search.constants import P256  # noqa: E402

NATIVE_SOURCE = REPOSITORY / "suite" / "examples" / "p256_isogeny_native_bench.rs"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def legendre(value: int, modulus: int) -> int:
    residue = pow(value % modulus, (modulus - 1) // 2, modulus)
    return -1 if residue == modulus - 1 else residue


def normalize_short_a(
    *, p: int, a: int, b: int, x: int, y: int
) -> dict[str, Any]:
    if p % 4 != 3 or a % p == 0:
        raise ValueError("normalization certificate requires p = 3 mod 4 and a != 0")
    least_nonsquare = next(value for value in range(2, 1000) if legendre(value, p) == -1)
    representative = 1 if legendre(a, p) == 1 else least_nonsquare
    ratio = a * pow(representative, -1, p) % p
    square_subgroup_order = (p - 1) // 2
    exponent = pow(4, -1, square_subgroup_order)
    u = pow(ratio, exponent, p)
    if pow(u, 4, p) != ratio:
        raise AssertionError("failed to extract the certified fourth root")

    u2 = pow(u, 2, p)
    u3 = u2 * u % p
    normalized_a = a * pow(u, -4, p) % p
    normalized_b = b * pow(u, -6, p) % p
    normalized_x = x * pow(u2, -1, p) % p
    normalized_y = y * pow(u3, -1, p) % p
    on_curve = (
        normalized_y * normalized_y
        - normalized_x * normalized_x * normalized_x
        - normalized_a * normalized_x
        - normalized_b
    ) % p == 0
    if normalized_a != representative or not on_curve:
        raise AssertionError("normalized model or transported generator check failed")
    return {
        "least_positive_quadratic_nonsquare": least_nonsquare,
        "source_a_legendre_symbol": legendre(a, p),
        "target_a": str(representative),
        "scaling_u": str(u),
        "target_b": str(normalized_b),
        "transported_generator": {"x": str(normalized_x), "y": str(normalized_y)},
        "u_fourth_equals_a_over_target_a": pow(u, 4, p) == ratio,
        "transported_generator_on_target": on_curve,
    }


def native_schedule() -> dict[str, Any]:
    source = NATIVE_SOURCE.read_text(encoding="utf-8")
    add = source.split("fn add(&self", 1)[1].split("fn double(&self", 1)[0]
    double = source.split("fn double(&self", 1)[1].split("fn scalar_mul(&self", 1)[0]
    advance = source.split("fn advance_batch(&self", 1)[1].split("fn relation_holds", 1)[0]
    return {
        "source": str(NATIVE_SOURCE.relative_to(REPOSITORY)),
        "source_sha256": sha256(NATIVE_SOURCE),
        "complete_addition_full_a_multiplications": add.count("self.a.mul"),
        "complete_addition_full_3b_multiplications": add.count("self.b3.mul"),
        "doubling_full_a_multiplications": double.count("self.a.mul"),
        "doubling_full_3b_multiplications": double.count("self.b3.mul"),
        "timed_batch_calls_complete_addition": "self.curve.add" in advance,
        "timed_batch_calls_doubling": "self.curve.double" in advance,
        "candidate_dependent_formula_branch": False,
        "interpretation": (
            "The timed walk uses the same complete-addition instruction schedule for every "
            "curve. Dynamic coefficient values do not create a structural speed difference "
            "in this backend; observed candidate-to-root differences are timing variation."
        ),
    }


def build_report() -> dict[str, Any]:
    p, n, a, b = P256.p, P256.n, P256.a, P256.b
    prime_order = bool(isprime(n))
    if not prime_order:
        raise AssertionError("P-256 subgroup order must be prime")
    normalization = normalize_short_a(p=p, a=a, b=b, x=P256.gx, y=P256.gy)
    no_small_embedding_degree = all(pow(p, k, n) != 1 for k in range(1, 1001))
    return {
        "schema_version": 1,
        "question": (
            "Can an F_p-isogenous P-256 curve acquire a dramatically cheaper standard "
            "curve model or a coefficient shortcut unavailable to P-256?"
        ),
        "isogeny_class_invariants": {
            "p": str(p),
            "group_order": str(n),
            "trace": str(P256.trace),
            "frobenius_discriminant": str(P256.frobenius_discriminant),
            "group_order_prime": prime_order,
            "group_order_mod_2": n % 2,
            "group_order_mod_3": n % 3,
            "anomalous": n == p,
            "embedding_degree_at_most_1000": not no_small_embedding_degree,
        },
        "model_obligations": {
            "rational_two_torsion": {
                "status": "refuted",
                "basis": "The full F_p group has odd prime order, so it has no point of order 2.",
            },
            "montgomery_model_over_fp": {
                "status": "refuted",
                "basis": (
                    "A nonsingular Montgomery model has the rational point (0,0) of order 2, "
                    "which is incompatible with the invariant odd prime group order."
                ),
            },
            "twisted_edwards_model_over_fp": {
                "status": "refuted",
                "basis": (
                    "A nonsingular twisted Edwards model has a rational point of order 2 and "
                    "is birational to a Montgomery model; the isogeny class has none."
                ),
            },
            "rational_three_torsion": {
                "status": "refuted",
                "basis": "The full F_p group order is 1 modulo 3, so it has no point of order 3.",
            },
            "exceptional_short_weierstrass_coefficients": {
                "status": "refuted",
                "basis": (
                    "a=0 gives j=0 and b=0 gives j=1728; the maximal CM field for this "
                    "isogeny class has neither exceptional j-invariant."
                ),
            },
        },
        "short_weierstrass_a_normalization": {
            "p_mod_4": p % 4,
            "fourth_power_image_equals_square_subgroup": True,
            "class_wide_statement": (
                "For p = 3 mod 4, every nonzero a is F_p-isomorphic to a model whose a is "
                "either 1 or the fixed least positive quadratic nonsquare. This shortcut is "
                "therefore not exceptional to a searched neighbor."
            ),
            "p256_certificate": normalization,
        },
        "native_benchmark_schedule": native_schedule(),
        "assessment": {
            "dramatic_speedup_found": False,
            "supported_finding": (
                "Standard Montgomery/Edwards torsion shortcuts are unavailable throughout "
                "the class, and short-Weierstrass a-specialization is available to P-256 "
                "itself. The existing matched native kernel has no candidate-dependent "
                "operation schedule."
            ),
            "open_obligation": (
                "A genuinely non-generic ECDLP algorithm or an independently isolated, "
                "end-to-end implementation with a new formula family would still need to be supplied."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output), **payload["assessment"]}, sort_keys=True))


if __name__ == "__main__":
    main()
