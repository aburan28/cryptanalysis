#!/usr/bin/env python3
"""Independently replay axis-factorized terms on a disjoint scalar panel."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

import axis
import holdout
from screen import load, sha

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
NATIVE = EXP / "prime-j0-secp256k1-native"


def affine_add(left, right):
    """Separate affine group law for accumulating fixture-independent terms."""
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1+y2) % holdout.P == 0:
        return None
    if x1 == x2:
        slope = 3*x1*x1*pow(2*y1, -1, holdout.P) % holdout.P
    else:
        slope = (y2-y1)*pow((x2-x1) % holdout.P, -1, holdout.P) % holdout.P
    x3 = (slope*slope-x1-x2) % holdout.P
    y3 = (slope*(x1-x3)-y1) % holdout.P
    assert y3*y3 % holdout.P == (x3*x3*x3+7) % holdout.P
    return x3, y3


def recode(pair, base, orbit):
    a, b = pair
    factor = 1
    rebuilt = [0, 0]
    selected = []
    for window in range(13):
        residue = a % base, b % base
        canonical = min((x % base, y % base)
                        for x, y in orbit.unit_images(residue))
        seed = orbit.nearest_digit(canonical, base)
        images = orbit.unit_images(seed)
        code = next(code for code, (x, y) in enumerate(images)
                    if (x % base, y % base) == residue)
        da, db = images[code]
        assert (a-da) % base == (b-db) % base == 0
        assert 3*axis.norm((da, db)) <= base*base
        rebuilt[0] += factor*da
        rebuilt[1] += factor*db
        if da or db:
            selected.append((window, (da, db), code))
        a, b = (a-da)//base, (b-db)//base
        factor *= base
    rebuilt[0] += factor*a
    rebuilt[1] += factor*b
    assert tuple(rebuilt) == pair
    return selected, (a, b)


def run() -> tuple[dict, bytes]:
    fixture = json.loads((HERE / "holdout.json").read_text())
    assert fixture["schema"] == 1 and fixture["seed"] == 20261012417
    assert fixture["generator_sha256"] == sha(HERE / "holdout.py")
    cases = fixture["cases"]
    assert len(cases) == 512
    scalars = [int(case["scalar_hex"], 16) for case in cases]
    assert len(set(scalars)) == len(scalars)
    assert sha256(b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest() == \
        fixture["scalar_sha256"]
    for name, digest in fixture["disjoint_prior_panels_sha256"].items():
        path = EXP / name
        assert sha(path) == digest
        prior = json.loads(path.read_text())
        values = prior.get("scalars_hex")
        if values is None:
            values = [case["scalar_hex"] for case in prior["cases"]]
        assert set(scalars).isdisjoint(int(value, 16) % holdout.ORDER for value in values)
    design = json.loads((HERE / "design.json").read_text())
    assert sha(EXP / "prime-j0-sector-digit-20261010/fresh-inputs.json") == \
        design["frozen_design_sha256"]

    sys.path.insert(0, str(NATIVE.resolve()))
    orbit = load("axis416_holdout_orbit", NATIVE / "unit_orbit_windows_screen.py")
    old = load("axis416_holdout_reference", NATIVE / "radix943_screen.py")
    totals = Counter()
    rows = []
    point_lines = []
    for index, case in enumerate(cases):
        scalar = scalars[index]
        assert 0 <= scalar < holdout.ORDER
        expected = None if case["expected_identity"] else (
            int(case["expected_x_hex"], 16), int(case["expected_y_hex"], 16))
        representative = old.nearest_representative(scalar)
        assert 3*axis.norm(representative) <= holdout.ORDER
        assert (representative[0]+old.LAMBDA_TAU*representative[1]-scalar) % holdout.ORDER == 0
        selected, terminal = recode(representative, axis.BASE, orbit)
        assert 3*axis.norm(terminal) <= axis.CAP
        code, u, b = axis.factor(terminal)
        if terminal != (0, 0):
            first = axis.images((-u, 0))[code]
            second = axis.images((0, b))[code]
            assert (first[0]+second[0], first[1]+second[1]) == terminal
            selected.extend(((13, first, code), (13, second, code)))
        control, control_top = recode(representative, 569, orbit)
        assert 3*axis.norm(control_top) <= 270_666
        control_terms = len(control) + (control_top != (0, 0))

        point = None
        scalar_sum = 0
        for power, (da, db), _ in selected:
            weight = pow(axis.BASE, power, holdout.ORDER)
            term_scalar = (da+old.LAMBDA_TAU*db)*weight % holdout.ORDER
            scalar_sum = (scalar_sum+term_scalar) % holdout.ORDER
            point = affine_add(point, holdout.multiply(term_scalar))
        assert scalar_sum == scalar
        assert point == expected, (index, point, expected)
        point_lines.append("identity" if point is None else
                           f"{point[0]:064x}:{point[1]:064x}")
        totals.update(cases=1, group_points_verified=1,
                      axis_terms=len(selected), control569_terms=control_terms,
                      terminal_nonzero=int(terminal != (0, 0)))
        rows.append({"index": index,
                     "scalar_sha256": sha256(scalar.to_bytes(32, "big")).hexdigest(),
                     "terminal": list(terminal), "sector_code": code,
                     "axis_u": u, "axis_b": b,
                     "selected_terms": len(selected),
                     "control569_terms": control_terms,
                     "point": point_lines[-1], "verified": True})
    row_bytes = ("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":"))
                           for row in rows) + "\n").encode()
    return {
        "schema": 1, "status": "independent_axis_group_point_replay",
        "curve": "secp256k1", "radix": axis.BASE,
        "cases": len(cases), "totals": dict(sorted(totals.items())),
        "point_digest": sha256("\n".join(point_lines).encode()).hexdigest(),
        "rows_sha256": sha256(row_bytes).hexdigest(),
        "holdout_sha256": sha(HERE / "holdout.json"),
        "design_commit": "bbda8011a",
        "design_sha256": sha(HERE / "design.json"),
        "replay_source_sha256": sha(Path(__file__)),
        "independent_group_source_sha256": sha(HERE / "holdout.py"),
    }, row_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt, rows = run()
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        for name in ("holdout-replay.json", "holdout-rows.jsonl"):
            if (HERE / name).exists():
                raise SystemExit(f"{name} exists; use --check")
        (HERE / "holdout-replay.json").write_bytes(payload)
        (HERE / "holdout-rows.jsonl").write_bytes(rows)
    elif (HERE / "holdout-replay.json").read_bytes() != payload or \
            (HERE / "holdout-rows.jsonl").read_bytes() != rows:
        raise SystemExit("holdout replay differs from frozen sources or inputs")
    print(json.dumps({"cases": receipt["cases"],
                      "totals": receipt["totals"]}, sort_keys=True))


if __name__ == "__main__":
    main()
