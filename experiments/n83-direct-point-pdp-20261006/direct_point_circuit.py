"""Deterministic regular-locus point-sum XCNF over odd-degree binary fields.

The only witness choices are factor x coordinates and one lift-sign bit per
factor. Inverses, half-traces, y coordinates, and intermediate sums are
functions of those choices. This circuit intentionally excludes x=0 factors
and equal-x affine addition steps; callers must record that coverage limit.
"""

from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "hamming-ic-e2e-20260929"))
sys.path.insert(0, str(HERE.parent / "pdp-scaling"))
from circuit import Circuit  # noqa: E402
from gf2n import GF2n  # noqa: E402


class DirectPointCircuit:
    def __init__(self, degree: int, low_terms: list[int]):
        if degree < 3 or degree % 2 != 1:
            raise ValueError("half-trace circuit requires odd degree >= 3")
        self.field = GF2n(degree, (1 << degree) | sum(1 << bit for bit in low_terms))
        self.circuit = Circuit(degree, low_terms)
        self.frobenius_images: dict[int, list[int]] = {}
        self.half_trace_images = [self.field.half_trace(1 << bit)
                                  for bit in range(degree)]

    def frobenius(self, wires: list[int], power: int) -> list[int]:
        if power == 0:
            return wires
        if power not in self.frobenius_images:
            self.frobenius_images[power] = [
                self.field.frob(1 << bit, power)
                for bit in range(self.field.n)
            ]
        return self.circuit.linear_element(wires, self.frobenius_images[power])

    def require_nonzero(self, wires: list[int]) -> None:
        if -1 in wires:
            return
        literals = [str(wire) for wire in wires if wire != 0]
        self.circuit.clauses.append(" ".join(literals + ["0"]))

    def inverse(self, wires: list[int]) -> list[int]:
        """Compute a^(2^n-2) with an addition chain for 2^(n-1)-1."""
        c = self.circuit
        degree = self.field.n
        target = degree - 1
        powers = {1: wires}
        length = 1
        while 2 * length <= target:
            current = powers[length]
            powers[2 * length] = c.mul(self.frobenius(current, length), current)
            length *= 2
        chosen = length
        result = powers[length]
        for bit in sorted((value for value in powers if target & value and value != length),
                          reverse=True):
            result = c.mul(self.frobenius(result, bit), powers[bit])
            chosen += bit
        assert chosen == target
        return self.frobenius(result, 1)

    def lift_nonzero_x(self, x: list[int], sign: int) -> tuple[list[int], list[int]]:
        """Enforce y^2+xy=x^3+1 and return the selected rational lift."""
        c = self.circuit
        self.require_nonzero(x)
        inverse_x = self.inverse(x)
        w = c.add(x, self.frobenius(inverse_x, 1))
        v = c.linear_element(w, self.half_trace_images)
        v = c.add(v, [sign] + [0] * (self.field.n - 1))
        c.require_zero(c.add(c.add(self.frobenius(v, 1), v), w))
        return x, c.mul(x, v)

    def add_regular(self, left: tuple[list[int], list[int]],
                    right: tuple[list[int], list[int]]) -> tuple[list[int], list[int]]:
        """Affine binary-curve sum for x_left != x_right, excluding identity."""
        c = self.circuit
        x_left, y_left = left
        x_right, y_right = right
        denominator = c.add(x_left, x_right)
        self.require_nonzero(denominator)
        slope = c.mul(c.add(y_left, y_right), self.inverse(denominator))
        x_sum = c.add(c.add(self.frobenius(slope, 1), slope), denominator)
        y_sum = c.add(c.add(c.mul(slope, c.add(x_left, x_sum)), x_sum), y_left)
        return x_sum, y_sum

    def require_sum(self, x_rows: list[list[int]], sign_wires: list[int],
                    target_x: int, target_y: int) -> dict:
        if len(x_rows) != len(sign_wires) or len(x_rows) < 2:
            raise ValueError("one sign bit per factor, at least two factors")
        c = self.circuit
        factors = [self.lift_nonzero_x(x, sign)
                   for x, sign in zip(x_rows, sign_wires)]
        prefix = factors[0]
        intermediates = []
        for factor in factors[1:]:
            prefix = self.add_regular(prefix, factor)
            intermediates.append(prefix)
        c.require_zero(c.add(prefix[0], c.constant(target_x)))
        c.require_zero(c.add(prefix[1], c.constant(target_y)))
        return {"factors": factors, "prefixes_after_addition": intermediates}
