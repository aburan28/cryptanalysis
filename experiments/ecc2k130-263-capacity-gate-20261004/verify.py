#!/usr/bin/env python3
"""Independently check every exact boundary and frozen-screen identity."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
SCREEN = ROOT / "experiments/ecc2k130-263-w-screen-20261004/evidence/run-r2/summary.json"
PROTOCOL_COMMIT = "41348c06286beec8d7f35c4556883224ed438eaf"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def choose_recurrence(n, k):
    if n < k:
        return 0
    value = 1
    for j in range(1, k + 1):
        value = value * (n - k + j) // j
    return value


def verify(path):
    if not __debug__:
        raise RuntimeError("verification assertions must remain enabled")
    config = json.loads(CONFIG.read_text())
    route = json.loads(ROUTE.read_text())
    frozen = json.loads(SCREEN.read_text())
    result = json.loads(path.read_text())
    assert digest(ROUTE) == config["route_manifest_sha256"]
    assert digest(SCREEN) == config["w_screen_summary_sha256"]
    assert result["schema"] == "ecc2k130_263_capacity_gate/v1"
    assert result["status"] == "exact_counting_complete"
    assert result["candidate_id"] is None
    assert result["route_id"] == route["route_id"] == config["route_id"]
    assert result["source_curve_id"] == route["curve_nodes"]["source"]["curve_id"]
    assert result["target_curve_id"] == route["curve_nodes"]["target"]["curve_id"]
    assert route["endomorphism"]["source_order_conductor"] == 1
    assert route["endomorphism"]["target_order_conductor"] == 263
    assert result["source_endomorphism_order_conductor"] == 1
    assert result["target_endomorphism_order_conductor"] == 263
    r = int(route["curve_nodes"]["source"]["subgroup_order"])
    assert r == int(route["curve_nodes"]["target"]["subgroup_order"])
    assert int(result["subgroup_order"]) == r
    residue_bytes = (r.bit_length() + 7) // 8
    assert result["subgroup_residue_bytes"] == residue_bytes
    assert result["input_sha256"] == {
        "CONFIG.json": digest(CONFIG),
        "route_manifest": digest(ROUTE),
        "w_screen_summary": digest(SCREEN),
        "derive.py": digest(HERE / "derive.py"),
    }
    assert result["protocol_commit"] == PROTOCOL_COMMIT
    assert result["source_main_commit"] == config["source_main_commit"]

    expected = [(m, threshold) for m in config["m_values"]
                for threshold in config["support_thresholds"]]
    assert len(result["rows"]) == len(expected)
    for row, (m, threshold) in zip(result["rows"], expected):
        assert row["summands"] == m
        n, d = threshold["numerator"], threshold["denominator"]
        assert (row["threshold_numerator"], row["threshold_denominator"]) == (n, d)
        b = row["minimum_actual_B"]
        assert isinstance(b, int) and b > 0
        before = choose_recurrence(b + m - 2, m)
        at = choose_recurrence(b + m - 1, m)
        assert before * d < (r - 1) * n <= at * d
        assert int(row["threshold_required_multisets"]) == ((r - 1) * n + d - 1) // d
        assert int(row["multisets_at_B_minus_one"]) == before
        assert int(row["multisets_at_B"]) == at
        sign = (b + 1) // 2
        orbit = (b + 261) // 262
        assert row["sign_only_columns_floor"] == sign
        assert row["sign_frobenius_columns_floor_if_orbit_closed"] == orbit
        assert row["sign_only_log_vector_bytes_floor"] == sign * residue_bytes
        assert row["orbit_closed_log_vector_bytes_floor"] == orbit * residue_bytes

    old = {(cell["dimension"], cell["capacity"]["summands"]): cell["capacity"]
           for cell in frozen["cells"]}
    assert len(result["w_cases"]) == len(config["w_cases"])
    for row, case in zip(result["w_cases"], config["w_cases"]):
        d, m = case["dimension"], case["summands"]
        assert (row["dimension"], row["summands"]) == (d, m)
        b_max = 2 * ((1 << d) - 1)
        ways = choose_recurrence(b_max + m - 1, m)
        assert row["projected_base_B_upper"] == b_max
        assert int(row["uniform_support_numerator_upper"]) == min(ways, r - 1)
        assert int(row["uniform_support_denominator"]) == r - 1
        assert row["below_one_percent"] is (ways * 100 < r - 1)
        assert row["upper_bound_is_saturated_at_one"] is (ways >= r - 1)
        assert row["reproduces_frozen_screen"] is ((d, m) in old)
        if (d, m) in old:
            assert old[(d, m)]["projected_base_B_upper"] == b_max
            assert old[(d, m)]["support_numerator_upper"] == min(ways, r - 1)
            assert old[(d, m)]["support_denominator"] == r - 1

    for key in ("natural_pdp_yield", "verified_relation_rank", "online_wall_time",
                "cold_wall_time", "verified_logarithm", "rho_ratio"):
        assert result[key] is None
    return {
        "schema": "ecc2k130_263_capacity_gate_verification/v1",
        "verified": True,
        "result_sha256": digest(path),
        "verifier_sha256": digest(Path(__file__)),
        "checked_threshold_rows": len(expected),
        "checked_w_cases": len(config["w_cases"]),
        "replayed_frozen_w_cases": len(old),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(args.result)
    with args.out.open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"verified": True,
                      "checked_threshold_rows": receipt["checked_threshold_rows"],
                      "checked_w_cases": receipt["checked_w_cases"]}))


if __name__ == "__main__":
    main()
