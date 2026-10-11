#!/usr/bin/env python3
"""Exact fixed-index action optimization for the Q1413 N131 base."""

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "compact-s3-m4-20261003"
INPUTS = {
    "base_protocol": PARENT / "q1413_projected_x_protocol.json",
    "base_receipt": PARENT / "runs/n131_q1413_projected_x_w6.json",
    "sage_replay": PARENT / "runs/n131_q1413_sage_projection_replay.json",
    "query_bound": PARENT / "runs/n131_q1414_exact_uniform_query_bound.json",
    "pair_screen": PARENT / "runs/n131_q1416_exact_base_pair_index_screen.json",
}
CURVE = "EC1N131Ckb1h6816f880945e"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def ceildiv(a, b):
    return (a + b - 1) // b


def cap(k, n):
    return k * (n * k + 1)


def first_true(predicate, low, high):
    assert predicate(high)
    while low < high:
        middle = (low + high) // 2
        if predicate(middle):
            high = middle
        else:
            low = middle + 1
    return low


def derivative_sign(k, n, u):
    return 2 * (2 * n * k + 1) * (n * k + 1) ** 2 - n * u


def unconstrained(k, u):
    # The least integer T with 2 floor(T/2) ceil(T/2) >= K U.
    t = math.isqrt(2 * k * u)
    while 2 * (t // 2) * (t - t // 2) < k * u:
        t += 1
    m = t // 2
    assert m + ceildiv(k * u, 2 * m) == t
    return m


def outcome(k, n, u):
    m_cap = min(u, cap(k, n))
    m = m_cap if 2 * m_cap * m_cap < k * u else unconstrained(k, u)
    assert 1 <= m <= m_cap
    lookups = ceildiv(k * u, 2 * m)
    actions = m + lookups
    return {
        "K": str(k), "M": str(m), "half_success_necessary_lookups_L": str(lookups),
        "necessary_build_plus_lookup_actions_T": str(actions),
        "log2_K": math.log2(k), "log2_M": math.log2(m),
        "log2_L": math.log2(lookups), "log2_T": math.log2(actions),
        "T_gap_over_2_to_61_bits": math.log2(actions) - 61,
    }


def freeze():
    assert not (HERE / "freeze.json").exists()
    write(HERE / "freeze.json", {
        "schema": "q1422-global-index-freeze-v1", "proposal_id": "Q1422",
        "curve_id": CURVE, "candidate_id": None, "run_id": None,
        "isogeny": "none",
        "protocol_sha256": sha(HERE / "PROTOCOL.md"),
        "compute_sha256": sha(HERE / "compute.py"),
        "verifier_sha256": sha(HERE / "verify.py"),
        "input_sha256": {key: sha(path) for key, path in INPUTS.items()},
    })
    print(json.dumps({"status": "FROZEN", "sha256": sha(HERE / "freeze.json")}))


def inputs():
    frozen = read(HERE / "freeze.json")
    assert frozen["schema"] == "q1422-global-index-freeze-v1"
    assert frozen["proposal_id"] == "Q1422" and frozen["curve_id"] == CURVE
    assert frozen["candidate_id"] is None and frozen["run_id"] is None
    assert frozen["isogeny"] == "none"
    assert frozen["protocol_sha256"] == sha(HERE / "PROTOCOL.md")
    assert frozen["compute_sha256"] == sha(HERE / "compute.py")
    assert frozen["verifier_sha256"] == sha(HERE / "verify.py")
    assert frozen["input_sha256"] == {key: sha(path) for key, path in INPUTS.items()}
    records = {key: read(path) for key, path in INPUTS.items()}
    protocol, base, replay, query, pair = (records[key] for key in INPUTS)
    n = base["field_degree_n"]
    r = protocol["instances"]["131"]["subgroup_order"]
    k = base["signed_frobenius_columns_K"]
    b = base["actual_usable_points_B_before_folding"]
    assert n == 131 and protocol["instances"]["131"]["curve_id"] == CURVE
    assert base["curve_id"] == replay["curve_id"] == query["curve_id"] == pair["curve_id"] == CURVE
    assert replay["status"] == "PASS" and replay["independent_subgroup_checks"] == 16
    assert base["normal_basis_weight_bound"] == 6 and b == 2 * n * k
    assert pair["subgroup_order_r"] == r and pair["folded_columns_K"] == k
    assert pair["actual_usable_points_B_before_folding"] == b
    assert query["folded_columns_K"] == k
    assert query["actual_usable_points_B_before_folding"] == b
    assert pair["base_set_sha256"] == query["base_set_sha256"] == base["enumerated_set_sha256"]
    assert (r - 1) % (2 * n) == 0
    return frozen, records, n, r, k, b, (r - 1) // (2 * n)


def run():
    assert not (HERE / "result.json").exists()
    frozen, records, n, r, k, b, u = inputs()
    switch = first_true(lambda x: 2 * x * (n * x + 1) ** 2 >= u, 1, u)
    derivative = first_true(lambda x: derivative_sign(x, n, u) >= 0, 1, switch)
    assert 1 < k < derivative < switch
    options = [outcome(derivative - 1, n, u), outcome(derivative, n, u),
               outcome(switch, n, u)]
    best = min(options, key=lambda row: int(row["necessary_build_plus_lookup_actions_T"]))
    actual = outcome(k, n, u)
    pair = records["pair_screen"]
    query = records["query_bound"]
    write(HERE / "result.json", {
        "schema": "q1422-global-index-result-v1", "proposal_id": "Q1422",
        "curve_id": CURVE, "candidate_id": None, "run_id": None,
        "isogeny": "none", "isogeny_stage_code": "ISO0",
        "action_unit": "one distinct index-key insertion or one canonical-key lookup",
        "scope": "explicit target-independent S3 index and fixed nonadaptive partner list; ordinary uniform nonzero subgroup target; K required rank rows",
        "field_degree_n": n, "prime_subgroup_order_r_decimal": str(r),
        "canonical_key_universe_U_decimal": str(u),
        "base_proposal_id": "Q1413", "normal_basis_weight_bound": 6,
        "actual_usable_points_B": b, "actual_folded_columns_K": k,
        "factor_base_enumerated_set_sha256": records["base_receipt"]["enumerated_set_sha256"],
        "exact_base_index_action_floor": actual,
        "cap_to_free_switch_K": str(switch),
        "convex_derivative_first_nonnegative_K": str(derivative),
        "certifying_global_candidates": options,
        "global_relaxed_index_action_floor": best,
        "q1416_conditional_K_row_pair_probe_model_log2": pair[
            "K_rows_pair_probes_model_log2"],
        "q1414_necessary_uniform_queries_for_half_rank": query[
            "query_bounds"]["rank_success_50_percent"]["minimum_uniform_nonidentity_queries"],
        "complete_cold_field_calls_log2": None,
        "complete_online_one_target_field_calls_log2": None,
        "complete_cold_wall_seconds": None,
        "complete_online_one_target_wall_seconds": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "input_sha256": frozen["input_sha256"],
    })
    print(json.dumps({"status": "RESULT", "exact_base_log2_actions":
                      actual["log2_T"], "global_log2_actions": best["log2_T"]}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    if parser.parse_args().action == "freeze":
        freeze()
    else:
        run()


if __name__ == "__main__":
    main()
