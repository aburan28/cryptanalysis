"""Relation yield: verification of algebraic solutions, an independent point-sum oracle,
exact whole-subgroup yields, and the yield prediction.

Every Boolean solution (x_1, ..., x_m) in V^m is lifted to points and a sign pattern with
sum R is sought.  Outcomes per solution:

  verified       a proper decomposition R = +-P_1 +- ... +- P_m (no two summands cancel)
  improper       only decompositions with a cancelling pair (R itself in F_V, e.g. P - P + R)
  lift_rejected  some x_i does not lift, or no sign pattern sums to R

The oracle never looks at the equations: it tabulates sums of factor-base points, so its
agreement with the algebraic route checks the summation polynomial, the descent over an
arbitrary basis, the Moebius solution count and the lifting together.

Yield prediction.  Sums of factor-base points land in <G> + <psi(F)>, psi(P) = [r]P.  Treating
the r-component of an m-tuple sum as uniform on <G> gives, for a target R in <G>,

    E[#ordered decompositions of R] = T_psi / r,   T_psi = #{ordered m-tuples : sum psi = O} - Z,

where Z counts the tuples summing to O itself (|F| pairs (P, -P) for m = 2).  T_psi is exact
to compute from the psi classes; for psi-balanced bases T_psi ~ |F|^m / h.
The decomposition probability is predicted as 1 - exp(-E[#unordered]), E[#unordered] = T_psi / (r m!).
"""

from __future__ import annotations

import itertools
import math
from collections import Counter

import numpy as np

import kernel
from descent import assignment_to_xs
from factor_base import FactorBase

INF = kernel.INF_X


def _key_pairs(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    return np.stack([xs, ys], axis=1)


def classify_solution(fb: FactorBase, m: int, R: tuple[int, int], v: int) -> dict:
    K = fb.curve.K
    xs = assignment_to_xs(fb, m, v)
    pts = [K.lift(x) for x in xs]
    if any(p is None for p in pts):
        return {"xs": xs, "status": "lift_rejected"}
    improper = None
    for signs in itertools.product((1, -1), repeat=m):
        signed = [p if s == 1 else K.neg(p) for p, s in zip(pts, signs)]
        acc = (INF, 0)
        for p in signed:
            acc = K.add(acc, p)
        if acc != R:
            continue
        cancel = any(K.add(signed[i], signed[j])[0] == INF for i in range(m) for j in range(i))
        if not cancel:
            return {"xs": xs, "status": "verified", "points": signed}
        improper = improper or {"xs": xs, "status": "improper", "points": signed}
    return improper or {"xs": xs, "status": "lift_rejected"}


def relation_row(fb: FactorBase, points: list[tuple[int, int]]) -> dict[int, int]:
    """Column -> coefficient (mod r) of sum log(P_i) in the folded factor-base columns."""
    index = fb.point_index()
    r = fb.curve.r
    row: dict[int, int] = {}
    for p in points:
        i = index[p]
        if fb.col_of[i] < 0:
            continue
        j = int(fb.col_of[i])
        row[j] = (row.get(j, 0) + int(fb.col_coeff[i])) % r
    return {j: c for j, c in row.items() if c}


class Oracle:
    """Exact decomposition counts from sums of factor-base points (m = 2, 3)."""

    def __init__(self, fb: FactorBase, m: int, max_pairs: int = 3_000_000):
        if m not in (2, 3):
            raise ValueError("oracle implemented for m = 2, 3")
        self.fb, self.m = fb, m
        K = fb.curve.K
        F = len(fb.xs)
        if F * (F + 1) // 2 > max_pairs:
            raise ValueError("factor base too large for the pair table")
        sx, sy = K.pair_sums(fb.xs, fb.ys)
        i, j = np.triu_indices(F)
        mult = np.where(i == j, 1, 2)
        self.ordered_pairs: Counter = Counter()
        for x, y, w in zip(sx.tolist(), sy.tolist(), mult.tolist()):
            self.ordered_pairs[(x, y)] += w

    def ordered_count(self, R: tuple[int, int]) -> int:
        if self.m == 2:
            return self.ordered_pairs.get(R, 0)
        fb, K = self.fb, self.fb.curve.K
        tx, ty = K.sub_from(R, fb.xs, fb.ys)
        get = self.ordered_pairs.get
        return sum(get((x, y), 0) for x, y in zip(tx.tolist(), ty.tolist()))


def psi_tuple_count(fb: FactorBase, m: int) -> int:
    """T_psi: ordered m-tuples of factor-base points whose psi images sum to O."""
    c, K = fb.curve, fb.curve.K
    px, py = c.psi(fb.xs, fb.ys)
    classes = Counter(zip(px.tolist(), py.tolist()))
    keys = list(classes)
    if m == 1:
        return classes.get((INF, 0), 0)
    pair: Counter = Counter()
    for a in keys:
        for b in keys:
            pair[K.add(a, b)] += classes[a] * classes[b]
    if m == 2:
        return pair.get((INF, 0), 0)
    if m == 3:
        return sum(cnt * pair.get(K.neg(t), 0) for t, cnt in classes.items())
    raise ValueError("m <= 3")


def zero_sum_tuples(fb: FactorBase, m: int) -> int:
    """Ordered m-tuples of factor-base points summing to O (they decompose no target)."""
    F = len(fb.xs)
    if m == 2:
        return F  # (P, -P): F is closed under negation, and -T = T for the 2-torsion point
    if m == 3:
        K = fb.curve.K
        pts = set(zip(fb.xs.tolist(), fb.ys.tolist()))
        sx, sy = K.pair_sums(fb.xs, fb.ys)
        i, j = np.triu_indices(F)
        count = 0
        for x, y, a, b in zip(sx.tolist(), sy.tolist(), i.tolist(), j.tolist()):
            if x != INF and (x, x ^ y) in pts:
                count += 1 if a == b else 2
        return count
    raise ValueError("m <= 3")


def predicted_yield(fb: FactorBase, m: int) -> dict:
    r = fb.curve.r
    Z = zero_sum_tuples(fb, m)
    T = psi_tuple_count(fb, m) - Z
    F = len(fb.xs)
    e_ord = T / r
    e_unord = e_ord / math.factorial(m)
    basic = F**m / fb.curve.order
    return {
        "psi_tuples": T,
        "zero_sum_tuples": Z,
        "expected_ordered": e_ord,
        "expected_unordered": e_unord,
        "p_decomposable": 1 - math.exp(-e_unord),
        "basic_expected_ordered": basic,
    }


def exact_subgroup_yield(fb: FactorBase, m: int, max_tuples: int = 4_000_000) -> dict | None:
    """Exact P(decomposable) and E[#ordered decompositions] over all R in <G> - {O}."""
    c, K = fb.curve, fb.curve.K
    F = len(fb.xs)
    if F**m > max_tuples or m not in (2, 3):
        return None
    xs, ys = fb.xs, fb.ys

    def plus_all(ax: np.ndarray, ay: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Every P_a + (ax, ay)[k], as P_a - (-(ax, ay)[k])."""
        ox = np.empty(F * len(ax), dtype=np.uint64)
        oy = np.empty(F * len(ax), dtype=np.uint64)
        neg_y = np.where(ax == np.uint64(INF), np.uint64(0), ax ^ ay)
        for a in range(F):
            bx, by = K.sub_from((int(xs[a]), int(ys[a])), ax, neg_y)
            ox[a * len(ax) : (a + 1) * len(ax)], oy[a * len(ax) : (a + 1) * len(ax)] = bx, by
        return ox, oy

    sx, sy = plus_all(xs, ys)
    if m == 3:
        sx, sy = plus_all(sx, sy)
    # INF has x = ~0 and the kernel leaves y unspecified; normalize before counting
    fin = sx != np.uint64(INF)
    sx, sy = sx[fin], sy[fin]
    rx, _ = c.psi(sx, sy)
    ins = rx == np.uint64(INF)
    sx, sy = sx[ins], sy[ins]
    total_ordered = int(len(sx))
    distinct = int(len(np.unique(_key_pairs(sx, sy), axis=0))) if len(sx) else 0
    return {
        "targets": c.r - 1,
        "decomposable_targets": distinct,
        "p_decomposable": distinct / (c.r - 1),
        "expected_ordered": total_ordered / (c.r - 1),
    }
