#!/usr/bin/env python3
"""Replay a fresh scalar panel through independent secp256k1 point additions."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
NATIVE = EXP / "prime-j0-secp256k1-native"
sys.path.insert(0, str(NATIVE.resolve()))

import holdout
from screen import load, plan_cost, sha
import topball

orbit = load("radix929_holdout_orbit", NATIVE / "unit_orbit_windows_screen.py")
radix943 = load("radix929_holdout_reference", NATIVE / "radix943_screen.py")
plans = load("radix929_holdout_plans", EXP / "prime-j0-pareto-tree-20261012/plans.py")


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
    assert y3 * y3 % holdout.P == (x3 * x3 * x3 + 7) % holdout.P
    return x3, y3


def recode(pair, base, cache, windows):
    a, b = pair
    factor = 1
    rebuilt = [0, 0]
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
        assert 3 * orbit.norm((da, db)) <= base * base
        assert (a - da) % base == (b - db) % base == 0
        rebuilt[0] += factor * da
        rebuilt[1] += factor * db
        if da or db:
            selected.append((index, (da, db), code))
        a, b = (a - da) // base, (b - db) // base
        factor *= base
    rebuilt[0] += factor * a
    rebuilt[1] += factor * b
    assert tuple(rebuilt) == pair
    return selected, (a, b)


def run():
    fixture = json.loads((HERE / "holdout.json").read_text())
    assert fixture["schema"] == 1 and fixture["seed"] == 20261012929
    assert fixture["generator_sha256"] == sha(HERE / "holdout.py")
    cases = fixture["cases"]
    assert len(cases) == 512
    scalar_bytes = b"".join(bytes.fromhex(case["scalar_hex"]) for case in cases)
    assert sha256(scalar_bytes).hexdigest() == fixture["scalar_sha256"]
    assert sha(EXP / "prime-j0-sector-digit-20261010/fresh-inputs.json") == \
        json.loads((HERE / "design.json").read_text())["frozen_design_sha256"]
    plan_table = (EXP / "prime-j0-pareto-tree-20261012/plans.bin").read_bytes()
    assert len(plan_table) == 680 * 42
    cache929 = {}
    cache943 = {}
    totals = Counter()
    top_ranks = set()
    prefix = [0]
    for u in range(1, topball.MAX_ROW + 1):
        low, high = topball.row_bounds(u)
        prefix.append(prefix[-1] + max(0, high - low + 1))
    assert prefix[-1] + 1 == 136_993
    rows = []
    point_lines = []
    for index, case in enumerate(cases):
        scalar = int(case["scalar_hex"], 16)
        assert 0 <= scalar < holdout.ORDER
        expected = None if case["expected_identity"] else (
            int(case["expected_x_hex"], 16), int(case["expected_y_hex"], 16))
        representative = radix943.nearest_representative(scalar)
        assert 3 * orbit.norm(representative) <= holdout.ORDER
        assert (representative[0] + radix943.LAMBDA_TAU * representative[1]
                - scalar) % holdout.ORDER == 0
        selected, terminal = recode(representative, 929, cache929, 12)
        assert 3 * topball.norm(terminal) <= topball.CAP
        top_rank = 0
        if terminal != (0, 0):
            canonical = [image for image in topball.images(terminal) if topball.sector(image)]
            assert len(canonical) == 1
            u, b = -canonical[0][0], canonical[0][1]
            low, high = topball.row_bounds(u)
            assert low <= b <= high
            top_rank = 1 + prefix[u - 1] + b - low
            assert 0 < top_rank < 136_993
            code = topball.images(canonical[0]).index(terminal)
            selected.append((12, terminal, code))
        top_ranks.add(top_rank)
        baseline, terminal943 = recode(representative, 943, cache943, 13)
        assert terminal943 == (0, 0)
        products929 = plan_cost([code for _, _, code in selected], plan_table, plans)
        products943 = plan_cost([code for _, _, code in baseline], plan_table, plans)

        point = None
        scalar_sum = 0
        for power, (da, db), _ in selected:
            weight = pow(929, power, holdout.ORDER)
            term_scalar = (da + radix943.LAMBDA_TAU * db) * weight % holdout.ORDER
            scalar_sum = (scalar_sum + term_scalar) % holdout.ORDER
            point = affine_add(point, holdout.multiply(term_scalar))
        assert scalar_sum == scalar
        assert point == expected, (index, point, expected)
        point_lines.append("identity" if point is None else
                           f"{point[0]:064x}:{point[1]:064x}")
        totals.update(cases=1, group_points_verified=1,
                      candidate_terms=products929["terms"],
                      candidate_products=products929["products"],
                      candidate_rotations=products929["rotations"],
                      candidate_depth=products929["depth"],
                      reference_terms=products943["terms"],
                      reference_products=products943["products"],
                      reference_rotations=products943["rotations"],
                      reference_depth=products943["depth"],
                      top_nonzero=int(terminal != (0, 0)))
        rows.append({"index": index,
                     "scalar_sha256": sha256(bytes.fromhex(case["scalar_hex"])).hexdigest(),
                     "top": list(terminal), "top_rank": top_rank,
                     "candidate": products929, "reference": products943,
                     "point": point_lines[-1], "verified": True})
    row_bytes = ("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":"))
                           for row in rows) + "\n").encode()
    return {
        "schema": 1, "status": "independent_group_point_replay",
        "source_costs_model_only": True, "curve": "secp256k1", "radix": 929,
        "cases": len(cases), "totals": dict(sorted(totals.items())),
        "distinct_top_ranks": len(top_ranks),
        "point_digest": sha256("\n".join(point_lines).encode()).hexdigest(),
        "rows_sha256": sha256(row_bytes).hexdigest(),
        "holdout_sha256": sha(HERE / "holdout.json"),
        "design_commit": "9a103281a",
        "design_sha256": sha(HERE / "design.json"),
        "plan_table_sha256": sha(EXP / "prime-j0-pareto-tree-20261012/plans.bin"),
        "replay_source_sha256": sha(Path(__file__)),
        "independent_group_source_sha256": sha(HERE / "holdout.py"),
    }, row_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt, rows = run()
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    receipt_path = HERE / "holdout-replay.json"
    row_path = HERE / "holdout-rows.jsonl"
    if args.write:
        if receipt_path.exists() or row_path.exists():
            raise SystemExit("holdout replay exists; use --check")
        receipt_path.write_bytes(payload)
        row_path.write_bytes(rows)
        print(json.dumps({"status": receipt["status"], "totals": receipt["totals"]}, sort_keys=True))
    elif receipt_path.read_bytes() != payload or row_path.read_bytes() != rows:
        raise SystemExit("holdout replay differs from frozen sources or inputs")
    else:
        print("512 independent group point replays verified")


if __name__ == "__main__":
    main()
