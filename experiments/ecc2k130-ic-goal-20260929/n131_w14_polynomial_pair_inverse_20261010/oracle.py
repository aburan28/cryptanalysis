"""Exact polynomial-W14 pair-output inverse over the ECC2K-130 field."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPLAY = ROOT.parent / "crypto/research/sat_factor_base_review_20260908/autolab_orbit_extract_20260924"
sys.path.insert(0, str(REPLAY))
from independent_replay import Curve, Field, half_trace, points_with_x  # noqa: E402

N = 131
D = 14
DOMAIN = 1 << D
LOW_TERMS = [0, 1, 2, 13]


def coordinate(basis, mask):
    value = 0
    for i, item in enumerate(basis):
        if mask >> i & 1:
            value ^= item
    return value


def echelon(columns):
    pivots = {}
    kernel = []
    for i, column in enumerate(columns):
        value, code = column, 1 << i
        while value:
            bit = value.bit_length() - 1
            if bit not in pivots:
                pivots[bit] = (value, code)
                break
            pivot, combo = pivots[bit]
            value ^= pivot
            code ^= combo
        else:
            kernel.append(code)
    return pivots, kernel


def solve(pivots, value):
    code = 0
    while value:
        bit = value.bit_length() - 1
        if bit not in pivots:
            return None
        pivot, combo = pivots[bit]
        value ^= pivot
        code ^= combo
    return code


def affine_solutions(particular, kernel):
    for choice in range(1 << len(kernel)):
        code = particular
        for i, vector in enumerate(kernel):
            if choice >> i & 1:
                code ^= vector
        yield code


class PairOracle:
    def __init__(self, columns):
        self.field = Field(N, LOW_TERMS)
        self.curve = Curve(self.field, 0)
        self.columns = dict(columns)
        self.valid = set(columns)
        self.basis_w = [1 << i for i in range(1, D + 1)]
        self.basis_u = [half_trace(self.field, w) for w in self.basis_w]
        if any(self.field.mul(u, u) ^ u != w
               for u, w in zip(self.basis_u, self.basis_w)):
            raise ValueError("W14 basis lost Artin-Schreier lift")
        self.squared_u = [self.field.mul(u, u) for u in self.basis_u]
        self.product_basis = [1 << degree for degree in range(2, 2*D + 1)]
        self.product_rank = len(echelon(self.product_basis)[0])
        if self.product_rank != 2*D - 1:
            raise ValueError("W14 polynomial product span is not dimension 27")

    def u_of_mask(self, mask):
        return coordinate(self.basis_u, mask)

    def point_options(self, mask):
        if mask not in self.valid:
            raise ValueError("mask is outside rational W14 support")
        u = self.u_of_mask(mask)
        return points_with_x(self.curve, 1 ^ self.field.inv(u))

    def phi_of(self, point):
        if point is None or point[0] in (0, 1):
            return None
        return self.field.inv(point[0] ^ 1)

    def fixed_sum(self, s, product):
        if s <= 0 or s >= DOMAIN:
            return []
        field = self.field
        w_s = coordinate(self.basis_w, s)
        columns = [field.mul(w, w) ^ field.mul(w_s, w)
                   for w in self.basis_w]
        pivots, kernel = echelon(columns)
        particular = solve(pivots, product)
        if particular is None:
            return []
        pairs = set()
        for a in affine_solutions(particular, kernel):
            b = a ^ s
            if (a in self.valid and b in self.valid and a != b and
                    self.columns[a] != self.columns[b]):
                pairs.add(tuple(sorted((a, b))))
        return sorted(pairs)

    def joint(self, z):
        field = self.field
        if z in (0, 1):
            return [], {"status": "EXCEPTIONAL", "rank": None,
                        "seed_sum": None}
        z2 = field.mul(z, z)
        az = z2 ^ z
        columns = self.squared_u + [field.mul(az, product)
                                    for product in self.product_basis]
        pivots, kernel = echelon(columns)
        rank = len(pivots)
        if rank < D + len(self.product_basis):
            return self.full_scan(z), {"status": "RANK_FALLBACK",
                                        "rank": rank, "nullity": len(kernel),
                                        "seed_sum": None}
        coefficients = solve(pivots, z2)
        if coefficients is None:
            return [], {"status": "SPAN_REJECT", "rank": rank,
                        "seed_sum": None}
        s = coefficients & (DOMAIN - 1)
        if s == 0:
            return [], {"status": "ZERO_SUM_REJECT", "rank": rank,
                        "seed_sum": 0}
        product = field.mul(coordinate(self.squared_u, s) ^ z2,
                            field.inv(az))
        pairs = self.fixed_sum(s, product)
        return pairs, {"status": "PAIR" if pairs else "FIXED_SUM_REJECT",
                       "rank": rank, "seed_sum": s}

    def full_scan(self, z):
        if z in (0, 1):
            return []
        field = self.field
        z2 = field.mul(z, z)
        inverse_az = field.inv(z2 ^ z)
        pairs = set()
        for s in range(1, DOMAIN):
            product = field.mul(coordinate(self.squared_u, s) ^ z2,
                                inverse_az)
            pairs.update(self.fixed_sum(s, product))
        return sorted(pairs)


def load_support(path):
    columns = {}
    with Path(path).open() as rows:
        for row in rows:
            mask, canonical = map(int, row.split())
            columns[mask] = canonical
    if len(columns) != 8220 or len(set(columns.values())) != 8160:
        raise ValueError("W14 support cardinalities changed")
    return columns
