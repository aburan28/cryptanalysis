"""Exact structural analysis of the P-256 isogeny class."""

from __future__ import annotations

import math
from typing import Any, Iterable

from sympy import factorint, isprime, kronecker_symbol, primerange

from .constants import P256, P256_FROBENIUS_DISCRIMINANT_FACTORS, PrimeCurve
from .ec import ShortWeierstrassCurve


# Pocklington certificates for the discriminant factors above 64 bits.  Each
# entry gives the complete factorization of n-1 and one witness per distinct
# prime divisor.  Leaves below 2^64 are proved with deterministic Miller-Rabin.
_POCKLINGTON_CERTIFICATES: dict[int, tuple[dict[int, int], dict[int, int]]] = {
    1_428_624_589_419_343_516_204_097: (
        {2: 6, 1669: 1, 13_374_631_042_347_059_581: 1},
        {2: 3, 1669: 2, 13_374_631_042_347_059_581: 2},
    ),
    46_523_541_035_814_968_339_936_406_074_986_559_003_387: (
        {
            2: 1,
            269: 1,
            643: 1,
            215_531: 1,
            333_814_693: 1,
            1_869_236_796_843_064_056_413: 1,
        },
        {
            2: 2,
            269: 2,
            643: 2,
            215_531: 2,
            333_814_693: 2,
            1_869_236_796_843_064_056_413: 2,
        },
    ),
    1_869_236_796_843_064_056_413: (
        {2: 2, 23: 1, 3911: 1, 5_195_037_399_650_551: 1},
        {2: 2, 23: 2, 3911: 2, 5_195_037_399_650_551: 2},
    ),
}


def _is_prime_u64(value: int) -> bool:
    """Deterministic Miller-Rabin primality test for unsigned 64-bit integers."""
    if value < 2:
        return False
    small_primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for prime in small_primes:
        if value % prime == 0:
            return value == prime
    d = value - 1
    shifts = 0
    while d % 2 == 0:
        shifts += 1
        d //= 2
    for base in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
        if base % value == 0:
            continue
        x = pow(base, d, value)
        if x in (1, value - 1):
            continue
        for _ in range(shifts - 1):
            x = x * x % value
            if x == value - 1:
                break
        else:
            return False
    return True


def prove_prime(value: int) -> bool:
    """Verify an in-tree recursive Pocklington primality certificate."""
    if value < 1 << 64:
        return _is_prime_u64(value)
    certificate = _POCKLINGTON_CERTIFICATES.get(value)
    if certificate is None:
        return False
    factors, witnesses = certificate
    if math.prod(prime**exponent for prime, exponent in factors.items()) != value - 1:
        return False
    if not all(prove_prime(prime) for prime in factors):
        return False
    for prime in factors:
        witness = witnesses[prime]
        if pow(witness, value - 1, value) != 1:
            return False
        if math.gcd(pow(witness, (value - 1) // prime, value) - 1, value) != 1:
            return False
    return True


def _integer(value: int) -> dict[str, Any]:
    magnitude = abs(value)
    hex_value = hex(magnitude)
    if value < 0:
        hex_value = "-" + hex_value
    return {
        "decimal": str(value),
        "hex": hex_value,
        "bits": magnitude.bit_length(),
    }


def is_fundamental_discriminant(discriminant: int, factors: Iterable[int]) -> bool:
    """Check the fundamental-discriminant criterion using prime factors."""
    factor_list = tuple(factors)
    if len(set(factor_list)) != len(factor_list):
        return False
    squarefree_abs = math.prod(factor_list)
    if squarefree_abs != abs(discriminant):
        return False
    if discriminant % 4 == 1:
        return True
    if discriminant % 4 == 0:
        quotient = discriminant // 4
        return quotient % 4 in (2, 3)
    return False


def verified_discriminant_factors(refactor: bool = False) -> tuple[int, ...]:
    """Return and verify a complete prime factorization of |D_pi|."""
    absolute_discriminant = abs(P256.frobenius_discriminant)
    if refactor:
        discovered = factorint(absolute_discriminant)
        factors = tuple(
            sorted(prime for prime, exponent in discovered.items() for _ in range(exponent))
        )
    else:
        factors = tuple(sorted(P256_FROBENIUS_DISCRIMINANT_FACTORS))

    if math.prod(factors) != absolute_discriminant:
        raise AssertionError("stored factors do not multiply to |D_pi|")
    composites = [factor for factor in factors if not prove_prime(factor)]
    if composites:
        raise AssertionError(f"non-prime discriminant factors: {composites}")
    return factors


def validate_curve(curve: PrimeCurve) -> dict[str, bool]:
    model = ShortWeierstrassCurve(curve.p, curve.a, curve.b)
    generator = model.from_affine((curve.gx, curve.gy))
    return {
        "field_modulus_prime": bool(isprime(curve.p)),
        "group_order_prime": bool(isprime(curve.n)),
        "curve_nonsingular": (4 * pow(curve.a, 3, curve.p) + 27 * pow(curve.b, 2, curve.p))
        % curve.p
        != 0,
        "generator_on_curve": model.is_on_curve((curve.gx, curve.gy)),
        "generator_has_declared_order": model.scalar_mul(curve.n, generator).is_infinity,
    }


def small_isogeny_degree_classes(discriminant: int, bound: int) -> dict[str, list[int]]:
    classes: dict[str, list[int]] = {"ramified": [], "split": [], "inert": []}
    for prime in primerange(2, bound + 1):
        symbol = int(kronecker_symbol(discriminant, prime))
        classes[{0: "ramified", 1: "split", -1: "inert"}[symbol]].append(int(prime))
    return classes


def structural_report(
    *, refactor: bool = False, isogeny_prime_bound: int = 199
) -> dict[str, Any]:
    curve = P256
    trace = curve.trace
    discriminant = curve.frobenius_discriminant
    factors = verified_discriminant_factors(refactor=refactor)
    fundamental = is_fundamental_discriminant(discriminant, factors)
    if not fundamental:
        raise AssertionError("P-256 D_pi was expected to be fundamental")

    # For D_K == 1 mod 4, every non-rational alpha in O_K can be written
    # (u + v sqrt(D_K))/2 with v != 0.  Its norm is at least |D_K|/4.
    non_scalar_norm_lower_bound = (abs(discriminant) + 3) // 4
    degree_classes = small_isogeny_degree_classes(discriminant, isogeny_prime_bound)
    checks = validate_curve(curve)
    if not all(checks.values()):
        raise AssertionError(f"curve validation failed: {checks}")

    rho_steps_no_automorphism = math.sqrt(math.pi * curve.n / 2)
    rho_steps_with_negation = math.sqrt(math.pi * curve.n / 4)

    return {
        "schema_version": 1,
        "curve": {
            "name": curve.name,
            "p": _integer(curve.p),
            "a": _integer(curve.a),
            "b": _integer(curve.b),
            "n": _integer(curve.n),
            "cofactor": curve.cofactor,
            "generator": {"x": _integer(curve.gx), "y": _integer(curve.gy)},
            "j_invariant": _integer(
                ShortWeierstrassCurve(curve.p, curve.a, curve.b).j_invariant()
            ),
        },
        "frobenius": {
            "trace": _integer(trace),
            "discriminant": _integer(discriminant),
            "absolute_discriminant_prime_factors": [str(value) for value in factors],
            "prime_factor_certificates_verified": all(
                prove_prime(value) for value in factors
            ),
            "factorization_is_squarefree": len(set(factors)) == len(factors),
            "discriminant_is_fundamental": fundamental,
        },
        "endomorphism_orders": {
            "frobenius_order_conductor_in_maximal_order": 1,
            "possible_orders": [
                {
                    "name": "maximal order O_K = Z[pi]",
                    "discriminant": str(discriminant),
                    "conductor": 1,
                }
            ],
            "conclusion": (
                "Every curve in this F_p-isogeny class has the same maximal "
                "endomorphism order; there are no vertical volcano levels."
            ),
        },
        "exceptional_structure": {
            "j_0_in_class": False,
            "j_1728_in_class": False,
            "automorphism_conclusion": (
                "The CM field discriminant is neither -3 nor -4, so geometric "
                "automorphisms are only +1 and -1."
            ),
            "minimum_non_scalar_endomorphism_norm_lower_bound": _integer(
                non_scalar_norm_lower_bound
            ),
            "low_norm_conclusion": (
                "Any non-scalar endomorphism has degree at least ceil(|D_K|/4), "
                "which is too large to give a useful GLV-style map."
            ),
        },
        "small_rational_isogeny_degrees": {
            "prime_bound": isogeny_prime_bound,
            **degree_classes,
            "interpretation": (
                "Because the order is maximal, ramified primes give one horizontal "
                "direction, split primes give two, and inert primes give none."
            ),
        },
        "generic_ecdlp": {
            "pollard_rho_expected_steps_log2": math.log2(rho_steps_no_automorphism),
            "pollard_rho_with_negation_expected_steps_log2": math.log2(
                rho_steps_with_negation
            ),
            "note": (
                "These are group-operation estimates. The reference benchmark does "
                "not claim a production-optimized negation-map implementation."
            ),
        },
        "verification": checks,
        "search_conclusion": {
            "eliminated": [
                "alternative endomorphism-ring levels",
                "exceptional j-invariants 0 and 1728",
                "low-degree non-scalar endomorphisms",
                "Pohlig-Hellman variation within the class",
                "MOV embedding-degree variation within the class",
            ],
            "remaining": [
                "constant-factor arithmetic differences",
                "explicit low-cost horizontal paths from P-256",
                "a presently unknown non-generic ECDLP algorithm",
            ],
        },
    }
