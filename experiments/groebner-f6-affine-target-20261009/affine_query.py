"""Compile the affine target dependence of the last S3 factor once."""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'groebner-f6-boundary-compact-20261009'))
from compact_query import CompactContext, equations, s3, point_replay  # noqa: E402


class AffineEquations:
    """Build exact ANF rows using a small target-bit lookup, with no answer cache.

    In characteristic two, S3(a,b,t) = a²b² + (a²+b²)t² + abt + curve_b.
    Squaring and multiplication by a fixed field element are GF(2)-linear in
    t. Each ANF row is consequently an affine function of the bits of t.
    """

    def __init__(self, field, curve_b, auxiliary, summand):
        self.n = field.n
        if not 1 <= self.n <= 64:
            raise ValueError('unsupported target width')
        zero = equations(field, s3(field, curve_b, auxiliary, summand, {0: 0}))
        basis = [equations(field, s3(field, curve_b, auxiliary, summand,
                                     {0: 1 << bit}))
                 for bit in range(self.n)]
        universe = sorted({term for rows in [zero, *basis]
                           for row in rows for term in row})
        position = {term: bit for bit, term in enumerate(universe)}

        def encode(row):
            mask = 0
            for term in row:
                mask ^= 1 << position[term]
            return mask

        self.universe = tuple(universe)
        self.base = tuple(encode(row) for row in zero)
        deltas = [tuple(encode(row) ^ self.base[i]
                        for i, row in enumerate(rows)) for rows in basis]
        self.groups = []
        for offset in range(0, self.n, 4):
            width = min(4, self.n - offset)
            table = []
            for pattern in range(1 << width):
                table.append(tuple(
                    self._xor(deltas[offset + bit][i]
                              for bit in range(width) if pattern >> bit & 1)
                    for i in range(self.n)))
            self.groups.append((offset, (1 << width) - 1, tuple(table)))

    @staticmethod
    def _xor(values):
        value = 0
        for part in values:
            value ^= part
        return value

    def build(self, target_x):
        if not isinstance(target_x, int) or not 0 <= target_x < 1 << self.n:
            raise ValueError('target abscissa outside the field encoding')
        bits = list(self.base)
        for offset, mask, table in self.groups:
            change = table[(target_x >> offset) & mask]
            for row in range(self.n):
                bits[row] ^= change[row]
        result = []
        for row in bits:
            terms = []
            while row:
                bit = row & -row
                terms.append(self.universe[bit.bit_length() - 1])
                row ^= bit
            result.append(terms)
        return result


class AffineContext:
    def __init__(self, case, *, sanitized=False):
        start = time.perf_counter_ns()
        self.base = CompactContext(case, sanitized=sanitized)
        prepared = self.base.base.base
        self.template = AffineEquations(prepared.field, prepared.case['curve_b'],
                                        prepared.auxiliary, prepared.summand)
        self.setup_ns = time.perf_counter_ns() - start

    def run(self, target_x, arm):
        if arm == 'compact':
            return self.base.run(target_x, 'compact')
        if arm != 'affine':
            raise ValueError('unknown arm')
        start = time.perf_counter_ns()
        dynamic = self.template.build(target_x)
        built = time.perf_counter_ns()
        result = self.base.compact.run(dynamic)
        solved = time.perf_counter_ns()
        prepared = self.base.base.base
        verified = (point_replay(prepared.curve, result['assignment'],
                                 prepared.case['m'], prepared.case['ell'], target_x)
                    if result['assignment'] is not None else None)
        finished = time.perf_counter_ns()
        return dict(arm=arm, target_x=target_x, status=result['status'],
                    assignment=result['assignment'], point_verified=verified,
                    equation_verified=result['independently_verified'],
                    online_ns=finished - start, equations_ns=built - start,
                    solver_ns=solved - built, point_replay_ns=finished - solved,
                    solver=result, timing_eligible=False, qualified_speedup=None)

    def close(self):
        self.base.close()
