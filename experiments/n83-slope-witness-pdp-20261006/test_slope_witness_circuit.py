#!/usr/bin/env python3
"""Exhaustive finite-target false-lift and regular-group controls over GF(2^5)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "n83-direct-point-pdp-20261006"))
sys.path.insert(0, str(HERE.parent / "pdp-scaling"))
sys.path.insert(0, str(HERE.parent / "hamming-ic-e2e-20260929"))
from gf2n import Curve, GF2n, Point, modulus  # noqa: E402
from run_n83_w34_sat_branch import parse_model, verify_model  # noqa: E402
from slope_witness_circuit import SlopeWitnessCircuit  # noqa: E402


SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def decode(wires: list[int], model: dict[int, bool]) -> int:
    return sum(1 << bit for bit, wire in enumerate(wires)
               if wire == -1 or (wire != 0 and model[wire]))


def solve(circuit, expected_sat: bool) -> dict[int, bool] | None:
    with tempfile.TemporaryDirectory(prefix="slope-witness-control-") as directory:
        path = Path(directory) / "case.xcnf"
        circuit.write(path)
        result = subprocess.run([str(SOLVER), "--threads=1", str(path)],
                                text=True, capture_output=True, timeout=15,
                                check=False)
    assert result.returncode in (10, 20), result.stderr
    model = parse_model(result.stdout)
    assert (model is not None) == expected_sat, result.stdout[-1000:]
    if model is not None:
        assert verify_model(circuit, model)
    return model


def main() -> None:
    assert SOLVER.is_file()
    n = 5
    mod = modulus(n)
    low_terms = [bit for bit in range(n) if mod & (1 << bit)]
    field = GF2n(n, mod)
    curve = Curve(field, 1)
    finite = {point for x in range(1 << n)
              for point in (curve.lift_x(x),) if point is not None}
    finite |= {curve.neg(point) for point in finite}
    nonzero = sorted((point for point in finite if point.x),
                     key=lambda point: (point.x, point.y))
    distinct = next((a, b) for a in nonzero for b in nonzero
                    if a.x != b.x and curve.add(a, b).x)
    x_pair = [point.x for point in distinct]
    reachable = {curve.add(a, b) for a in finite for b in finite
                 if a.x == x_pair[0] and b.x == x_pair[1]}
    assert len(reachable) == 4
    for target in sorted(finite, key=lambda point: (point.x, point.y)):
        builder = SlopeWitnessCircuit(n, low_terms)
        c = builder.circuit
        x_rows = [[c.variable() for _ in range(n)] for _ in x_pair]
        wires = builder.require_sum(x_rows, target.x, target.y)
        for value, row in zip(x_pair, x_rows):
            c.require_zero(c.add(row, c.constant(value)))
        model = solve(c, target in reachable)
        if model is None:
            continue
        points = [Point(decode(x, model), decode(y, model))
                  for x, y in wires["factors"]]
        assert all(curve.on_curve(point) and point.x for point in points)
        assert points[0].x != points[1].x
        assert curve.add(*points) == target
        expected_slope = field.mul(points[0].y ^ points[1].y,
                                   field.inv(points[0].x ^ points[1].x))
        assert decode(wires["slopes"][0], model) == expected_slope
        assert Point(*(decode(row, model) for row in
                       wires["prefixes_after_addition"][0])) == target

    # Equal-x addition is explicitly excluded, including both doubling and
    # a point plus its negative.  This is a coverage limit, not an UNSAT
    # claim for the complete group law.
    for target in sorted(finite, key=lambda point: (point.x, point.y)):
        builder = SlopeWitnessCircuit(n, low_terms)
        c = builder.circuit
        x_rows = [[c.variable() for _ in range(n)] for _ in range(2)]
        builder.require_sum(x_rows, target.x, target.y)
        for row in x_rows:
            c.require_zero(c.add(row, c.constant(x_pair[0])))
        solve(c, False)
    print("PASS: slope witness two-point exact group replay; "
          f"{len(reachable)} reachable and {len(finite) - len(reachable)} "
          f"unreachable finite targets; equal-x regular-locus guard")


if __name__ == "__main__":
    main()
