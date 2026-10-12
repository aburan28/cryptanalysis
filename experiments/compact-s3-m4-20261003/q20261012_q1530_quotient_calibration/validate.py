#!/usr/bin/env python3
"""Independently verify Q1530 frozen inputs and finite work arithmetic."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    assert protocol["proposal_id"] == analysis["proposal_id"] == "Q1530"
    assert protocol["candidate_id"] is None and protocol["run_id"] is None
    assert protocol["isogeny"] == analysis["isogeny"] == "none"
    assert sha(HERE / "protocol.json") == analysis["protocol_sha256"]
    assert sha(HERE / "analyze.py") == analysis["source_sha256"]
    sources = {}
    for name, record in protocol["source_records"].items():
        path = PARENT / record["relative_path"]
        assert sha(path) == record["sha256"]
        sources[name] = json.loads(path.read_text())
    full, part = sources["n53_full_measurement"], sources["n53_ordinary_measurement"]
    full_p = sources["n53_full_protocol"]
    r53, b53 = int(full_p["subgroup_order"]), full_p["factor_base_actual_B"]
    full_hits = len({row[0] for row in full["matches"]})
    assert full_hits == 399 and full["query_samples_processed"] == 30000000
    assert sources["n53_ordinary_analysis"]["matched_query_positions"] == 11
    assert part["table_samples"] == 2000000
    assert full["table_distinct_keys"] == 2730335
    assert part["table_distinct_keys"] == 1418520
    for row, hits, queries, keys in zip(
        analysis["calibration"], [399, 11], [30000000, 1500000],
        [2730335, 1418520]):
        expected_num = queries * b53*b53 * keys
        expected_den = 2*r53*2730335
        assert row["queries"] == queries and row["matched_query_positions"] == hits
        assert math.isclose(row["predicted_matched_positions_conditional"],
                            expected_num/expected_den, rel_tol=1e-14)
        assert row["wilson95"][0] <= row["predicted_match_probability_conditional"] <= row["wilson95"][1]
    old = sources["n131_q1526_sweep"]
    assert len(old["cells"]) == len(analysis["cells"]) == 84
    r131 = int(old["subgroup_order_r"])
    eligible = []
    for old_row, row in zip(old["cells"], analysis["cells"]):
        assert (old_row["B"], old_row["K"], old_row["table_fraction_binary_exponent"]) == (
            row["B"], row["K"], row["table_fraction_binary_exponent"])
        b, k, j = row["B"], row["K"], row["table_fraction_binary_exponent"]
        # Independently cross-multiply the rational T+(263/262)Q formula.
        numerator = 131*k*k*262*b*b + 526*k*r131*(2**(2*j))
        denominator = (2**j)*262*b*b
        exponent = math.log2(numerator) - math.log2(denominator)
        assert abs(row["quotient_reuse_pair_additions_log2"] - exponent) < 1e-9
        assert row["matrix_proxy_below_2pow61"] == (4*k*k < 2**61)
        if row["matrix_proxy_below_2pow61"]:
            eligible.append(row)
    best = min(eligible, key=lambda x: x["quotient_reuse_pair_additions_log2"])
    assert best == analysis["best_matrix_eligible_cell"]
    assert best["weight_bound"] == 7 and best["table_fraction_binary_exponent"] == 0
    assert best["quotient_reuse_pair_additions_log2"] > 61
    q1529 = sources["n83_q1529_measurement"]
    assert abs(best["quotient_reuse_pair_additions_log2"] -
               q1529["conditional_N131_W7_quotient_reuse_pair_additions_log2"]) < 1e-9
    proof = json.loads((HERE / "lean/proof_receipt.json").read_text())
    for file, key in (("Calibration.lean", "source_sha256"),
                      ("build.stdout.txt", "stdout_sha256"),
                      ("build.stderr.txt", "stderr_sha256")):
        assert sha(HERE / "lean" / file) == proof[key]
    assert not (HERE / "lean/build.stderr.txt").read_text()
    assert (HERE / "lean/build.stdout.txt").read_text().count("does not depend on any axioms") == 4
    print("PASS Q1530: frozen sources, N53 calibration, 84 cells, Lean proof")


if __name__ == "__main__":
    main()
