#!/usr/bin/env python3
"""Small-field SAT/group controls for the regular direct-point circuit."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from direct_point_circuit import DirectPointCircuit
from gf2n import Curve, GF2n, Point, modulus


SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def decode(wires: list[int], model: dict[int, bool]) -> int:
    def value(wire: int) -> bool:
        if wire == -1:
            return True
        if wire == 0:
            return False
        return model[wire]

    return sum(1 << bit for bit, wire in enumerate(wires) if value(wire))


def run_case(points: tuple[Point, Point], target: Point, expected_sat: bool,
             low_terms: list[int]) -> None:
    builder = DirectPointCircuit(5, low_terms)
    circuit = builder.circuit
    x_rows = [[circuit.variable() for _ in range(5)] for _ in points]
    signs = [circuit.variable() for _ in points]
    wires = builder.require_sum(x_rows, signs, target.x, target.y)
    for point, row in zip(points, x_rows):
        for bit, variable in enumerate(row):
            circuit.clauses.append(f"{variable if point.x & (1 << bit) else -variable} 0")
    with tempfile.TemporaryDirectory(prefix="direct-point-control-") as directory:
        path = Path(directory) / "case.xcnf"
        circuit.write(path)
        result = subprocess.run([str(SOLVER), "--threads=1", str(path)],
                                text=True, capture_output=True, timeout=15,
                                check=False)
    assert result.returncode in (10, 20), result.stderr
    sat = "s SATISFIABLE" in result.stdout
    unsat = "s UNSATISFIABLE" in result.stdout
    assert (sat, unsat) == (expected_sat, not expected_sat)
    if not sat:
        return
    model: dict[int, bool] = {}
    for line in result.stdout.splitlines():
        if line.startswith("v "):
            for word in line[2:].split():
                literal = int(word)
                if literal:
                    model[abs(literal)] = literal > 0
    field = builder.field
    curve = Curve(field, 1)
    decoded = [Point(decode(x, model), decode(y, model))
               for x, y in wires["factors"]]
    assert all(curve.on_curve(point) for point in decoded)
    assert all(point.x == source.x for point, source in zip(decoded, points))
    assert curve.sum(decoded) == target
    assert [Point(decode(x, model), decode(y, model))
            for x, y in wires["prefixes_after_addition"]] == [target]


def main() -> None:
    assert SOLVER.is_file()
    mod = modulus(5)
    low_terms = [bit for bit in range(5) if mod & (1 << bit)]
    field = GF2n(5, mod)
    curve = Curve(field, 1)
    rational = [curve.lift_x(x) for x in range(1, 1 << 5)]
    rational = [point for point in rational if point is not None]
    pair = next((a, b) for a in rational for b in rational
                if a.x != b.x and curve.add(a, b).x != 0)
    signs = [(a, b) for a in (pair[0], curve.neg(pair[0]))
             for b in (pair[1], curve.neg(pair[1]))]
    attainable = {curve.add(a, b) for a, b in signs}
    outside = next(point for point in rational if point not in attainable)
    for chosen in signs:
        target = curve.add(*chosen)
        assert not target.inf
        run_case(chosen, target, True, low_terms)
    run_case(pair, outside, False, low_terms)
    print(f"PASS: four sign-combination SAT group replays and one UNSAT false-lift control over GF(2^5)")


if __name__ == "__main__":
    main()
