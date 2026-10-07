#!/usr/bin/env python3
"""Independent Frobenius-trace and group-law controls for Q1476."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from run_probe import curves, field  # noqa: E402

OUT = HERE / "trace_validation.json"
Q1475 = PARENT / "q1475_ordered_leaves"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frobenius_trace(onb, x: int) -> int:
    total = 0
    value = x
    for _ in range(onb.m):
        total = onb.add(total, value)
        value = onb.frob(value, 1)
    assert total in (0, onb.one())
    return int(total == onb.one())


def build() -> dict:
    rows = []
    for n, weight, seed in ((53, 3, 1476053), (83, 4, 1476083)):
        rng = random.Random(seed)
        onb = field.Onb(n)
        curve = curves.Curve(onb)
        checks = 0
        for position in range(n):
            mask = 1 << position
            assert frobenius_trace(onb, onb.fromCoords(mask)) == 1
            checks += 1
        points = []
        while len(points) < 20:
            mask = sum(1 << j for j in rng.sample(
                range(n), rng.randint(1, weight)))
            x = onb.fromCoords(mask)
            assert frobenius_trace(onb, x) == mask.bit_count() & 1
            checks += 1
            point = curve.pointFromX(x)
            if point is not None:
                assert curve.onCurve(point)
                points.append(point)
        for a, b in zip(points[::2], points[1::2]):
            joined = curve.add(a, b)
            phi = lambda p: (0 if p is None else frobenius_trace(onb, p[0]))
            assert phi(joined) == phi(a) ^ phi(b)
            assert phi(curve.neg(a)) == phi(a)
            assert curve.add(a, curve.neg(a)) is None
            checks += 3
        control = "n53_pinned_sorted" if n == 53 else "n83_pinned_sorted"
        meta = json.loads((Q1475 / "inputs" / control / "meta.json").read_text())
        masks = [int(v, 16) for v in meta["sorted_pinned_raw_x_onb_hex"]]
        raw_points = [curve.pointFromX(onb.fromCoords(x)) for x in masks]
        assert all(point is not None for point in raw_points)
        left = curve.add(raw_points[0], raw_points[1])
        right = curve.add(raw_points[2], raw_points[3])
        total = curve.add(left, right)
        assert left is not None and right is not None and total is not None
        midpoint_masks = [int(onb.toCoords(left[0])),
                          int(onb.toCoords(right[0]))]
        target_mask = int(onb.toCoords(total[0]))
        assert (masks[0].bit_count() ^ masks[1].bit_count() ^
                midpoint_masks[0].bit_count()) & 1 == 0
        assert (masks[2].bit_count() ^ masks[3].bit_count() ^
                midpoint_masks[1].bit_count()) & 1 == 0
        assert (midpoint_masks[0].bit_count() ^
                midpoint_masks[1].bit_count() ^
                target_mask.bit_count()) & 1 == 0
        checks += 3
        rows.append({
            "degree_n": n, "curve_id": meta["curve_id"],
            "factor_base_actual_B": meta["factor_base_actual_B"],
            "folded_columns_K": meta["folded_columns_K"],
            "factor_base_enumerated_set_sha256": meta[
                "factor_base_enumerated_set_sha256"],
            "deterministic_seed": seed,
            "basis_trace_checks": n,
            "rational_point_pair_checks": 10,
            "pinned_control": control,
            "pinned_trace_equations_checked": 3,
            "assertion_count": checks,
            "pinned_raw_target_x_onb_hex": format(target_mask, "x"),
            "parent_input_meta_sha256": sha(Q1475 / "inputs" / control /
                                            "meta.json"),
        })
    return {
        "kind": "q1476_independent_trace_validation",
        "proposal_id": "Q1476", "candidate_id": None,
        "isogeny": "none", "status": "passed",
        "rows": rows,
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "parent_protocol_sha256": sha(Q1475 / "protocol.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = build()
    if args.emit:
        assert not OUT.exists(), "refuse overwrite"
        OUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert result == json.loads(OUT.read_text())
    print(json.dumps({"status": "pass", "checks": sum(
        row["assertion_count"] for row in result["rows"])}), flush=True)


if __name__ == "__main__":
    main()
