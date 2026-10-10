#!/usr/bin/env python3
"""Freeze a corrected reader against the immutable version-one packed index."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SUPPORT = ROOT / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
LEGACY = ROOT / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
MIXED = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


prepare = json.loads((HERE / "prepare_protocol.json").read_text())
old_query = json.loads((HERE / "query_protocol.json").read_text())
setup = json.loads((HERE / "setup.json").read_text())
assert sha(HERE / "stream_v1.cpp") == prepare["source_sha256"]["stream.cpp"]
assert sha(HERE / "stream_v1") == prepare["source_sha256"]["stream"]
assert old_query["source_sha256"]["index.bin"] == sha(HERE / "index.bin")
assert setup["packed_bytes"] == (HERE / "index.bin").stat().st_size
assert setup["status"] == "COMPLETE_PACKED_SEED_PREPARE"
assert (HERE / "query_failure_v1.json").exists()
files = {name: HERE / name for name in
         ("stream.cpp", "stream", "stream_v1.cpp", "stream_v1",
          "freeze_query_v2.py", "run_query_v2.py", "compiler_version.txt",
          "prepare_protocol.json", "query_protocol.json", "setup.json",
          "index.bin", "query_failure_v1.json")}
files.update({"support_w14.tsv": SUPPORT, "legacy_native.cpp": LEGACY,
              "mixed_inputs.json": MIXED})
panel = json.loads(MIXED.read_text())["panels"]["131"]
protocol = {"status": "FROZEN_BEFORE_PACKED_SEED_QUERY_V2",
            "candidate_id": None, "seed_first": 1, "seed_last": 64,
            "case_order": ["positive", "trace_zero_control"],
            "target_z": {"positive": panel["positive_z"],
                         "trace_zero_control": panel["trace_zero_control_z"]},
            "worker_count": 1, "query_cap_seconds_per_case": 30,
            "rss_cap_bytes": 4294967296,
            "source_sha256": {name: sha(path) for name, path in files.items()}}
(HERE / "query_protocol_v2.json").write_text(
    json.dumps(protocol, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": protocol["status"]}, sort_keys=True))
