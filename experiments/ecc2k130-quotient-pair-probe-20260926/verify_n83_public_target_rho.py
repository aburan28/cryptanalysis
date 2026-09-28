#!/usr/bin/env python3
"""Independently replay a rho scalar for the frozen n83 public target."""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import curves
import field

HERE = Path(__file__).resolve().parent
CURVE_ID = "EC1N83Ckb1h876c2921cb64"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--driver-source", type=Path, required=True)
    parser.add_argument("--rho-source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    assert reference["curve_id"] == CURVE_ID
    identity = reference["curve_identity_record"]
    canonical_identity = json.dumps(identity, sort_keys=True,
                                    separators=(",", ":")).encode()
    assert CURVE_ID.endswith("h" + hashlib.sha256(
        canonical_identity).hexdigest()[:12])
    g = tuple(reference["curve_identity_record"]["curve"]["generator"])
    q = tuple(reference["workload"]["target"])
    order = int(reference["subgroup_order"])
    log = args.log.read_text()
    scalars = re.findall(r"^\s*k = (\d+)\s*$", log, re.MULTILINE)
    finishes = re.findall(
        r"^\s*solved after (\d+) iterations of (\d+) walks in ([0-9.]+) s "
        r"\((\d+) distinguished points\)\s*$", log, re.MULTILINE)
    if (len(scalars) != 1 or len(finishes) != 1 or
            "verified [k]P == Q" not in log):
        raise SystemExit("rho log has no single completed, internally verified solve")
    k = int(scalars[0])
    iterations_per_walk, walks, seconds, distinguished = finishes[0]
    curve = curves.Curve(field.Onb(83))
    assert curve.onCurve(g) and curve.onCurve(q)
    assert curve.mul(g, order) is None
    assert curve.mul(q, order) is None
    assert 0 < k < order
    assert curve.mul(g, k) == q
    total_walk_iterations = int(iterations_per_walk) * int(walks)
    report = {
        "kind": "independent_n83_public_target_rho_replay",
        "curve_id": CURVE_ID,
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none",
        "subgroup_order": str(order),
        "public_generator": list(g),
        "public_target": list(q),
        "recovered_scalar": str(k),
        "independent_scalar_replay_passed": True,
        "rho_online_seconds_from_runner": float(seconds),
        "rho_walk_iterations": str(total_walk_iterations),
        "rho_walk_iterations_log2": math.log2(total_walk_iterations),
        "rho_distinguished_points": int(distinguished),
        "work_boundary": "rho walk iterations only; no IC relation yield or IC solve-work claim",
        "complete_IC_work_log2": None,
        "reference_sha256": digest(reference_path),
        "rho_log_sha256": digest(args.log),
        "rho_binary_sha256": digest(args.binary),
        "rho_source_sha256": digest(args.rho_source),
        "executed_driver_source_sha256": digest(args.driver_source),
        "portable_driver_source_sha256": digest(
            HERE / "n83_public_target_rho.cpp"),
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": CURVE_ID, "scalar": str(k),
                      "rho_walk_iterations_log2": report[
                          "rho_walk_iterations_log2"],
                      "independent_scalar_replay_passed": True}))


if __name__ == "__main__":
    main()
