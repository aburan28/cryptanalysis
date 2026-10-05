"""Fixed-target support bound for uniformly sampled first-pair x midpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXP = ROOT / "experiments/compact-s3-m4-20261003"
INPUTS = {
    "n53_n83_curves": EXP / "q1438_dense_base/protocol.json",
    "n131_curve": EXP / "q1413_projected_x_protocol.json",
    "n53_base": EXP / "q1438_dense_base/n53_w4_base.json",
    "n83_base": EXP / "q1438_dense_base/n83_w6_base.json",
    "n131_base": EXP / "runs/n131_q1413_projected_x_w6.json",
    "selected_w7_model": EXP / "q1442_selected_base_screen/result.json",
}
PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "result.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def frozen_protocol() -> dict:
    return {
        "kind": "q1447_uniform_midpoint_support_protocol",
        "proposal_id": "Q1447",
        "candidate_id": None,
        "isogeny": "none",
        "work_unit": "one uniformly sampled raw first-pair intermediate x; all subsequent computation is free",
        "input_law": "For one fixed public target, sample each first-pair intermediate x independently and uniformly from all 2^n field elements. Test all target preimages, signs, second pairs, and correctness for free. The factor base contains both signs of every included raw point.",
        "scope": "Applies only to uniform midpoint sampling or restarts, including an oracle for everything after the midpoint choice. It does not bound SAT-guided, algebraically constrained, or other nonuniform midpoint selection, nor shared batch processing of midpoint choices.",
        "proof": "The B signed raw factor-base points yield at most C(B+1,2) distinct pair sums, even allowing repeated leaves. Because the raw base is closed under negation, pair-sum support is negation-invariant. An ordinary binary curve has at most one nonidentity rational 2-torsion point, so at most ceil(C(B+1,2)/2) field x coordinates can be first-pair sums. For any fixed public target, every valid four-point witness has its first-pair midpoint in this support. A union bound gives P(success in t uniform x draws) <= t*min(1,ceil(C(B+1,2)/2)/2^n).",
        "source_sha256": sha(Path(__file__)),
        "audit_source_sha256": sha(HERE / "verify.py"),
        "input_sha256": {
            str(path.relative_to(ROOT)): sha(path) for path in INPUTS.values()
        },
    }


def exact_base(path: Path, n: int, expected_curve: str) -> dict:
    data = json.loads(path.read_text())
    assert data["field_degree_n"] == n
    assert data["curve_id"] == expected_curve
    assert data["candidate_id"] is None
    assert data["isogeny"] == "none"
    assert all(row["identity_projection_orbits"] == 0 for row in data["strata"])
    assert all(row.get("duplicate_projected_orbits_at_insertion",
                       row.get("duplicate_projection_orbits")) == 0
               for row in data["strata"])
    b = int(data["actual_usable_points_B_before_folding"])
    k = int(data["signed_frobenius_columns_K"])
    assert b == 2 * n * k, "raw/sign/Frobenius expansion mismatch"
    assert "both signs" in data["enumerated_set_encoding"]
    assert len(data["enumerated_set_sha256"]) == 64
    return data


def row(label: str, n: int, curve_id: str, b: int, k: int | None,
        set_digest: str | None, conditional: bool) -> dict:
    pair_bound = b * (b + 1) // 2
    x_support_bound = (pair_bound + 1) // 2
    field_size = 1 << n
    assert x_support_bound < field_size
    # P(success) <= t*x_support_bound/field_size; 19/20 is the
    # necessary 95-percent coverage threshold, with a free suffix oracle.
    minimum_trials = (19 * field_size + 20 * x_support_bound - 1) // (
        20 * x_support_bound)
    return {
        "label": label,
        "curve_id": curve_id,
        "field_degree_n": n,
        "actual_B": None if conditional else b,
        "actual_K": None if conditional else k,
        "B_used_in_bound": str(b),
        "K_reference": None if k is None else str(k),
        "base_set_sha256": set_digest,
        "conditional_base_model": conditional,
        "maximum_unordered_raw_pair_sums": str(pair_bound),
        "maximum_first_pair_x_support": str(x_support_bound),
        "uniform_midpoint_hit_probability_log2_upper": (
            math.log2(x_support_bound) - n),
        "minimum_uniform_midpoint_trials_for_95pct_one_relation": str(
            minimum_trials),
        "minimum_uniform_midpoint_trials_log2": math.log2(minimum_trials),
        "minimum_trials_exceed_2pow61": minimum_trials > 2**61,
    }


def compute(protocol: dict) -> dict:
    if protocol != frozen_protocol():
        raise ValueError("source or input changed after protocol freeze")
    specs = (
        ("n53_base", 53, "EC1N53Ckb1hf77aab617904", "N53_exact_W_le_4"),
        ("n83_base", 83, "EC1N83Ckb1h876c2921cb64", "N83_exact_W_le_6"),
        ("n131_base", 131, "EC1N131Ckb1h6816f880945e",
         "N131_exact_W_le_6"),
    )
    rows = []
    dense_curves = json.loads(INPUTS["n53_n83_curves"].read_text())
    n131_curve = json.loads(INPUTS["n131_curve"].read_text())
    for key, n, curve_id, label in specs:
        base = exact_base(INPUTS[key], n, curve_id)
        if n in (53, 83):
            curve = dense_curves["instances"][str(n)]["curve"]
            assert curve["curve_id"] == curve_id
            assert (curve["a1"], curve["a3"]) == (1, 0)
        else:
            assert n131_curve["instances"]["131"]["curve_id"] == curve_id
            assert n131_curve["mathematical_identity"].startswith(
                "For y^2+xy=x^3+1")
        rows.append(row(label, n, curve_id,
                        int(base["actual_usable_points_B_before_folding"]),
                        int(base["signed_frobenius_columns_K"]),
                        base["enumerated_set_sha256"], False))
    selected = json.loads(INPUTS["selected_w7_model"].read_text())
    assert selected["curve_id"] == rows[-1]["curve_id"]
    assert selected["actual_selected_B"] is None
    assert selected["actual_selected_K"] is None
    assert selected["selected_base_set_sha256"] is None
    model = next(item for item in selected["rows"]
                 if item["label"] == "selected_W7_conditional_model")
    b_model, k_model = int(model["B_model"]), int(model["K_model"])
    assert b_model == 2 * 131 * k_model
    rows.append(row("N131_selected_W7_conditional_model", 131,
                    rows[-1]["curve_id"], b_model, k_model, None, True))
    return {
        "kind": "q1447_uniform_midpoint_support_bound",
        "proposal_id": "Q1447",
        "candidate_id": None,
        "isogeny": "none",
        "work_unit": protocol["work_unit"],
        "input_law": protocol["input_law"],
        "scope": protocol["scope"],
        "proof": protocol["proof"],
        "rows": rows,
        "ordinary_N83_relation_measured_here": False,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "decision": "Uniform midpoint restarts are excluded as a sub-2^61 N131 W<=6 or conditional selected-W7 route even with free completion. Keep the first-pair intermediate unfixed until target and both sparse pairs jointly constrain it; measure that new solver on ordinary N53/N83 queries.",
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if sum((args.freeze, args.emit, args.check)) != 1:
        parser.error("choose --freeze, --emit, or --check")
    if args.freeze:
        write_new(PROTOCOL, frozen_protocol())
        return
    result = compute(json.loads(PROTOCOL.read_text()))
    if args.emit:
        write_new(RESULT, result)
    elif json.loads(RESULT.read_text()) != result:
        raise ValueError("result differs from pinned source and inputs")
    else:
        print("Q1447 uniform-midpoint support screen reproduces")


if __name__ == "__main__":
    main()
