#!/usr/bin/env python3
"""Rerunnable audit of frozen W14 pair inverse and independent replay."""
import hashlib
import json
from pathlib import Path

import freeze

HERE = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
protocol = json.loads((HERE / "protocol.json").read_text())
inputs = json.loads((HERE / "inputs.json").read_text())
result = json.loads((HERE / "result.json").read_text())
sage = json.loads((HERE / "sage_audit.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_PAIR_QUERIES"
assert protocol["source_sha256"] == {name: sha(path)
                                      for name, path in freeze.sources().items()}
assert protocol["inputs_sha256"] == sha(HERE / "inputs.json")
assert inputs["status"] == "FROZEN_INPUTS"
assert len(inputs["positives"]) == 32 and len(inputs["controls"]) == 34
assert result["status"] == "PASS_EXACT_W14_JOINT_PAIR_INVERSE_CONTROLS"
assert result["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
assert result["source_sha256"]["inputs"] == sha(HERE / "inputs.json")
assert result["same_rotation_product_span_rank"] == 27
assert result["adjacent_rotation_product_span_rank"] == 131
assert result["joint_column_count"] == 41
assert result["status_histogram"] == {"PAIR": 32, "SPAN_REJECT": 32,
                                      "EXCEPTIONAL": 2}
assert result["rank_histogram"] == {"41": 64, "None": 2}
assert result["total_wall_ns"] <= protocol["wall_cap_seconds"]*10**9
assert result["peak_process_rss_bytes"] <= protocol["rss_cap_bytes"]
for row in result["queries"]:
    if row["kind"] == "positive":
        fixture = inputs["positives"][row["input_index"]]
        assert row["pairs"] == [sorted(fixture["masks"])]
    else:
        assert row["pairs"] == []
assert [(item["kind"], item["pair_count"], item["seed_sums_full_scan"])
        for item in result["comparisons"]] == [
            ("positive", 1, 16383), ("uniform_field", 0, 16383)]
assert sage["status"] == "PASS_INDEPENDENT_SAGE_W14_JOINT_RANK_AND_GROUP_REPLAY"
assert sage["checked_positive_outputs"] == 32
assert sage["checked_uniform_span_rejects"] == 32
assert sage["source_sha256"]["result"] == sha(HERE / "result.json")
receipt = {"status": "PASS_FROZEN_W14_PAIR_INVERSE_AND_SAGE_AUDIT",
           "source_commit": "6bab4147",
           "curve_id": protocol["curve_id"],
           "actual_factor_base_points_B": protocol["actual_factor_base_points_B"],
           "effective_folded_columns_K": protocol["effective_folded_columns_K"],
           "same_rotation_product_span_rank": 27,
           "adjacent_rotation_product_span_rank": 131,
           "positive_outputs": 32, "uniform_span_rejects": 32,
           "source_sha256": {"script": sha(__file__),
                             "protocol": sha(HERE / "protocol.json"),
                             "inputs": sha(HERE / "inputs.json"),
                             "result": sha(HERE / "result.json"),
                             "sage": sha(HERE / "sage_audit.json")}}
path = HERE / "terminal_audit.json"
if path.exists():
    assert json.loads(path.read_text()) == receipt
else:
    with path.open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
print(json.dumps({"status": receipt["status"],
                  "positive_outputs": receipt["positive_outputs"]}))
