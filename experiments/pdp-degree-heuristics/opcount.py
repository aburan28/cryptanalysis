"""Exclusive phase accounting: wall time plus deterministic operation counters.

A `Meter` owns one phase at a time.  While a phase is open, the module global `COUNTS`
is that phase's Counter, and the arithmetic entry points charge it:

  class        charged by                                    one unit is
  mac_op       macaulay.degree_scan (added by the caller)    one 64-bit word XOR in elimination
                                                             or one monomial insertion
  gf_mul       kernel.Field mul/sqr/mul_const/mul_vec        one F_2^n multiplication or squaring
  gf_inv       kernel.Field.inv                              one F_2^n inversion
  gf_lin       kernel.Field trace/half_trace/sqrt            one F_2-linear map application
  ec_add       kernel.Field add/smul/smul_batch/pair_sums/   one affine point addition or doubling
               sub_from                                      (ec_add calls in pdpkernel.c)
  ec_lift      kernel.Field.lift_batch                       one x -> y lift attempt
  sys_word     descent.BooleanSystem                         one 64-bit coefficient word sliced
                                                             into the n Boolean equations
  anf_op       BooleanSystem.solutions, kernel.count_standard one word XOR or test in the Moebius
                                                             transform / standard-monomial count
                                                             ((N + 2) 2^(N-1) per call); affine
                                                             systems: equations * N
  modr_mul     monitor.RankTracker                           one multiply-subtract mod r
  modr_inv     monitor.RankTracker                           one inversion mod r

The counts are exact functions of the inputs (ec_mul in pdpkernel.c performs
bitlen(k) + popcount(k) additions), so they do not depend on the host.  Python
bookkeeping (dicts, numpy index arithmetic, integer factoring of #E) is not counted;
it appears only in wall time.  Outside every phase `COUNTS` is None and nothing is charged.
"""

from __future__ import annotations

import time
from collections import Counter
from contextlib import contextmanager

CLASSES = ("mac_op", "anf_op", "sys_word", "gf_mul", "gf_inv", "gf_lin", "ec_add", "ec_lift", "modr_mul", "modr_inv")

COUNTS: Counter | None = None


def charge(cls: str, k: int = 1) -> None:
    if COUNTS is not None:
        COUNTS[cls] += k


def smul_cost(k: int) -> int:
    """ec_add calls made by the left-to-right double-and-add ec_mul for a scalar k >= 0."""
    return k.bit_length() + k.bit_count() if k > 0 else 0


class Meter:
    """Exclusive phases: wall_ns[phase] and ops[phase][class]."""

    def __init__(self):
        self.wall_ns: Counter = Counter()
        self.ops: dict[str, Counter] = {}
        self.active: str | None = None

    @contextmanager
    def phase(self, name: str):
        global COUNTS
        assert self.active is None, f"phase {name} opened inside {self.active}: phases are exclusive"
        self.active = name
        saved = COUNTS
        COUNTS = self.ops.setdefault(name, Counter())
        t0 = time.perf_counter_ns()
        try:
            yield COUNTS
        finally:
            self.wall_ns[name] += time.perf_counter_ns() - t0
            COUNTS = saved
            self.active = None

    def move(self, src: str, dst: str, ops: Counter, wall_ns: int) -> None:
        """Recharge work metered under `src` to `dst` (both closed)."""
        assert self.active is None
        self.ops[src].subtract(ops)
        self.ops[src] = +self.ops[src]
        self.ops.setdefault(dst, Counter()).update(ops)
        self.wall_ns[src] -= wall_ns
        self.wall_ns[dst] += wall_ns

    def class_totals(self, phases=None) -> Counter:
        out: Counter = Counter()
        for name, c in self.ops.items():
            if phases is None or name in phases:
                out.update(c)
        return out

    def priced(self, weights: dict[str, int]) -> dict[str, int]:
        """Integer cost of every phase under integer per-class weights."""
        missing = {cls for c in self.ops.values() for cls in c} - set(weights)
        if missing:
            raise ValueError(f"no calibration weight for {sorted(missing)}")
        return {name: sum(k * weights[cls] for cls, k in c.items()) for name, c in self.ops.items()}
