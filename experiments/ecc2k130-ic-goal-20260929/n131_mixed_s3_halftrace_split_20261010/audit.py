#!/usr/bin/env python3
"""Bind the paired panel, exact root audit, and source-bound work counts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010"
COUNT = ROOT / "n131_w14_fixed_seed_support_gate_20261010/result_bounds.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


protocol = json.loads((HERE / "protocol.json").read_text())
result = json.loads((HERE / "result.json").read_text())
identity = json.loads((HERE / "identity_audit.json").read_text())
assert result["status"] == "PASS_PAIRED_TARGET_SPLIT_HALFTRACE_PANEL"
assert result["protocol_sha256"] == sha(HERE / "protocol.json")
assert identity["status"] == "PASS_ALL_SPLIT_ROOT_COMPARISONS"
assert len(identity["cases"]) == 4
assert all(row["checked"] == 1026 for row in identity["cases"])
assert len(result["trials"]) == len(protocol["run_order"]) == 16

summary = {}
for n in (41, 131):
    for case in ("positive", "trace_zero_control"):
        panel = [row for row in result["trials"]
                 if row["field_degree"] == n and row["case"] == case]
        assert [row["variant"] for row in panel] == [
            "baseline", "split", "split", "baseline"]
        reference = panel[0]["result"]
        for row in panel:
            label = row["label"]
            raw = HERE / f"{label}.json"
            stdout = HERE / f"{label}.stdout.txt"
            stderr = HERE / f"{label}.stderr.txt"
            assert sha(raw) == row["result_sha256"]
            assert sha(stdout) == row["stdout_sha256"]
            assert sha(stderr) == row["stderr_sha256"]
            assert json.loads(raw.read_text()) == row["result"]
            assert row["returncode"] == 0
            assert row["result"]["status"] == "COMPLETE_ALGEBRAIC_SCAN"
            assert row["result"]["hits"] == reference["hits"]
            assert row["result"]["left_outputs_checked"] == reference["left_outputs_checked"]
            assert row["result"]["peak_rss_bytes"] < protocol["rss_cap_bytes"]
            assert row["parent_ns"] < 35 * 10**9
        baseline = [row["result"]["query_ns"] for row in panel
                    if row["variant"] == "baseline"]
        split = [row["result"]["query_ns"] for row in panel
                 if row["variant"] == "split"]
        summary[f"n{n}_{case}"] = {
            "baseline_query_ns": baseline,
            "split_query_ns": split,
            "split_batch_inverse_terms": [row["result"]["batch_inverse_terms"]
                                          for row in panel if row["variant"] == "split"],
            "hits": len(reference["hits"]),
            "left_outputs_checked": reference["left_outputs_checked"]}

count = json.loads(COUNT.read_text())["n131"]
# The exact mask-pair census is already an archived, independently audited
# count; the streaming byte expression is a proposed packed record format.
pair_count = 33780028
assert count["usable_unordered_mask_pairs"] == pair_count
assert count["seed_count"] == 16383
assert count["fixed_seed_unordered_mask_pairs"] == 2062
output_entries_upper = 2 * pair_count
packed_bytes_upper = output_entries_upper * (17 + 17 + 4 + 17 + 4)
assert output_entries_upper == 67560056
assert packed_bytes_upper == 3986043304
receipt = {
    "status": "PASS_TARGET_SPLIT_HALFTRACE_AUDIT",
    "candidate_id": None,
    "source_sha256": {
        "audit.py": sha(Path(__file__)),
        "protocol.json": sha(HERE / "protocol.json"),
        "result.json": sha(HERE / "result.json"),
        "identity_audit.json": sha(HERE / "identity_audit.json"),
        "audit_roots.cpp": sha(HERE / "audit_roots.cpp"),
        "audit_roots": sha(HERE / "audit_roots"),
        "archived_pair_count.json": sha(COUNT),
        "mixed_inputs.json": sha(BASE / "inputs.json")},
    "summary": summary,
    "source_bound_projection": {
        "status": "UNMEASURED_ALL_SEED_STREAM_PROJECTION",
        "usable_unordered_mask_pairs": pair_count,
        "nonzero_seed_count": 16383,
        "pair_output_entries_per_rotation_upper": output_entries_upper,
        "proposed_packed_two_rotation_bytes_upper": packed_bytes_upper,
        "record_layout_bytes": {"left_coordinate": 17,
                                "left_halftrace": 17,
                                "left_mask_pair": 4,
                                "right_coordinate": 17,
                                "right_mask_pair": 4}}}
(HERE / "terminal_audit.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": receipt["status"],
                  "n131_positive": summary["n131_positive"]}, sort_keys=True))
