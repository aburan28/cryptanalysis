#!/usr/bin/env python3
"""Bind the batched orbit run to the independent Sage witness replay."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    protocol = read("batch_protocol.json")
    run = read("batch_run_receipt.json")
    native = read("batch_native.json")
    hit = read("batch_hit.json")
    baseline = read("native.json")
    sage = read("sage_audit.json")
    assert sage["status"] == "PASS_INDEPENDENT_ORBIT_RELATION_AND_SCALAR"
    assert sage["source_sha256"]["hit"] == digest(HERE / "hit.json")
    assert sage["source_sha256"]["native"] == digest(HERE / "native.json")
    assert sage["source_sha256"]["script"] == digest(HERE / "audit_sage.py")
    assert protocol["status"] == "FROZEN_BEFORE_BATCH_QUERY"
    for key, path in protocol["source_paths"].items():
        assert protocol["source_sha256"][key] == digest(path), key
    for name in ("batch_protocol", "batch_hit", "batch_native", "batch_stdout", "batch_stderr"):
        suffix = ".txt" if name.endswith(("stdout", "stderr")) else ".json"
        assert run[f"{name}_sha256"] == digest(HERE / (name + suffix))
    assert native["status"] == run["status"] == "VERIFIED_SCALAR"
    assert run["exit_code"] == 0
    assert protocol["target"] == run["target"] == hit["original_target"]
    assert digest(HERE / "batch_hit.json") == digest(HERE / "hit.json")
    assert native["recovered_scalar"] == baseline["recovered_scalar"] == sage["recovered_scalar"]
    assert native["orbit_index"] == baseline["orbit_index"] == sage["orbit_index"]
    assert native["accepted_probes"] == baseline["accepted_probes"] == run["accepted_right_samples"]
    assert native["orbit_lookups"] == baseline["orbit_lookups"] == run["orbit_lookups"]
    assert native["group_hits"] == baseline["group_hits"]
    assert native["column_rejects"] == baseline["column_rejects"]
    assert sum(native["exclusive_phase_ns"].values()) == native["online_ns"] == run["online_ns"]
    assert native["peak_rss_bytes"] <= protocol["rss_cap_bytes"]
    receipt = {
        "status": "PASS_BATCH_EQUIVALENCE_AND_SAGE_BOUND_WITNESS",
        "online_ns": native["online_ns"],
        "baseline_unbatched_online_ns": baseline["online_ns"],
        "orbit_lookups": native["orbit_lookups"],
        "recovered_scalar": native["recovered_scalar"],
        "source_sha256": {name: digest(HERE / name) for name in (
            "audit_batch.py", "batch_protocol.json", "batch_run_receipt.json",
            "batch_native.json", "batch_hit.json", "sage_audit.json")},
    }
    with (HERE / "batch_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({k: receipt[k] for k in ("status", "online_ns", "orbit_lookups")}))


if __name__ == "__main__":
    main()
