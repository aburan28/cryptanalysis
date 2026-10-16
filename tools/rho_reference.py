"""The Pollard-rho reference every IC comparison in this repository is divided by.

One module, so the binary harness (`experiments/ic-bench/bench.py`), the prime
bridge (`experiments/ic-bench/prime_bridge.py`) and the cross-regime table
(`experiments/ic-bench/cross_report.py`) cannot drift apart again.  All figures
are expected **group operations** (affine additions/doublings); a caller
converts them to its own unit (rps, bitop/v1) by multiplying by the price of one
group operation.

* `floor_group_operations(r, A)` -- sqrt(pi r / (2A)): rho on the r/A classes of
  a curve offering A automorphisms (A = 1: no folding; A = 2: negation;
  A = 2n on a Koblitz curve over F_{2^n}: negation and the n Frobenius powers).
* `single_target_group_operations(r)` -- the single-target expectation without
  equivalence classes, sqrt(pi r / 2) = floor_group_operations(r, 1).  The
  constant is sqrt(pi/2) = 1.2533..., not "about 1.3".
* `batch_group_operations(r, T, A, variant)` -- Kuhn-Struik distinguished-point
  rho solving T targets in turn, each walk able to end on an earlier target's
  trail:  sqrt(pi (r/A) / 2) * sum_{k<T} C(2k, k) / 4^k   (= the floor for T = 1),
  in one of two explicitly named variants:

    generous    no seeding, jump-table setup or detection lag: the series alone.
                The most favourable figure rho can be given.
    with_setup  the series plus T (2 smul + 1) for seeding each target's walk and
                32 smul for a 32-entry jump table, smul = scalar_mul_ops(r) =
                ceil(3 bits(r) / 2) additions.  This is what `ca-ic`'s
                `batch_rho_expected_ops` (suite/src/cryptanalysis/
                prime_orbit_index_calculus.rs) charges.

Two ratios IC / rho are comparable only when both use the same variant; every
consumer names the variant it used.

`scalar_mul_ops`: the Rust `scalar_mul_ops` is `(3 * bits).div_ceil(2)`, i.e.
ceil(3b/2); the Python form `(3 * b + 1) // 2` is the same integer for every
b >= 0 (3b even: both 3b/2; 3b odd: both (3b+1)/2), so the two already agree.
"""

from __future__ import annotations

import math

VARIANTS = ("generous", "with_setup")
JUMP_TABLE_ENTRIES = 32


def scalar_mul_ops(r: int) -> int:
    """Group operations charged for one scalar multiplication: ceil(1.5 * bits(r))."""
    return (3 * int(r).bit_length() + 1) // 2


def kuhn_struik_series(targets: int) -> float:
    """sum_{k < T} C(2k, k) / 4^k, accumulated exactly as every caller always has."""
    if targets < 1:
        raise ValueError("targets must be positive")
    coeff, series = 1.0, 0.0
    for k in range(targets):
        series += coeff
        coeff *= (2 * k + 1) / (2 * k + 2)
    return series


def floor_group_operations(r: int, automorphisms: int = 1) -> float:
    """sqrt(pi r / (2A)): expected rho group operations on the r/A automorphism classes."""
    if automorphisms < 1:
        raise ValueError("automorphisms must be positive")
    return math.sqrt(math.pi * r / (2 * automorphisms))


def single_target_group_operations(r: int) -> float:
    """sqrt(pi r / 2): one-target rho without equivalence classes."""
    return floor_group_operations(r, 1)


def setup_group_operations(r: int, targets: int) -> int:
    """The with_setup surcharge: T (2 smul + 1) seeding plus a 32-entry jump table."""
    s = scalar_mul_ops(r)
    return targets * (2 * s + 1) + JUMP_TABLE_ENTRIES * s


def batch_group_operations(r: int, targets: int, automorphisms: int = 1, variant: str = "generous") -> float:
    """Kuhn-Struik batch rho on r/A classes for T targets, in the named variant (unrounded)."""
    if variant not in VARIANTS:
        raise ValueError(f"unknown rho variant {variant!r}; use one of {VARIANTS}")
    if automorphisms < 1:
        raise ValueError("automorphisms must be positive")
    classes = r / automorphisms
    walk = math.sqrt(math.pi * classes / 2) * kuhn_struik_series(targets)
    if variant == "generous":
        return walk
    s = scalar_mul_ops(r)
    # Summed in this order so the float is bit-identical to ca-ic's and the old prime bridge's.
    return walk + targets * (2 * s + 1) + JUMP_TABLE_ENTRIES * s


def model(variant: str) -> str:
    """One-line description of a variant, for receipts and tables."""
    if variant == "generous":
        return ("Kuhn-Struik distinguished-point expectation sqrt(pi (r/A) / 2) sum_{k<T} C(2k,k)/4^k; "
                "variant generous: no seeding, jump-table setup or detection lag")
    if variant == "with_setup":
        return ("Kuhn-Struik distinguished-point expectation sqrt(pi (r/A) / 2) sum_{k<T} C(2k,k)/4^k; "
                "variant with_setup: + T (2 smul + 1) seeding + 32 smul jump table, smul = ceil(3 bits(r)/2)")
    raise ValueError(f"unknown rho variant {variant!r}")


def references(r: int, targets: int, automorphisms: int, unit_per_group_operation: int | float = 1) -> dict:
    """Every reference a receipt needs, under both variants, in the caller's unit (rounded group operations
    times the unit price, so integer prices give integer figures)."""
    out = {"automorphisms": automorphisms, "unit_per_group_operation": unit_per_group_operation,
           "floor_group_operations": round(floor_group_operations(r, automorphisms)),
           "variants": {}}
    for v in VARIANTS:
        single = round(batch_group_operations(r, 1, 1, v))
        out["variants"][v] = {
            "model": model(v),
            "single_target_operations": single * unit_per_group_operation,
            "independent_batch_operations": targets * single * unit_per_group_operation,
            "batch_operations": round(batch_group_operations(r, targets, 1, v)) * unit_per_group_operation,
            "folded_batch_operations": round(batch_group_operations(r, targets, automorphisms, v))
            * unit_per_group_operation,
        }
    return out
