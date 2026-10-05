#!/usr/bin/env python3
"""Known-witness N53 PDP search control, paired across weight encodings."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import time

from circuit import Circuit
from n53_group import Curve, Field, N, normal_basis
import run_n53_stage as stage

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEED = 53009


def planted_fixture(field, curve, base):
    rng = random.Random(SEED)
    points = sorted(base["raw_to_projected"])
    for attempt in range(1, 10001):
        picked = rng.sample(points, 5)
        prefixes = []
        total = None
        for point in picked:
            total = curve.add(total, point)
            prefixes.append(total)
        if total is None or total[0] == 0:
            continue
        if any(value is None or value[0] == 0 for value in prefixes[1:4]):
            continue
        xs = [point[0] for point in picked]
        mids = [point[0] for point in prefixes[1:4]]
        for a, b, c in ((xs[0], xs[1], mids[0]),
                        (mids[0], xs[2], mids[1]),
                        (mids[1], xs[3], mids[2]),
                        (mids[2], xs[4], total[0])):
            e2 = field.mul(a, b) ^ field.mul(a, c) ^ field.mul(b, c)
            e3 = field.mul(field.mul(a, b), c)
            assert field.square(e2) ^ e3 ^ 1 == 0
        return {"seed": SEED, "selection_attempt": attempt,
                "points": [list(p) for p in picked], "x": xs,
                "intermediate_x": mids, "target": list(total),
                "curve_group_witness_replayed": True}
    raise AssertionError("no nondegenerate planted fixture")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoding", choices=("fc", "unary"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--conflicts", type=int, default=100000)
    args = parser.parse_args()
    if args.seconds < 1 or args.conflicts < 1:
        raise ValueError("limits must be positive")
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("run output is immutable")
    out.mkdir(parents=True)
    field = Field()
    curve = Curve(field)
    _, conjugates = normal_basis(field)
    base_start = time.perf_counter_ns()
    base = stage.geometry(field, curve, conjugates)
    base_ns = time.perf_counter_ns() - base_start
    fixture = planted_fixture(field, curve, base)
    target = tuple(fixture["target"])
    stage.TARGET = target  # The common builder and lift read this fixed target.
    circuit = Circuit(N, list(stage.LOW_TERMS))
    build_start = time.perf_counter_ns()
    meta = stage.build(circuit, conjugates, base["rejected_pairs"], args.encoding)
    build_ns = time.perf_counter_ns() - build_start
    xcnf = out / "system.xcnf"
    write_start = time.perf_counter_ns()
    circuit.write(xcnf)
    write_ns = time.perf_counter_ns() - write_start
    attempt = stage.solve(xcnf, out, args.seconds, args.conflicts)
    model = stage.parse_model((out / "solver.stdout.txt").read_text(errors="replace"))
    model_verified = model is not None and stage.verify_model(circuit, model)
    group_lift = stage.lift_model(curve, base["raw_to_projected"], conjugates,
                                  meta, model) if model_verified else None
    if group_lift and group_lift["verified"]:
        status = "VERIFIED_DECOMPOSITION"
    elif model is not None:
        status = "INVALID_MODEL_OR_GROUP_LIFT"
    elif attempt["guard"]:
        status = attempt["guard"].upper()
    else:
        status = "INDETERMINATE"
    source_paths = [Path(__file__), HERE / "run_n53_stage.py",
                    HERE / "n53_group.py", HERE / "circuit.py",
                    HERE / "fc_hamming.py", HERE / "unary_hamming.py"]
    receipt = {
        "kind": "n53_weight2_s3_planted_pdp_control",
        "status": status, "candidate_id": None, "proposal_id": None,
        "encoding": args.encoding, "summands": 5,
        "target_kind": "planted_control_not_natural_yield",
        "target": fixture["target"], "fixture": fixture,
        "workload_id": "W" + stage.digest({"curve": "N53_kb1", "fixture": fixture})[:12],
        "factor_base": {
            "actual_usable_points": base["usable_projected_points"],
            "effective_columns": base["signed_frobenius_columns"],
            "projected_set_sha256": base["projected_set_sha256"]},
        "formula": {key: value for key, value in meta.items()
                    if key not in ("x_rows", "middle_rows")},
        "x_rows": meta["x_rows"], "middle_rows": meta["middle_rows"],
        "limits": {"seconds": args.seconds, "conflicts": args.conflicts,
                   "solver_threads": 1,
                   "sampled_rss_guard_bytes": stage.MAX_RSS_BYTES},
        "phase_wall_ns": {"factor_base": base_ns,
                          "formula_build": build_ns,
                          "xcnf_write": write_ns,
                          "solver": attempt["solver_wall_ns"]},
        "attempt": attempt, "model_xcnf_verified": model_verified,
        "group_lift": group_lift,
        "xcnf_sha256": stage.file_hash(xcnf),
        "solver_binary_sha256": stage.file_hash(stage.CMS),
        "source_sha256": {str(p.relative_to(ROOT)): stage.file_hash(p)
                          for p in source_paths},
        "host": {"platform": platform.platform(), "machine": platform.machine(),
                 "python": platform.python_version()},
        "claim_boundary": "Planted known-witness PDP control only; not natural relation yield or a DLP."}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"encoding": args.encoding, "status": status,
                      "target": fixture["target"], "formula": receipt["formula"],
                      "solver_wall_ns": attempt["solver_wall_ns"],
                      "sampled_peak_child_rss_bytes": attempt["sampled_peak_child_rss_bytes"]},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
