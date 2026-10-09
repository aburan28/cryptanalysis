#!/usr/bin/env python3
"""Rank audit against independent points in the exact N41 DLP subgroup."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from run_n41_disjoint_s5_sat import Curve, Field  # noqa: E402

_spec = importlib.util.spec_from_file_location("n41_pair_decoder_audit", HERE / "verify.py")
assert _spec is not None and _spec.loader is not None
_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_audit)
feature_vector, insert_low, sha = _audit.feature_vector, _audit.insert_low, _audit.sha


def vector(point):
    x, y = point
    assert x & 1 == 0
    packed = (x >> 1) | (y << 40)
    return feature_vector(packed, 81)


def main():
    rows_out = HERE / "subgroup_control_rows.json"
    result_out = HERE / "subgroup_control_result.json"
    if rows_out.exists() or result_out.exists():
        raise FileExistsError("preserve first subgroup control")
    start = time.monotonic_ns()
    protocol_path = HERE / "protocol_subgroup_control.json"
    protocol = json.loads(protocol_path.read_text())
    names = ("curve_control_rows", "initial_rows", "holdout_rows",
             "cofactor_result", "feature_auditor", "curve_arithmetic")
    paths = {name: (HERE / protocol[name]).resolve() for name in names}
    assert all(sha(path) == protocol[f"{name}_sha256"] for name, path in paths.items())
    cofactor = json.loads(paths["cofactor_result"].read_text())
    assert cofactor["status"] == "PASS" and cofactor["trace_basis_one_bits"] == [0]
    controls = json.loads(paths["curve_control_rows"].read_text())["points"]
    initial = json.loads(paths["initial_rows"].read_text())["rows"]
    holdout = json.loads(paths["holdout_rows"].read_text())["rows"]
    assert len(controls) == len(initial) == len(holdout) == 8192
    curve = Curve(Field(41, [0, 3]), 0)
    subgroup = []
    for point in controls:
        doubled = curve.add(tuple(point), tuple(point))
        assert doubled is not None and curve.on_curve(doubled)
        subgroup.append(doubled)
    assert all(curve.mul(protocol["subgroup_order"], point) is None
               for point in subgroup[:256])
    rows_out.write_text(json.dumps({
        "kind": "n41_independent_doubled_subgroup_control_rows",
        "curve_id": protocol["curve_id"],
        "status": "COMPLETE",
        "points": subgroup,
    }, sort_keys=True, separators=(",", ":")) + "\n")
    pair_points = [row["sum_point"] for row in initial + holdout]
    pair_basis: dict[int, int] = {}
    subgroup_basis: dict[int, int] = {}
    for point in reversed(pair_points):
        insert_low(pair_basis, vector(point))
    for point in reversed(subgroup):
        insert_low(subgroup_basis, vector(point))
    union_basis = dict(pair_basis)
    for row in subgroup_basis.values():
        insert_low(union_basis, row)
    assert len(pair_basis) == 3198
    result = {
        "kind": protocol["kind"],
        "status": "COMPLETE_RANK_CONTROL",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "feature_count": protocol["feature_count"],
        "pair_rows": len(pair_points),
        "pair_rank": len(pair_basis),
        "subgroup_control_rows": len(subgroup),
        "subgroup_control_distinct_points": len(set(subgroup)),
        "subgroup_control_rank": len(subgroup_basis),
        "combined_rank": len(union_basis),
        "subgroup_scalar_replays": 256,
        "subgroup_scalar_replay_failures": 0,
        "exploratory_wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_sha256": {**{name: sha(path) for name, path in paths.items()},
                          "protocol": sha(protocol_path),
                          "subgroup_control": sha(Path(__file__)),
                          "subgroup_control_rows": sha(rows_out)},
    }
    result_out.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"pair_rank": len(pair_basis),
                      "subgroup_rank": len(subgroup_basis),
                      "combined_rank": len(union_basis),
                      "wall_s": result["exploratory_wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
