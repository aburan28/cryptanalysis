"""Price ic-bench's exact operation counters in bitop/v1 (beside, never instead of, rps).

ic-bench meters ten counter classes (`pdp-degree-heuristics/opcount.py`).  Each is
mapped here to the bitop/v1 primitives (`tools/bitops.py`, `crypto:docs/units/
BITOPS.md`) over F_{2^n} that one increment performs, by reading what the
charged code does.  Where one increment can be one of several operations the
dearer one is charged, so the bitop total is an upper bound on the counted
work and never flatters IC.  Python bookkeeping (dicts, numpy index
arithmetic, factoring #E, the `instrument` phase) is not counted, exactly as
it is not counted in rps.

  class     one increment is (charged by)                         bitop/v1 primitives
  gf_mul    one F_2^n product or squaring (kernel.Field mul/sqr/   field_mul (a squaring is charged
            mul_const/mul_vec -> pdpkernel gf_mul)                 as a product: dearer)
  gf_inv    one F_2^n inversion (Field.inv)                        field_inv
  gf_lin    one F_2-linear map: trace, half-trace or sqrt          as_solve = n^2 AND + n(n-1) XOR
            (pdpkernel lin_apply on a precomputed table)           (n x n matrix times a vector)
  ec_add    one affine addition or doubling (pdpkernel ec_add;     group_add, binary affine
            ec_mul makes bitlen(k) + popcount(k) of them)          I + 2M + S + 9A (dearer than a
                                                                   doubling, I + 2M + 2S + 5A)
  ec_lift   one x -> y lift attempt (pdpkernel ec_lift_batch):     field_sqr + field_inv
            rhs = x + a2 + b / x^2; Tr(rhs); y = x * HT(rhs)       + 2 field_mul + 2 field_add
                                                                   + 2 as_solve (trace, half-trace);
                                                                   the successful path, the dearest
  modr_mul  one multiply-subtract mod r (monitor.RankTracker       modr_mul + modr_add (BITOPS
            elimination, normalisation, back substitution)         "row_op"; a plain product is
                                                                   charged as a multiply-subtract)
  modr_inv  one inversion mod r (Python pow(v, -1, r))             ceil(3 w / 2) modr_mul: Fermat
                                                                   v^(r-2) by square-and-multiply
                                                                   at BITOPS' 1.5 w-operation
                                                                   convention, w = bits(r)
  mac_op    one 64-bit word XOR of F_2 elimination, or one         word_op (64 gates)
            monomial insertion (macaulay, htsolver)
  anf_op    one word XOR or test of the Moebius transform /        word_op
            standard-monomial count
  sys_word  one 64-bit coefficient word sliced into a Boolean      word_op
            equation (descent.BooleanSystem)

The floor a total is divided by is sqrt(pi r / (2A)) * gates(group_add), with A
the automorphisms the curve offers: A = 2n on the Koblitz curves ic-bench runs
(negation and the n powers of the Frobenius tau).
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import bitops  # noqa: E402
import rho_reference  # noqa: E402

# Fixed primitives per increment; modr_inv depends on w and is added in `primitives`.
CLASS_PRIMITIVES: dict[str, dict[str, int]] = {
    "gf_mul": {"field_mul": 1},
    "gf_inv": {"field_inv": 1},
    "gf_lin": {"as_solve": 1},
    "ec_add": {"group_add": 1},
    "ec_lift": {"field_sqr": 1, "field_inv": 1, "field_mul": 2, "field_add": 2, "as_solve": 2},
    "modr_mul": {"modr_mul": 1, "modr_add": 1},
    "modr_inv": {},
    "mac_op": {"word_op": 1},
    "anf_op": {"word_op": 1},
    "sys_word": {"word_op": 1},
}


def modr_inv_products(r_bits: int) -> int:
    """modr_mul charged per inversion mod r: ceil(3 w / 2)."""
    return (3 * max(r_bits, 1) + 1) // 2


def primitives(counts: dict[str, int], r_bits: int) -> Counter:
    """bitop/v1 primitive counts for ic-bench class counts; an unmapped class raises."""
    missing = set(counts) - set(CLASS_PRIMITIVES)
    if missing:
        raise ValueError(f"no bitop/v1 mapping for {sorted(missing)}")
    out: Counter = Counter()
    for cls, k in counts.items():
        for prim, per in CLASS_PRIMITIVES[cls].items():
            out[prim] += k * per
        if cls == "modr_inv":
            out["modr_mul"] += k * modr_inv_products(r_bits)
    return +out


def bitops_of(counts: dict[str, int], n: int, r_bits: int) -> int:
    field = bitops.binary_field(n)
    return sum(k * bitops.gates(p, field, r_bits) for p, k in primitives(counts, r_bits).items())


def work_block(phase_counters: dict[str, dict[str, int]], per_target: list[dict[str, int]], n: int, r: int,
               automorphisms: int, complete: bool) -> dict:
    """The receipt's `work` block: totals, per phase and per target, and the ratio to the floor."""
    r_bits = r.bit_length()
    field = bitops.binary_field(n)
    totals: Counter = Counter()
    for c in phase_counters.values():
        totals.update(c)
    prims = primitives(totals, r_bits)
    total = sum(k * bitops.gates(p, field, r_bits) for p, k in prims.items())
    group_add = bitops.gates("group_add", field, r_bits)
    floor_ops = rho_reference.floor_group_operations(r, automorphisms)
    return {
        "unit": bitops.UNIT,
        "field": field,
        "r_bits": r_bits,
        "class_mapping": "experiments/ic-bench/bitop_work.py (CLASS_PRIMITIVES; modr_inv = ceil(3w/2) modr_mul)",
        "primitives": dict(sorted(prims.items())),
        "phase_bitops": {p: bitops_of(c, n, r_bits) for p, c in phase_counters.items()},
        "per_target_bitops": [bitops_of(c, n, r_bits) for c in per_target],
        # As total_operations: a total only for a complete verified DLP; otherwise a lower bound, not a cost.
        "bitops": total if complete else None,
        "log2_bitops": bitops.log2(total) if complete else None,
        "counted_bitops": total,
        "automorphisms": automorphisms,
        "group_add_bitops": group_add,
        "floor_group_operations": floor_ops,
        "floor_bitops": floor_ops * group_add,
        "floor_rule": "sqrt(pi r / (2A)) * gates(group_add), A = 2n (Koblitz: negation and Frobenius)",
        "ratio_to_floor": total / (floor_ops * group_add) if complete else None,
        "not_counted": "Python bookkeeping and the instrument phase; memory is not a gate",
    }
