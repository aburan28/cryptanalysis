#!/usr/bin/env python3
"""Exact integer Q1422 index law on conditional larger N131 bases."""

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
W7 = PARENT / "q20261010190000_w7_frontier/run.json"
W5 = PARENT / "runs/n131_q1413_projected_x_w5.json"
W6 = PARENT / "runs/n131_q1413_projected_x_w6.json"
PROPOSAL = "Q20261010192300"
CURVE = "EC1N131Ckb1h6816f880945e"
N = 131
R = 680564733841876926932320129493409985129
Q1422_EXACT_T = 395993893517632118233168669
Q1422_REFERENCE_SHA256 = "412ed6aa1987023442b85e729e675855249093dc"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def law(k):
    assert isinstance(k, int) and 0 < k
    u = (R-1)//(2*N)
    cap = min(u, k*(N*k+1))
    # Here all selected K lie below the unconstrained insertion optimum.
    # Check the one-step direction so the full allowed cap minimizes T.
    def total(m):
        l = (k*u + 2*m-1)//(2*m)
        return m+l, l
    assert total(cap)[0] <= total(cap-1)[0]
    t, l = total(cap)
    return {"K": k, "maximum_distinct_index_keys_M": str(cap),
            "half_success_necessary_lookups_L": str(l),
            "necessary_insertions_plus_lookups_T": str(t),
            "log2_M": math.log2(cap), "log2_L": math.log2(l),
            "log2_T": math.log2(t),
            "gap_over_2pow61_log2": math.log2(t)-61}


def freeze():
    w7, w5, w6 = load(W7), load(W5), load(W6)
    assert w7["curve_id"] == w5["curve_id"] == w6["curve_id"] == CURVE
    assert w7["proposal_id"] == "Q20261010190000"
    assert w6["actual_usable_points_B_before_folding"] == 6559634788
    assert w6["signed_frobenius_columns_K"] == 25036774
    assert law(w6["signed_frobenius_columns_K"])[
        "necessary_insertions_plus_lookups_T"] == str(Q1422_EXACT_T)
    save(HERE / "freeze.json", {
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "curve_id": CURVE, "isogeny": "none", "field_degree_n": N,
        "prime_subgroup_order_r_decimal": str(R),
        "q1422_reference": "https://github.com/aburan28/cryptanalysis/blob/codex/ecc2k130-q1422-global-index/experiments/compact-s3-m4-q1422-global-index-20261010/result.json",
        "q1422_reference_sha256": Q1422_REFERENCE_SHA256,
        "q1422_exact_base_action_count": str(Q1422_EXACT_T),
        "input_sha256": {str(path.relative_to(ROOT)): sha(path)
                         for path in (W7, W5, W6)},
        "source_sha256": {name: sha(HERE / name) for name in
                          ("PROTOCOL.md", "screen.py", "verify.py")}})


def check():
    frozen = load(HERE / "freeze.json")
    assert frozen["curve_id"] == CURVE
    assert frozen["q1422_exact_base_action_count"] == str(Q1422_EXACT_T)
    for name, value in frozen["source_sha256"].items():
        assert sha(HERE / name) == value
    for name, value in frozen["input_sha256"].items():
        assert sha(ROOT / name) == value
    return frozen


def run():
    frozen = check()
    w7 = load(W7)
    exact = [load(W5), load(W6)]
    rows = []
    for weight, item in zip((5, 6), exact):
        assert item["normal_basis_weight_bound"] == weight
        rows.append({"weight_bound": weight, "base_status": "exact_Q1413",
                     "actual_B_or_conditional_B": item[
                         "actual_usable_points_B_before_folding"],
                     **law(item["signed_frobenius_columns_K"])})
    assert int(rows[1]["necessary_insertions_plus_lookups_T"]) == (
        Q1422_EXACT_T)
    estimate = w7["rows"][2]
    assert estimate["weight_bound"] == 7
    scenarios = {
        "sample_low": math.floor(estimate["B_interval_conditional"][0]/(2*N)),
        "sample_point": round(estimate["folded_K_or_conditional_K"]),
        "sample_high": math.ceil(estimate["B_interval_conditional"][1]/(2*N)),
    }
    assert scenarios["sample_low"] <= scenarios["sample_point"] <= (
        scenarios["sample_high"])
    for label, k in scenarios.items():
        rows.append({"weight_bound": 7,
                     "base_status": "conditional_sample_no_projection_collision",
                     "scenario": label, **law(k)})
    extrap = w7["rows"][3]
    assert extrap["weight_bound"] == 8
    rows.append({"weight_bound": 8,
                 "base_status": "half_rational_extrapolation_no_projection_collision",
                 **law(round(extrap["folded_K_or_conditional_K"]))})
    save(HERE / "result.json", {
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "curve_id": CURVE, "isogeny": "none", "field_degree_n": N,
        "canonical_key_universe_U_decimal": str((R-1)//(2*N)),
        "freeze_sha256": sha(HERE / "freeze.json"),
        "scope": "Q1422 fixed target-independent explicit S3 output index and uniform nonzero subgroup target; conditional larger-base sizes where labeled",
        "rows": rows, "complete_solve_work_log2": None,
        "action_unit": "one distinct index-key insertion or canonical-key lookup"})
    print(json.dumps([{"weight": row["weight_bound"],
                      "scenario": row.get("scenario"),
                      "log2_T": row["log2_T"]} for row in rows]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run"))
    action = parser.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "check":
        check(); print("PASS: freeze")
    else:
        run()
