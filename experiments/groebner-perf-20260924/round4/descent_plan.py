"""Target-independent contraction layout for the existing Weil descent.

This caches field/ring structure, never target coefficients or answers. The
reference descend.py remains unchanged and is the independent equation oracle.
"""
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'pdp-scaling'))

from descend import GF2n, MulTable, block_polys, sumpoly


class DescentPlan:
    def __init__(self, n, mod, b, m, ell):
        if not (2 <= m <= 4 and 1 <= ell <= n and m*ell <= 20 and 0 <= b < 1 << n):
            raise ValueError('descent plan bounds: m 2..4, 1 <= ell <= n, m*ell <= 20')
        self.shape = n, mod, b, m, ell
        self._field = GF2n(n, mod)
        self._lock = threading.Lock()
        polynomial = sumpoly.load(m+1)[m+1]
        initial = sorted({tuple(mono[:m]) for mono in polynomial})
        indices = {key: i for i, key in enumerate(initial)}
        self._terms = tuple((indices[tuple(mono[:m])], mono[m], self._field.pow(b, mono[sumpoly.B]))
                            for mono in sorted(polynomial))
        self._exponents = tuple(sorted({e for _, e, _ in self._terms}))
        blocks = block_polys(self._field, ell, 2**(m-1))
        tables = [{mask: MulTable(self._field, coefficient) for mask, coefficient in block.items()}
                  for block in blocks]
        support = [(0, key) for key in initial]
        self._buffers = [[0]*len(support)]
        self._stages = []
        for i in range(m):
            following, stage = {}, []
            for source, (mask, rest) in enumerate(support):
                edges = []
                for bm, table in tables[rest[0]].items():
                    key = mask | (bm << (i*ell)), rest[1:]
                    if key not in following:
                        following[key] = len(following)
                    edges.append((following[key], table))
                stage.append((source, tuple(edges)))
            self._stages.append(tuple(stage))
            support = list(following)
            self._buffers.append([0]*len(support))
        self._masks = tuple(mask for mask, rest in support)

    def descend(self, x_target):
        if not isinstance(x_target, int) or not 0 <= x_target < 1 << self.shape[0]:
            raise ValueError('target coordinate outside the field')
        with self._lock:
            # Every reused slot is reset before coefficients of this target are
            # written. Nothing numerical is reused from the previous query.
            for buffer in self._buffers:
                for i in range(len(buffer)):
                    buffer[i] = 0
            powers = {e: self._field.pow(x_target, e) for e in self._exponents}
            for destination, exponent, fixed in self._terms:
                self._buffers[0][destination] ^= self._field.mul(powers[exponent], fixed)
            for i, stage in enumerate(self._stages):
                source, destination = self._buffers[i], self._buffers[i+1]
                for index, edges in stage:
                    value = source[index]
                    if value:
                        for target, table in edges:
                            destination[target] ^= table(value)
            return {mask: coefficient for mask, coefficient in zip(self._masks, self._buffers[-1]) if coefficient}
