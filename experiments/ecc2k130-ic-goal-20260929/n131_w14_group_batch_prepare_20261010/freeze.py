#!/usr/bin/env python3
"""Freeze the native group-batch preparation before its 64-seed run."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_mixed_s3_stream64_20261010"
SUPPORT = HERE.parent / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
NATIVE = HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            digest.update(part)
    return digest.hexdigest()


def sources():
    return {"prepare_source": HERE / "prepare.cpp", "prepare_binary": HERE / "prepare",
            "freezer": HERE / "freeze.py", "runner": HERE / "run.py",
            "index_audit": HERE / "audit_index.py",
            "compiler_version": HERE / "compiler_version.txt",
            "field_source": NATIVE, "support": SUPPORT,
            "baseline_source": OLD / "stream.cpp", "baseline_binary": OLD / "stream",
            "baseline_index": OLD / "index.bin", "baseline_setup": OLD / "setup.json",
            "baseline_query_protocol": OLD / "query_protocol_v2.json",
            "baseline_positive": OLD / "positive_v2.json",
            "baseline_negative": OLD / "trace_zero_control_v2.json"}


def main():
    protocol = HERE / "protocol.json"
    assert not protocol.exists()
    setup = json.loads((OLD / "setup.json").read_text())
    query = json.loads((OLD / "query_protocol_v2.json").read_text())
    assert setup["status"] == "COMPLETE_PACKED_SEED_PREPARE"
    assert setup["seed_first"] == query["seed_first"] == 1
    assert setup["seed_last"] == query["seed_last"] == 64
    assert setup["usable_mask_pairs"] == 132101
    assert setup["entries_per_rotation"] == 264202
    assert (OLD / "index.bin").stat().st_size == setup["packed_bytes"]
    record = {"status": "FROZEN_GROUP_BATCH_PREPARE_64_SEEDS",
              "curve_id": "EC1N131Ckb1heb5f1998f20b", "candidate_id": None,
              "seed_first": 1, "seed_last": 64, "workers": 1,
              "prepare_cap_seconds": 120, "parent_cap_seconds": 130,
              "query_cap_seconds_per_case": 30,
              "rss_cap_bytes": 4*1024**3,
              "query_cases": query["target_z"],
              "source_sha256": {name: sha(path) for name, path in sources().items()}}
    with protocol.open("x") as stream:
        json.dump(record, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": record["status"], "sources": len(record["source_sha256"])}))


if __name__ == "__main__":
    main()
