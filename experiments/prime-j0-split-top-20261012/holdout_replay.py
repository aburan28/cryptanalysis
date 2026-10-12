#!/usr/bin/env python3
"""Replay the frozen split-top holdout through independent curve addition."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXP / "prime-j0-secp256k1-native"))
import holdout
import screen


def affine_add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % holdout.P == 0:
        return None
    if x1 == x2:
        slope = 3 * x1 * x1 * pow(2 * y1, -1, holdout.P) % holdout.P
    else:
        slope = (y2 - y1) * pow((x2 - x1) % holdout.P, -1, holdout.P) % holdout.P
    x3 = (slope * slope - x1 - x2) % holdout.P
    y3 = (slope * (x1 - x3) - y1) % holdout.P
    assert y3 * y3 % holdout.P == (x3*x3*x3 + 7) % holdout.P
    return x3, y3


def generic_recode(pair, base, windows, cache, orbit):
    a, b = pair
    selected = []
    for index in range(windows):
        residue = a % base, b % base
        if residue not in cache:
            canonical = min((x % base, y % base)
                            for x, y in orbit.unit_images(residue))
            seed = orbit.nearest_digit(canonical, base)
            images = orbit.unit_images(seed)
            code = next(code for code, (x, y) in enumerate(images)
                        if (x % base, y % base) == residue)
            cache[residue] = images[code], code
        (da, db), code = cache[residue]
        assert 3 * orbit.norm((da, db)) <= base*base
        assert (a-da) % base == 0 and (b-db) % base == 0
        a, b = (a-da)//base, (b-db)//base
        if da or db:
            selected.append(code)
    return (a, b), selected


def run():
    fixture = json.loads((HERE / "holdout.json").read_text())
    assert fixture["seed"] == holdout.SEED == 20261012671
    assert fixture["generator_sha256"] == screen.sha(HERE / "holdout.py")
    cases = fixture["cases"]
    assert len(cases) == 512
    scalar_stream = b"".join(bytes.fromhex(case["scalar_hex"]) for case in cases)
    assert sha256(scalar_stream).hexdigest() == fixture["scalar_sha256"]
    for name, digest in fixture["excluded_panel_sha256"].items():
        assert screen.sha(EXP / name) == digest
    orbit = screen.load("split_holdout_orbit", screen.NATIVE / "unit_orbit_windows_screen.py")
    old = screen.load("split_holdout_old", screen.NATIVE / "radix943_screen.py")
    plans = screen.load("split_holdout_plans", EXP / "prime-j0-pareto-tree-20261012/plans.py")
    topball = screen.load("split_holdout_topball",
                          EXP / "prime-j0-radix929-topball-20261012/topball.py")
    table = screen.PLANS.read_bytes()
    codes, digits, digest = screen.atlas(orbit)
    assert digest == json.loads((HERE / "design.json").read_text())["ordinary_atlas_sha256"]
    cache929 = {}
    cache943 = {}
    totals = Counter()
    rows = []
    point_lines = []
    for index, case in enumerate(cases):
        scalar = int(case["scalar_hex"], 16)
        assert 0 <= scalar < holdout.ORDER
        expected = None if case["expected_identity"] else (
            int(case["expected_x_hex"], 16), int(case["expected_y_hex"], 16))
        start = old.nearest_representative(scalar)
        assert 3 * orbit.norm(start) <= old.ORDER
        assert (start[0] + old.LAMBDA_TAU*start[1] - scalar) % old.ORDER == 0
        a, b = start
        rebuilt_a = rebuilt_b = 0
        power = 1
        selected = []
        terms = []
        for window in range(screen.WINDOWS):
            packed = codes[(a % screen.BASE)*screen.BASE + (b % screen.BASE)]
            digit = orbit.unit_images(digits[packed >> 3])[packed & 7]
            da, db = digit
            assert (a-da) % screen.BASE == 0 and (b-db) % screen.BASE == 0
            a, b = (a-da)//screen.BASE, (b-db)//screen.BASE
            rebuilt_a += power*da
            rebuilt_b += power*db
            if digit != (0, 0):
                selected.append(packed & 7)
                terms.append((power, digit))
            power *= screen.BASE
        assert 3*orbit.norm((a, b)) <= screen.CAP
        la, ha = screen.split(a)
        lb, hb = screen.split(b)
        assert abs(ha) <= screen.HIGH_A and abs(hb) <= screen.HIGH_B
        assert (rebuilt_a+power*(la+screen.SPLIT*ha),
                rebuilt_b+power*(lb+screen.SPLIT*hb)) == start
        if la or lb:
            selected.append(0)
            terms.append((power, (la, lb)))
        if ha or hb:
            selected.append(0)
            terms.append((power*screen.SPLIT, (ha, hb)))
        point = None
        scalar_sum = 0
        for weight, (da, db) in terms:
            term_scalar = weight*(da + old.LAMBDA_TAU*db) % holdout.ORDER
            scalar_sum = (scalar_sum + term_scalar) % holdout.ORDER
            point = affine_add(point, holdout.multiply(term_scalar))
        assert scalar_sum == scalar
        assert point == expected, (index, point, expected)
        point_lines.append("identity" if point is None else
                           f"{point[0]:064x}:{point[1]:064x}")
        cost = screen.plan_cost(selected, table, plans)
        top929, codes929 = generic_recode(start, 929, 12, cache929, orbit)
        assert 3*orbit.norm(top929) <= topball.CAP
        if top929 != (0, 0):
            canonical = [image for image in topball.images(top929)
                         if topball.sector(image)]
            assert len(canonical) == 1
            codes929.append(topball.images(canonical[0]).index(top929))
        cost929 = screen.plan_cost(codes929, table, plans)
        top943, codes943 = generic_recode(start, 943, 13, cache943, orbit)
        assert top943 == (0, 0)
        cost943 = screen.plan_cost(codes943, table, plans)
        totals.update(cases=1, points_verified=1,
                      split_terms=cost["terms"], split_products=cost["products"],
                      split_rotations=cost["rotations"],
                      control929_products=cost929["products"],
                      control943_products=cost943["products"],
                      high_active=int(bool(ha or hb)))
        rows.append({"index": index,
                     "scalar_sha256": sha256(scalar.to_bytes(32, "big")).hexdigest(),
                     "point": point_lines[-1], "top": [a, b],
                     "low": [la, lb], "high": [ha, hb],
                     "cost": cost, "control929": cost929, "control943": cost943})
    row_bytes = ("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":"))
                           for row in rows) + "\n").encode()
    point_bytes = ("\n".join(point_lines) + "\n").encode()
    receipt = {"schema": 1, "status": "independent_point_replay",
               "cases": len(cases), "totals": dict(sorted(totals.items())),
               "point_stream_sha256": sha256(point_bytes).hexdigest(),
               "rows_sha256": sha256(row_bytes).hexdigest(),
               "holdout_sha256": screen.sha(HERE / "holdout.json"),
               "holdout_generator_sha256": screen.sha(HERE / "holdout.py"),
               "screen_sha256": screen.sha(HERE / "screen.py"),
               "replay_source_sha256": screen.sha(Path(__file__)),
               "plans_sha256": screen.sha(screen.PLANS),
               "orbit_source_sha256": screen.sha(screen.NATIVE / "unit_orbit_windows_screen.py")}
    return receipt, row_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt, rows = run()
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    path = HERE / "holdout-replay.json"
    row_path = HERE / "holdout-rows.jsonl"
    if args.write:
        if path.exists() or row_path.exists():
            raise SystemExit("holdout replay exists; use --check")
        path.write_bytes(payload)
        row_path.write_bytes(rows)
    elif path.read_bytes() != payload or row_path.read_bytes() != rows:
        raise SystemExit("holdout replay differs from frozen files")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
