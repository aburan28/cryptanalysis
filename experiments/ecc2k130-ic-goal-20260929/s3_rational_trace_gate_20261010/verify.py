#!/usr/bin/env python3
"""Bind the frozen N41/N131 trace audit and its terminal measurements."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sources = {"audit.py": HERE / "audit.py",
           "arithmetic_snapshot.py": ROOT / "n41_two_free_pair_occupancy_20261009/arithmetic_snapshot.py",
           "n41_screen.json": ROOT / "n41_n131_diagonal_atom_20261010/screen.json",
           "mixed_inputs.json": ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json",
           "n131_index.bin": ROOT / "n131_mixed_s3_stream64_20261010/index.bin",
           "n131_index_setup.json": ROOT / "n131_mixed_s3_stream64_20261010/setup.json"}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
protocol = json.loads((HERE / "protocol.json").read_text())
result = json.loads((HERE / "result.json").read_text())
assert protocol["source_sha256"] == {name: sha(path) for name, path in sources.items()}
assert result["protocol_sha256"] == sha(HERE / "protocol.json")
assert result["status"] == "PASS_S3_RATIONAL_TRACE_SUPPORT_GATE"
assert result["wall_ns"] < protocol["cap_seconds"] * 10**9
assert result["peak_process_rss_bytes"] < protocol["rss_cap_bytes"]
assert result["n41"]["signed_pair_states"] == 1956
assert result["n41"]["distinct_outputs_per_rotation"] == [978, 978]
for row in result["n41"]["cases"].values():
    assert row["target_trace_bit"] == 0
    assert row["rational_left_coordinates"] == 978
    assert row["one_distinct_s3_root"] == 0
    assert row["two_distinct_s3_roots"] == 978
assert result["n131"]["left_entries"] == 264202
assert result["n131"]["left_trace_bit_counts"] == [264202, 0]
assert result["n131"]["independent_trace_samples"] == 192
assert all(row["target_trace_bit"] == 0
           for row in result["n131"]["cases"].values())
receipt = {"status": "PASS_S3_RATIONAL_TRACE_TERMINAL_AUDIT",
           "source_sha256": {"verify.py": sha(Path(__file__)),
                             "protocol.json": sha(HERE / "protocol.json"),
                             "result.json": sha(HERE / "result.json")},
           "n41_local_s3_root_checks": 1956,
           "n131_packed_trace_flags": 264202,
           "n131_independent_trace_samples": 192}
(HERE / "terminal_audit.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": receipt["status"]}, sort_keys=True))
