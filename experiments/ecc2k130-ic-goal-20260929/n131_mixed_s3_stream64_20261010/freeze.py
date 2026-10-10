#!/usr/bin/env python3
"""Freeze the packed-index preparation and later the two fixed queries."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MIXED = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
SUPPORT = ROOT / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
LEGACY = ROOT / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


sources = {"stream.cpp": HERE / "stream.cpp", "stream": HERE / "stream",
           "freeze.py": Path(__file__), "run.py": HERE / "run.py",
           "compiler_version.txt": HERE / "compiler_version.txt",
           "support_w14.tsv": SUPPORT, "legacy_native.cpp": LEGACY,
           "mixed_inputs.json": MIXED}
if len(sys.argv) != 2 or sys.argv[1] not in ("prepare", "query"):
    raise SystemExit("usage: freeze.py prepare|query")
if sys.argv[1] == "prepare":
    record = {"status": "FROZEN_BEFORE_PACKED_SEED_PREPARE",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "field": "GF(2^131), t^131+t^13+t^2+t+1",
              "seed_first": 1, "seed_last": 64,
              "worker_count": 1, "setup_cap_seconds": 120,
              "rss_cap_bytes": 4294967296,
              "compiler_command": "clang++ -O3 -std=c++17 stream.cpp -o stream",
              "source_sha256": {name: sha(path) for name, path in sources.items()}}
    (HERE / "prepare_protocol.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n")
else:
    prepare = json.loads((HERE / "prepare_protocol.json").read_text())
    assert prepare["source_sha256"] == {
        name: sha(path) for name, path in sources.items()}
    setup = json.loads((HERE / "setup.json").read_text())
    assert setup["status"] == "COMPLETE_PACKED_SEED_PREPARE"
    assert [setup["seed_first"], setup["seed_last"]] == [1, 64]
    assert setup["packed_bytes"] == (HERE / "index.bin").stat().st_size
    panel = json.loads(MIXED.read_text())["panels"]["131"]
    record = {"status": "FROZEN_BEFORE_PACKED_SEED_QUERY",
              "candidate_id": None, "seed_first": 1, "seed_last": 64,
              "case_order": ["positive", "trace_zero_control"],
              "target_z": {"positive": panel["positive_z"],
                           "trace_zero_control": panel["trace_zero_control_z"]},
              "worker_count": 1, "query_cap_seconds_per_case": 30,
              "rss_cap_bytes": 4294967296,
              "source_sha256": {**prepare["source_sha256"],
                                "prepare_protocol.json": sha(HERE / "prepare_protocol.json"),
                                "setup.json": sha(HERE / "setup.json"),
                                "index.bin": sha(HERE / "index.bin")}}
    (HERE / "query_protocol.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": record["status"]}, sort_keys=True))
