#!/usr/bin/env python3
"""Independent exact base and integer-optimizer checks for Q1422."""

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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def ceildiv(a, b):
    return (a + b - 1) // b


def cost(k, m, u):
    return m + ceildiv(k * u, 2 * m)


def check_small_domains():
    checked = 0
    for n in (1, 2, 3, 5):
        for u in range(2, 65):
            for k in range(1, u + 1):
                cap = min(u, k * (n * k + 1))
                brute = min(cost(k, m, u) for m in range(1, cap + 1))
                root = math.isqrt((k * u) // 2)
                choices = {cap, min(cap, max(1, root)), min(cap, root + 1)}
                derived = min(cost(k, m, u) for m in choices)
                assert derived == brute, (n, u, k)
                checked += 1
    return checked


def check_row(row, n, u):
    k, m = int(row["K"]), int(row["M"])
    assert 1 <= m <= min(u, k * (n * k + 1))
    l = ceildiv(k * u, 2 * m)
    t = m + l
    assert l == int(row["half_success_necessary_lookups_L"])
    assert t == int(row["necessary_build_plus_lookup_actions_T"])
    assert math.isclose(math.log2(t), row["log2_T"], abs_tol=1e-12)
    assert math.isclose(math.log2(t) - 61, row["T_gap_over_2_to_61_bits"], abs_tol=1e-12)
    return t


def main():
    freeze = read(HERE / "freeze.json")
    result = read(HERE / "result.json")
    records = {key: read(path) for key, path in INPUTS.items()}
    assert freeze["protocol_sha256"] == sha(HERE / "PROTOCOL.md")
    assert freeze["compute_sha256"] == sha(HERE / "compute.py")
    assert freeze["verifier_sha256"] == sha(HERE / "verify.py")
    assert freeze["input_sha256"] == {key: sha(path) for key, path in INPUTS.items()}
    assert result["freeze_sha256"] == sha(HERE / "freeze.json")
    assert result["input_sha256"] == freeze["input_sha256"]
    curve = "EC1N131Ckb1h6816f880945e"
    assert result["curve_id"] == freeze["curve_id"] == curve
    assert result["proposal_id"] == "Q1422"
    assert result["candidate_id"] is None and result["run_id"] is None
    assert result["isogeny"] == "none" and result["isogeny_stage_code"] == "ISO0"
    protocol = records["base_protocol"]
    base = records["base_receipt"]
    replay = records["sage_replay"]
    query = records["query_bound"]
    pair = records["pair_screen"]
    n = base["field_degree_n"]
    r = protocol["instances"]["131"]["subgroup_order"]
    assert n == 131 and all(x["curve_id"] == curve for x in (base, replay, query, pair))
    assert replay["status"] == "PASS" and replay["independent_subgroup_checks"] == 16
    assert pair["subgroup_order_r"] == r
    assert (r - 1) % (2 * n) == 0
    u = (r - 1) // (2 * n)
    k = base["signed_frobenius_columns_K"]
    b = base["actual_usable_points_B_before_folding"]
    assert b == 2 * n * k
    assert (b, k) == (result["actual_usable_points_B"], result["actual_folded_columns_K"])
    assert base["enumerated_set_sha256"] == result["factor_base_enumerated_set_sha256"]
    assert pair["base_set_sha256"] == query["base_set_sha256"] == base["enumerated_set_sha256"]
    assert check_small_domains() == 8316
    switch = int(result["cap_to_free_switch_K"])
    assert 2 * (switch - 1) * (n * (switch - 1) + 1) ** 2 < u
    assert 2 * switch * (n * switch + 1) ** 2 >= u
    derivative = int(result["convex_derivative_first_nonnegative_K"])
    sign = lambda x: 2 * (2 * n * x + 1) * (n * x + 1) ** 2 - n * u
    assert k < derivative < switch
    assert sign(derivative - 1) < 0 <= sign(derivative)
    actual = result["exact_base_index_action_floor"]
    assert int(actual["K"]) == k
    assert int(actual["M"]) == k * (n * k + 1)
    actual_cost = check_row(actual, n, u)
    candidates = result["certifying_global_candidates"]
    assert [int(x["K"]) for x in candidates] == [derivative - 1, derivative, switch]
    global_cost = min(check_row(x, n, u) for x in candidates)
    best = result["global_relaxed_index_action_floor"]
    assert check_row(best, n, u) == global_cost
    assert global_cost <= actual_cost
    assert result["q1416_conditional_K_row_pair_probe_model_log2"] == pair[
        "K_rows_pair_probes_model_log2"]
    assert result["q1414_necessary_uniform_queries_for_half_rank"] == query[
        "query_bounds"]["rank_success_50_percent"]["minimum_uniform_nonidentity_queries"]
    assert result["complete_cold_field_calls_log2"] is None
    assert result["complete_online_one_target_field_calls_log2"] is None
    report = {
        "schema": "q1422-global-index-verification-v1",
        "status": "PASS_EXACT_BASE_AND_INTEGER_OPTIMUM",
        "small_domain_cases": 8316,
        "exact_base_B": b, "exact_base_K": k,
        "exact_base_actions": str(actual_cost),
        "global_relaxed_actions": str(global_cost),
        "freeze_sha256": sha(HERE / "freeze.json"),
        "result_sha256": sha(HERE / "result.json"),
        "verifier_sha256": sha(HERE / "verify.py"),
    }
    (HERE / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "small_domain_cases": 8316}, sort_keys=True))


if __name__ == "__main__":
    main()
