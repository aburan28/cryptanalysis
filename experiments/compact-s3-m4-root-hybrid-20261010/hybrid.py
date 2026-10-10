"""Balanced four-leaf S3 system with selected exact external pair links."""

from __future__ import annotations

from collections import Counter
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "experiments/compact-s3-m4-20261003"
sys.path.insert(0, str(OLD))

from chain_s3 import Formula, field, multiplication_table, square_destinations  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from chain_s3_multitarget import choose_target_x  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def build_hybrid(n, weight, raw_target_xs, deferred_pairs=(0,)):
    """Retain four leaves and the outer link; defer selected inner links."""
    assert set(deferred_pairs) <= {0, 1}
    onb = field.Onb(n)
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    mids = [[formula.new() for _ in range(n)] for _ in range(2)]
    for leaf in leaves:
        formula.at_most(leaf, weight)
        formula.clauses.append(leaf[:])
    target, selector = choose_target_x(formula, n, raw_target_xs)
    if 0 not in deferred_pairs:
        s3_link_factored(formula, leaves[0], leaves[1], mids[0], table,
                         destinations)
    if 1 not in deferred_pairs:
        s3_link_factored(formula, leaves[2], leaves[3], mids[1], table,
                         destinations)
    s3_link_factored(formula, mids[0], mids[1], target, table,
                     destinations)
    return formula, leaves, mids, target, selector


def bits_value(bits, model):
    return sum(1 << i for i, bit in enumerate(bits) if model[bit])


class MeteredField:
    """Count public field API calls in one exact S3 root oracle invocation."""

    COUNTED = frozenset(("mul", "sqr", "inv", "trace", "frob", "add",
                         "fromCoords", "toCoords", "one"))

    def __init__(self, onb):
        self.inner = onb
        self.calls = Counter()
        self.m = onb.m

    def __getattr__(self, name):
        attr = getattr(self.inner, name)
        if name not in self.COUNTED or not callable(attr):
            return attr

        def counted(*args, **kwargs):
            self.calls[name] += 1
            return attr(*args, **kwargs)

        return counted


def exact_roots(metered, left_x, right_x):
    a = metered.fromCoords(left_x)
    b = metered.fromCoords(right_x)
    return tuple(metered.toCoords(root) for root in s3_roots(metered, a, b))


def root_lemma(left, right, mid, left_x, right_x, roots, branch=None):
    """CNF equivalent to pair-match => mid is one of the exact roots.

    `branch` is a fresh variable if and only if there are two roots. DIMACS
    literals in `mismatch` are false exactly on this leaf-pair assignment.
    """
    n = len(left)
    assert len(right) == len(mid) == n
    assert 0 < left_x < 1 << n and 0 < right_x < 1 << n
    assert len(set(roots)) == len(roots) <= 2
    assert all(0 <= value < 1 << n for value in roots)
    mismatch = [(-bit if left_x >> i & 1 else bit)
                for i, bit in enumerate(left)]
    mismatch += [(-bit if right_x >> i & 1 else bit)
                 for i, bit in enumerate(right)]
    if not roots:
        assert branch is None
        return [mismatch]
    if len(roots) == 1:
        assert branch is None
        return [mismatch + [bit if roots[0] >> i & 1 else -bit]
                for i, bit in enumerate(mid)]
    assert branch is not None
    rows = []
    for i, bit in enumerate(mid):
        value0 = bool(roots[0] >> i & 1)
        value1 = bool(roots[1] >> i & 1)
        if value0 == value1:
            rows.append(mismatch + [bit if value0 else -bit])
        else:
            rows.append(mismatch + [branch, bit if value0 else -bit])
            rows.append(mismatch + [-branch, bit if value1 else -bit])
    return rows


def check_clauses(clauses, model):
    return all(any(model[abs(lit)] == (lit > 0) for lit in clause)
               for clause in clauses)
