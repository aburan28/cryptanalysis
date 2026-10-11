"""Check source binding, capped query logs, and matched baseline dimensions."""

import gzip
import hashlib
import json
from pathlib import Path

from run import HERE, ROOT, save, sha, sources


def load(path):
    return json.loads(Path(path).read_text())


def main():
    protocol = load(HERE / "protocol.json")
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    control = load(HERE / "control_result.json")
    query = load(HERE / "query_result.json")
    arithmetic = load(HERE / "audit_result.json")
    orders = load(HERE / "order_search.json")
    baseline_dir = ROOT / "n41_single_branch_joint_sat_20261011"
    baseline_protocol = load(baseline_dir / "protocol.json")
    baseline = load(baseline_dir / "query_result.json")
    assert control["status"] == "PASS_FULL_N41_PUBLIC_WITNESS_ASSIGNMENT"
    assert arithmetic["status"] == "PASS_16_DIRECT_FIELD_EVALUATIONS"
    assert orders["rows"][0]["order"] == [1, 2, 0, 4, 3]
    assert protocol["target_q"] == baseline_protocol["target_q"]
    for key in ("workers", "construction_cap_seconds", "solver_cap_seconds",
                "rss_cap_bytes", "solver_flags", "source_mask_counts",
                "factor_base_B", "folded_columns_K"):
        assert protocol[key] == baseline_protocol[key], key
    assert query["status"] == baseline["status"] == "BOUNDED_UNKNOWN"
    assert query["solver_started"] and query["solver_timed_out"]
    assert query["solver_returncode"] == -9 and not query["primary_model_saved"]
    assert not query["solver_rss_exceeded"]
    assert abs(sum(query["phase_seconds"][key] for key in
                   ("construction", "write_and_hash", "solver")) -
               query["phase_seconds"]["total"]) < 0.05
    for label in ("stdout", "stderr"):
        path = HERE / f"solver.{label}.gz"
        raw = gzip.open(path, "rb").read()
        assert sha(path) == query[f"{label}_gzip_sha256"]
        assert hashlib.sha256(raw).hexdigest() == query[f"{label}_sha256"]
        if label == "stdout":
            assert b"c rst  geom" in raw
            assert not any(line.startswith(b"s ") for line in raw.splitlines())
    keys = ("quartic_field_multiplications", "quartic_field_squares", "variables",
            "and_gates", "clauses", "native_xor_rows", "bytes")
    comparison = {key: {"baseline": baseline["formula"][key],
                        "horner": query["formula"][key]}
                  for key in keys}
    assert comparison["quartic_field_multiplications"] == {
        "baseline": 312, "horner": 165}
    assert query["formula"]["quartic_field_multiplications"] == 3 * (
        arithmetic["quartic_field_multiplications_per_block"] + 1)
    assert query["formula"]["quartic_field_squares"] == 3 * (
        arithmetic["quartic_field_squares_per_block"])
    record = {"status": "PASS_SOURCE_LOG_PHASE_AND_MATCHED_DIMENSION_AUDIT",
              "target": protocol["target_q"], "comparison": comparison,
              "query_status": query["status"],
              "solver_seconds": query["phase_seconds"]["solver"],
              "source_sha256": {name: sha(HERE / name) for name in (
                  "protocol.json", "control_result.json", "query_result.json",
                  "audit_result.json", "order_search.json", "verify_receipts.py")}}
    save(HERE / "terminal_audit.json", record)
    print(json.dumps({"status": record["status"], "comparison": comparison},
                     sort_keys=True))


if __name__ == "__main__":
    main()
