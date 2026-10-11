"""Compare dense-kernel transfer diagnostics for the two exact emitters."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n41_single_branch_joint_sat_20261011"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    query = json.loads((HERE / "query_result.json").read_text())
    baseline = json.loads((OLD / "query_result.json").read_text())
    dense = json.loads((OLD / "projection_result.json").read_text())
    assert query["target"] == baseline["target"]
    assert query["status"] == baseline["status"] == "BOUNDED_UNKNOWN"
    n131 = dense["one_dense_field_multiplication"]["n131"]
    calls = query["formula"]["quartic_field_multiplications"]
    old_calls = baseline["formula"]["quartic_field_multiplications"]
    assert calls == 159 and old_calls == 312
    result = {"status": "COMPLETE_PAIRED_ARITHMETIC_WIDTH_DIAGNOSTIC",
              "same_public_target": query["target"],
              "factor_base_B_n41": 384, "folded_columns_K_n41": 26,
              "factor_base_B_n131": 197292, "folded_columns_K_n131": 16381,
              "quartic_field_multiplications": {"factored": calls, "baseline": old_calls},
              "n41_full_and_gates": {"factored": query["formula"]["and_gates"],
                                      "baseline": baseline["formula"]["and_gates"]},
              "one_dense_n131_field_multiplication": n131,
              "all_dense_n131_quartic_kernel_estimate": {
                  "factored_AND": calls * n131["and_gates"],
                  "baseline_AND": old_calls * n131["and_gates"],
                  "note": "Diagnostic only; actual structured operand gates, whole formula, memory, and solver cost remain unmeasured at N131."},
              "public_N41_status": query["status"],
              "n131_public_promotion_gate": "NOT_ESTABLISHED",
              "source_sha256": {"projection.py": sha(Path(__file__)),
                                "factored_query_result.json": sha(HERE / "query_result.json"),
                                "baseline_query_result.json": sha(OLD / "query_result.json"),
                                "dense_reference.json": sha(OLD / "projection_result.json")}}
    (HERE / "projection_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "factored_dense_AND_diagnostic": result["all_dense_n131_quartic_kernel_estimate"]["factored_AND"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
