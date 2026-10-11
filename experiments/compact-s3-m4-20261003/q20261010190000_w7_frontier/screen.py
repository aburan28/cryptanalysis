#!/usr/bin/env python3
"""N131 weight-seven rationality sample and relation/matrix budget screen."""

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(PARENT), str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402

Q1413_W5 = PARENT / "runs/n131_q1413_projected_x_w5.json"
Q1413_W6 = PARENT / "runs/n131_q1413_projected_x_w6.json"
PROTOCOL = PARENT / "protocol.json"
PROPOSAL = "Q20261010190000"
SAMPLE_SIZE = 250_000
SEED = 20261010190000
N = 131


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def freeze():
    curve = load(PROTOCOL)["degree_131_design"]["curve"]
    assert curve["curve_id"] == "EC1N131Ckb1h6816f880945e"
    assert curves.curveOrder(N) == curve["order"]
    assert int(curve["subgroup_order"]) * int(curve["cofactor"]) == curve["order"]
    for path in (Q1413_W5, Q1413_W6):
        assert load(path)["curve_id"] == curve["curve_id"]
    save(HERE / "freeze.json", {
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "curve_id": curve["curve_id"], "isogeny": "none",
        "subgroup_order_r": int(curve["subgroup_order"]),
        "sample_size": SAMPLE_SIZE, "seed": SEED,
        "input_sha256": {str(p.relative_to(ROOT)): digest(p) for p in
                         (Q1413_W5, Q1413_W6, PROTOCOL,
                          Path(field.__file__), Path(curves.__file__))},
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "screen.py")}})


def check_freeze():
    frozen = load(HERE / "freeze.json")
    assert frozen["proposal_id"] == PROPOSAL
    assert frozen["sample_size"] == SAMPLE_SIZE and frozen["seed"] == SEED
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    for name, value in frozen["input_sha256"].items():
        assert digest(ROOT / name) == value
    return frozen


def wilson(success, total):
    z = 1.959963984540054
    p = success / total
    den = 1 + z*z/total
    center = (p + z*z/(2*total)) / den
    radius = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / den
    return center-radius, center+radius


def screen_row(weight, b, k, r, status, interval=None):
    # Uniform-target representation mean: all four-point multisets, repeats
    # included. The one-row-per-query scenario is a separate collector law.
    representations = math.comb(math.ceil(b)+3, 4) / (r-1)
    all_models_queries = max(1, math.ceil(k / representations))
    single_model_queries = math.ceil(k)
    return {
        "weight_bound": weight, "base_status": status,
        "actual_B_or_conditional_B": b,
        "folded_K_or_conditional_K": k,
        "B_interval_conditional": interval,
        "log2_mean_representations_upper": math.log2(representations),
        "all_models_uniform_query_lower_bound_log2": math.log2(all_models_queries),
        "one_novel_row_per_query_lower_bound_log2": math.log2(single_model_queries),
        "one_row_per_query_zero_other_cost_ceiling_under_2pow61_log2":
            61-math.log2(single_model_queries),
        "matrix_4K2_touch_model_log2": math.log2(4*k*k),
        "matrix_8K2_touch_model_log2": math.log2(8*k*k),
    }


def run():
    frozen = check_freeze()
    assert not (HERE / "run.json").exists()
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    rng = random.Random(SEED)
    seen = set()
    classification = hashlib.sha256()
    rational = 0
    replay = []
    started = time.monotonic()
    while len(seen) < SAMPLE_SIZE:
        mask = sum(1 << i for i in rng.sample(range(N), 7))
        if mask in seen:
            continue
        seen.add(mask)
        x = onb.fromCoords(mask)
        is_rational = onb.trace(onb.inv(x)) == onb.trace(x)
        rational += is_rational
        classification.update(mask.to_bytes(17, "little"))
        classification.update(bytes((int(is_rational),)))
        if len(replay) < 64:
            lift = curve.pointFromX(x)
            assert (lift is not None) == is_rational
            replay.append({"mask": mask, "rational": is_rational})
    elapsed = time.monotonic()-started
    low, high = wilson(rational, SAMPLE_SIZE)
    exact_w5 = load(Q1413_W5)
    exact_w6 = load(Q1413_W6)
    b5 = exact_w5["actual_usable_points_B_before_folding"]
    k5 = exact_w5["signed_frobenius_columns_K"]
    b6 = exact_w6["actual_usable_points_B_before_folding"]
    k6 = exact_w6["signed_frobenius_columns_K"]
    pop7 = math.comb(N, 7)
    pop8 = math.comb(N, 8)
    p = rational/SAMPLE_SIZE
    b7 = b6+2*pop7*p
    k7 = k6+pop7*p/N
    b8 = b7+pop8  # P(rational)=1/2, no collisions, extrapolation only.
    k8 = k7+pop8/(2*N)
    r = frozen["subgroup_order_r"]
    rows = [
        screen_row(5, b5, k5, r, "exact_Q1413"),
        screen_row(6, b6, k6, r, "exact_Q1413"),
        screen_row(7, b7, k7, r, "sample_conditional_no_projection_collision",
                   [b6+2*pop7*low, b6+2*pop7*high]),
        screen_row(8, b8, k8, r, "half_rational_extrapolation_no_projection_collision"),
    ]
    save(HERE / "run.json", {
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "curve_id": frozen["curve_id"], "isogeny": "none",
        "freeze_sha256": digest(HERE / "freeze.json"),
        "sample": {"weight": 7, "population": pop7, "size": SAMPLE_SIZE,
                   "seed": SEED, "rational": rational, "rate": p,
                   "wilson_95": [low, high],
                   "support_classification_sha256": classification.hexdigest(),
                   "curve_lift_replay": replay,
                   "elapsed_seconds_exploratory": elapsed},
        "rows": rows,
        "accounting_scope": "Conditional uniform-query supply and explicit 4K2/8K2 matrix-entry touch models; no calibrated complete-solve operation exponent",
        "complete_solve_work_log2": None,
    })
    print(json.dumps({"rational": rational, "rate": p,
                      "B7": b7, "K7": k7, "wall_seconds": elapsed}))


def check():
    frozen = check_freeze()
    receipt = load(HERE / "run.json")
    assert receipt["freeze_sha256"] == digest(HERE / "freeze.json")
    assert receipt["curve_id"] == frozen["curve_id"]
    assert receipt["sample"]["rational"] <= SAMPLE_SIZE
    assert receipt["sample"]["support_classification_sha256"]
    assert receipt["rows"][0]["actual_B_or_conditional_B"] == 309633434
    assert receipt["rows"][1]["actual_B_or_conditional_B"] == 6559634788
    assert receipt["complete_solve_work_log2"] is None
    print("PASS: freeze, exact prefixes, and receipt schema")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("freeze", "run", "check"))
    action = p.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "run":
        run()
    else:
        check()
