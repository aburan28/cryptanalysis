"""Exact regular-locus binary-curve sum circuit with affine slope witnesses.

Each factor y and each regular addition slope is a free witness constrained by
the curve/group equations.  There is no inversion or half-trace circuit.  The
nonzero-x and unequal-x clauses preserve the coverage boundary of the prior
direct-point pilot; a SAT model is still replayed in the independent group.
"""

from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "hamming-ic-e2e-20260929"))
sys.path.insert(0, str(HERE.parent / "pdp-scaling"))
from circuit import Circuit  # noqa: E402
from gf2n import GF2n  # noqa: E402


class SlopeWitnessCircuit:
    def __init__(self, degree: int, low_terms: list[int]):
        if degree < 3:
            raise ValueError("field degree must be at least three")
        self.field = GF2n(degree, (1 << degree) | sum(1 << bit for bit in low_terms))
        self.circuit = Circuit(degree, low_terms)

    def require_nonzero(self, wires: list[int]) -> None:
        if -1 in wires:
            return
        literals = [str(wire) for wire in wires if wire != 0]
        self.circuit.clauses.append(" ".join(literals + ["0"]))

    def lift_nonzero_x(self, x: list[int]) -> tuple[list[int], list[int]]:
        """Constrain a free y to y²+xy=x³+1 with x nonzero."""
        c = self.circuit
        self.require_nonzero(x)
        y = [c.variable() for _ in range(self.field.n)]
        lhs = c.add(c.square(y), c.mul(x, y))
        rhs = c.add(c.mul(c.square(x), x), c.constant(1))
        c.require_zero(c.add(lhs, rhs))
        return x, y

    def add_regular(self, left: tuple[list[int], list[int]],
                    right: tuple[list[int], list[int]]) -> \
            tuple[tuple[list[int], list[int]], list[int]]:
        """Constrain a free slope and return the exact regular affine sum."""
        c = self.circuit
        x_left, y_left = left
        x_right, y_right = right
        denominator = c.add(x_left, x_right)
        self.require_nonzero(denominator)
        slope = [c.variable() for _ in range(self.field.n)]
        c.require_zero(c.add(c.mul(slope, denominator), c.add(y_left, y_right)))
        x_sum = c.add(c.add(c.square(slope), slope), denominator)
        y_sum = c.add(c.add(c.mul(slope, c.add(x_left, x_sum)), x_sum), y_left)
        return (x_sum, y_sum), slope

    def require_sum(self, x_rows: list[list[int]], target_x: int,
                    target_y: int) -> dict:
        if len(x_rows) < 2 or any(len(row) != self.field.n for row in x_rows):
            raise ValueError("need at least two field-width factor x rows")
        c = self.circuit
        factors = [self.lift_nonzero_x(x) for x in x_rows]
        prefix = factors[0]
        intermediates = []
        slopes = []
        for factor in factors[1:]:
            prefix, slope = self.add_regular(prefix, factor)
            intermediates.append(prefix)
            slopes.append(slope)
        c.require_zero(c.add(prefix[0], c.constant(target_x)))
        c.require_zero(c.add(prefix[1], c.constant(target_y)))
        return {"factors": factors, "prefixes_after_addition": intermediates,
                "slopes": slopes}
