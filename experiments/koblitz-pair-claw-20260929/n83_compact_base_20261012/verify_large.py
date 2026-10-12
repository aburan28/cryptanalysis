#!/usr/bin/env python3
"""Check the large-base construction, independent log replay, and stage parity."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    base = read("large_base.json")
    replay = read("large_base_sage_replay.json")
    stage = read("large_stage.json")
    parent = PAIR / "runs/n83_knownlog_orbit_base_k48194.json"
    data = HERE / "large_base_keys_and_logs.bin"
    assert base["K"] == 200000
    assert base["actual_usable_points_B_before_folding"] == 33200000
    assert base["pair_rank_domain"] == 3319983400000
    assert base["verified_parent_K"] == 48194
    assert base["parent_receipt_sha256"] == sha(parent)
    assert base["key_and_log_file_sha256"] == sha(data)
    assert data.stat().st_size == 32 * base["K"]
    for name, digest in base["source_sha256"].items():
        if name == "builder":
            assert sha(HERE / "build_large_base.py") == digest
        elif name == "orbit_key":
            assert sha(PAIR / "orbit_key.py") == digest
        else:
            assert sha(PAIR.parents[1] / "ecc2k130/runner/codegen" / f"{name}.py") == digest
    assert replay["status"] == "PASS"
    assert replay["K"] == base["K"]
    assert replay["B"] == base["actual_usable_points_B_before_folding"]
    assert replay["every_canonical_log_replayed"] is True
    assert replay["key_file_sha256"] == sha(data)
    assert replay["base_receipt_sha256"] == sha(HERE / "large_base.json")
    assert replay["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert replay["verifier_source_sha256"] == sha(HERE / "verify_large_sage.py")
    assert stage["status"] == "PASS"
    assert stage["K"] == base["K"]
    assert stage["B"] == base["actual_usable_points_B_before_folding"]
    parent_protocol = PAIR / "n83_fresh_m32_k23859_20261012/protocol.json"
    frozen_target = json.loads(parent_protocol.read_text())
    assert stage["parent_protocol_sha256"] == sha(parent_protocol)
    assert stage["workload_id"] == frozen_target["workload_id"]
    assert stage["large_base_receipt_sha256"] == sha(HERE / "large_base.json")
    assert stage["base_file_sha256"] == sha(data)
    assert stage["compact_source_sha256"] == sha(HERE / "compact_base.inc")
    assert stage["generator_source_sha256"] == sha(HERE / "generate.py")
    assert stage["driver_source_sha256"] == sha(HERE / "run_large_stage.py")
    assert len(stage["cells"]) == 2
    assert [row["mode"] for row in stage["cells"]] == ["eager", "compact"]
    eager = read("large_eager.json")
    compact = read("large_compact.json")
    for row, result_name, result in zip(stage["cells"],
                                        ("large_eager.json", "large_compact.json"),
                                        (eager, compact)):
        assert row["returncode"] == 0
        assert row["result_sha256"] == sha(HERE / result_name)
        assert row["peak_rss_bytes"] == result["peak_rss_bytes"]
        assert result["actual_B"] == base["actual_usable_points_B_before_folding"]
    for key in stage["parity_fields"]:
        assert eager[key] == compact[key], key
    assert compact["peak_rss_bytes"] < eager["peak_rss_bytes"]
    audit = read("large_audit.json")
    audited = read("large_compact_audit.json")
    assert audit["status"] == "PASS"
    assert audit["K"] == base["K"]
    assert audit["B"] == base["actual_usable_points_B_before_folding"]
    assert audit["audit_define"] == "COMPACT_BASE_AUDIT=1"
    assert audit["base_receipt_sha256"] == sha(HERE / "large_base.json")
    assert audit["base_file_sha256"] == sha(data)
    assert audit["stage_receipt_sha256"] == sha(HERE / "large_stage.json")
    assert audit["parent_protocol_sha256"] == sha(parent_protocol)
    assert audit["compact_source_sha256"] == sha(HERE / "compact_base.inc")
    assert audit["driver_source_sha256"] == sha(HERE / "run_large_audit.py")
    assert audit["result_sha256"] == sha(HERE / "large_compact_audit.json")
    assert audit["native_returncode"] == 0
    for key in audit["parity_fields"]:
        assert audited[key] == compact[key], key
    print(json.dumps({"status": "PASS", "K": base["K"],
                      "B": base["actual_usable_points_B_before_folding"],
                      "eager_peak_rss_bytes": eager["peak_rss_bytes"],
                      "compact_peak_rss_bytes": compact["peak_rss_bytes"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
