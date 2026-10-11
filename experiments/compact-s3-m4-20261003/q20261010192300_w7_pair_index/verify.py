#!/usr/bin/env python3
"""Independent exact-integer replay of fixed-index action scenarios."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    freeze = json.loads((HERE / "freeze.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    assert result["freeze_sha256"] == sha(HERE / "freeze.json")
    assert result["candidate_id"] is result["run_id"] is None
    assert result["curve_id"] == freeze["curve_id"] == (
        "EC1N131Ckb1h6816f880945e")
    assert result["isogeny"] == freeze["isogeny"] == "none"
    for name, digest in freeze["source_sha256"].items():
        assert sha(HERE / name) == digest
    for name, digest in freeze["input_sha256"].items():
        assert sha(ROOT / name) == digest
    base = json.loads((PARENT / "q20261010190000_w7_frontier/run.json").read_text())
    q1413 = [json.loads((PARENT / f"runs/n131_q1413_projected_x_w{w}.json").read_text())
             for w in (5, 6)]
    rows = result["rows"]
    assert len(rows) == 6
    assert [row["weight_bound"] for row in rows] == [5, 6, 7, 7, 7, 8]
    assert [row["K"] for row in rows[:2]] == [item[
        "signed_frobenius_columns_K"] for item in q1413]
    r = int(freeze["prime_subgroup_order_r_decimal"])
    u = (r-1)//(2*131)
    assert u == int(result["canonical_key_universe_U_decimal"])
    assert rows[1]["necessary_insertions_plus_lookups_T"] == (
        freeze["q1422_exact_base_action_count"])
    interval = base["rows"][2]["B_interval_conditional"]
    assert rows[2]["K"] == math.floor(interval[0]/262)
    assert rows[3]["K"] == round(base["rows"][2][
        "folded_K_or_conditional_K"])
    assert rows[4]["K"] == math.ceil(interval[1]/262)
    assert rows[5]["K"] == round(base["rows"][3][
        "folded_K_or_conditional_K"])
    for row in rows:
        k = row["K"]
        maximum = min(u, k*(131*k+1))
        lookups = (k*u + 2*maximum-1)//(2*maximum)
        actions = maximum+lookups
        assert int(row["maximum_distinct_index_keys_M"]) == maximum
        assert int(row["half_success_necessary_lookups_L"]) == lookups
        assert int(row["necessary_insertions_plus_lookups_T"]) == actions
        assert math.isclose(row["log2_T"], math.log2(actions))
        assert math.isclose(row["gap_over_2pow61_log2"],
                            math.log2(actions)-61)
        assert maximum < math.isqrt(k*u//2)
    assert rows[2]["log2_T"] > rows[3]["log2_T"] > rows[4]["log2_T"]
    assert result["complete_solve_work_log2"] is None
    receipt = {"status": "PASS", "proposal_id": result["proposal_id"],
               "result_sha256": sha(HERE / "result.json"),
               "verifier_source_sha256": sha(__file__),
               "rows_checked": len(rows), "q1422_exact_control": True}
    path = HERE / "verification.json"
    assert not path.exists()
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
