#!/usr/bin/env python3
"""Exhaustive small-field selector and regular two-point replay controls."""

from __future__ import annotations

import itertools
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "n83-direct-point-pdp-20261006"))
from direct_point_circuit import DirectPointCircuit  # noqa: E402
from gf2n import Curve, GF2n, Point, modulus  # noqa: E402
from run_n83_w34_sat_branch import parse_model, verify_model  # noqa: E402
from indexed_factor import decode_positions, factor, pin_positions  # noqa: E402


SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def rank(values: list[int]) -> int:
    pivots = {}
    for item in values:
        while item:
            place = item.bit_length() - 1
            if place not in pivots:
                pivots[place] = item
                break
            item ^= pivots[place]
    return len(pivots)


def solve(circuit, expected_sat: bool) -> dict[int, bool] | None:
    with tempfile.TemporaryDirectory(prefix="indexed-factor-control-") as directory:
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


def pin_raw_codes(circuit, encoded: dict, values: list[int]) -> None:
    for position, value in zip(encoded["positions"], values):
        for place, bit in enumerate(position["bits"]):
            circuit.clauses.append(f"{bit if value & (1 << place) else -bit} 0")


def main() -> None:
    assert SOLVER.is_file()
    n = 5
    mod = modulus(n)
    low_terms = [bit for bit in range(n) if mod & (1 << bit)]
    field = GF2n(n, mod)
    curve = Curve(field, 1)
    normal = next(a for a in range(1, 1 << n)
                  if rank([field.frob(a, i) for i in range(n)]) == n)
    conjugates = [field.frob(normal, i) for i in range(n)]
    masks = [list(items) for weight in (3, 4)
             for items in itertools.combinations(range(n), weight)]
    assert len(masks) == 15

    # Every valid mask has exactly one ordered positional witness.
    for mask in masks:
        builder = DirectPointCircuit(n, low_terms)
        encoded = factor(builder.circuit, conjugates)
        pin_positions(builder.circuit, encoded, mask)
        x = 0
        for index in mask:
            x ^= conjugates[index]
        builder.circuit.require_zero(builder.circuit.add(encoded["x"],
                                                         builder.circuit.constant(x)))
        model = solve(builder.circuit, True)
        assert model is not None and decode_positions(model, encoded) == mask

    for values in ([0, 0, 1, 2], [1, 0, 2, 3],
                   [0, 1, 2, n + 1], [n, 1, 2, 3]):
        builder = DirectPointCircuit(n, low_terms)
        encoded = factor(builder.circuit, conjugates)
        pin_raw_codes(builder.circuit, encoded, values)
        solve(builder.circuit, False)

    rational = []
    for mask in masks:
        x = 0
        for index in mask:
            x ^= conjugates[index]
        point = curve.lift_x(x)
        if point is not None:
            rational.append((mask, point))
    (left_mask, left), (right_mask, right) = next(
        ((a, p), (b, q)) for a, p in rational for b, q in rational
        if p.x != q.x and not curve.add(p, q).inf)
    reachable = {curve.add(a, b)
                 for a in (left, curve.neg(left))
                 for b in (right, curve.neg(right))}
    all_finite = {point for x in range(1 << n)
                  for point in (curve.lift_x(x),) if point is not None}
    all_finite |= {curve.neg(point) for point in all_finite}
    assert reachable <= all_finite
    for target in sorted(all_finite, key=lambda point: (point.x, point.y)):
        builder = DirectPointCircuit(n, low_terms)
        encoded = [factor(builder.circuit, conjugates) for _ in range(2)]
        for item, mask in zip(encoded, (left_mask, right_mask)):
            pin_positions(builder.circuit, item, mask)
        signs = [builder.circuit.variable() for _ in range(2)]
        builder.require_sum([item["x"] for item in encoded], signs,
                            target.x, target.y)
        model = solve(builder.circuit, target in reachable)
        if model is None:
            continue
        assert [decode_positions(model, item) for item in encoded] == \
            [left_mask, right_mask]
        actual = []
        for source, sign in zip((left, right), signs):
            actual.append(curve.neg(source) if model[sign] else source)
        assert curve.sum(actual) == target
    print("PASS: 15 exact W3/W4 selector masks, four rejected invalid codes, "
          f"and {len(reachable)}/{len(all_finite)} finite two-point targets")


if __name__ == "__main__":
    main()
