"""Exact reciprocal-coordinate inverse for two W14 diagonal atoms."""

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ORACLE_DIR = BASE / "n131_w14_polynomial_pair_inverse_20261010"
sys.path.insert(0, str(ORACLE_DIR))
import oracle as prior  # noqa: E402

N = 131
D = 14
DOMAIN = 1 << D
SUPPORT = BASE / "n131_w14_ten_source_gate_20261009/support_w14.tsv"


def support_columns():
    rows = [tuple(map(int, line.split())) for line in SUPPORT.read_text().splitlines()]
    if len(rows) != 8220 or len({mask for mask, _ in rows}) != 8220:
        raise ValueError("W14 source support changed")
    return dict(rows)


class DiagonalPairInverse:
    def __init__(self, columns=None):
        self.columns = support_columns() if columns is None else columns
        self.raw = prior.PairOracle(self.columns)
        self.field = self.raw.field
        self.curve = self.raw.curve
        self.basis_w = self.raw.basis_w
        self.basis_s2 = [self.field.mul(w, w) for w in self.basis_w]
        self.basis_product = [1 << d for d in range(2, 29)]
        if len(prior.echelon(self.basis_product)[0]) != 27:
            raise AssertionError("W14 product span changed")

    def atom(self, mask):
        point = self.raw.point_options(mask)[0]
        f = self.field
        frobenius = (f.mul(point[0], point[0]), f.mul(point[1], point[1]))
        atom = self.curve.add(point, frobenius)
        if atom is None or atom[0] != f.inv(prior.coordinate(self.basis_w, mask)):
            raise AssertionError("diagonal-atom reciprocal identity failed")
        return atom

    def pair_outputs(self, a, b):
        if a == b or self.columns[a] == self.columns[b]:
            return []
        left, right = self.atom(a), self.atom(b)
        values = set()
        for point in (self.curve.add(left, right),
                      self.curve.add(left, self.curve.neg(right))):
            if point is not None and point[0] != 0:
                values.add(self.field.inv(point[0]))
        return sorted(values)

    def fixed_sum(self, s, product, z):
        matches = []
        for pair in self.raw.fixed_sum(s, product):
            if z in self.pair_outputs(*pair):
                matches.append(pair)
        return matches

    def exhaustive(self, z):
        if z == 0:
            return []
        f = self.field
        z_inverse = f.inv(z)
        z2 = f.mul(z, z)
        matches = set()
        for s in range(1, DOMAIN):
            rhs = f.mul(prior.coordinate(self.basis_w, s),
                        prior.coordinate(self.basis_w, s)) ^ z2
            # Trace(rhs)=0 is necessary for v^2+v=rhs, with v=z*p.
            v = prior.half_trace(f, rhs)
            if f.mul(v, v) ^ v != rhs:
                continue
            for choice in (v, v ^ 1):
                p = f.mul(choice, z_inverse)
                matches.update(self.fixed_sum(s, p, z))
        return sorted(matches)

    def joint(self, z):
        if z == 0:
            return [], {"status": "EXCEPTIONAL", "rank": None,
                        "seed_sum": None}
        f = self.field
        z2 = f.mul(z, z)
        columns = self.basis_s2 + [f.mul(z, p) ^ f.mul(z2, f.mul(p, p))
                                   for p in self.basis_product]
        pivots, kernel = prior.echelon(columns)
        rank = len(pivots)
        code = prior.solve(pivots, z2)
        if code is None:
            return [], {"status": "SPAN_REJECT", "rank": rank,
                        "seed_sum": None}
        if kernel:
            pairs = self.exhaustive(z)
            return pairs, {"status": "RANK_FALLBACK", "rank": rank,
                           "nullity": len(kernel), "seed_sum": None}
        s = code & (DOMAIN-1)
        if s == 0:
            return [], {"status": "ZERO_SUM_REJECT", "rank": rank,
                        "seed_sum": 0}
        product = 0
        for i, value in enumerate(self.basis_product):
            if code >> (D+i) & 1:
                product ^= value
        pairs = self.fixed_sum(s, product, z)
        return pairs, {"status": "PAIR" if pairs else "FIXED_SUM_REJECT",
                       "rank": rank, "seed_sum": s, "product": product}
