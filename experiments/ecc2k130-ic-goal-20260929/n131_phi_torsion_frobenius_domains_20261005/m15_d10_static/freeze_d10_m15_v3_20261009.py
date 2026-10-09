#!/usr/bin/env python3
"""Freeze the corrected d10/m15 RSS monitor under a new candidate ID."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD_MANIFEST = HERE / "d10_m15_candidate_manifest_v2.json"
OLD_PROTOCOL = HERE / "d10_m15_single_target_protocol_v2.json"
NEW_MANIFEST = HERE / "d10_m15_candidate_manifest_v3.json"
NEW_PROTOCOL = HERE / "d10_m15_single_target_protocol_v3.json"
OLD_RUNNER = HERE / "run_d10_m15_single_target_v2.py"
NEW_RUNNER = HERE / "run_d10_m15_single_target.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def replace_hash(value, old, new):
    if isinstance(value, dict):
        return {key: replace_hash(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_hash(item, old, new) for item in value]
    return new if value == old else value


def main():
    if NEW_MANIFEST.exists() or NEW_PROTOCOL.exists():
        raise FileExistsError("v3 freeze already exists")
    old_manifest = json.loads(OLD_MANIFEST.read_text())
    old_protocol = json.loads(OLD_PROTOCOL.read_text())
    old_hash, new_hash = sha(OLD_RUNNER), sha(NEW_RUNNER)
    if old_hash != old_protocol["source_sha256"]["runner"] or old_hash == new_hash:
        raise ValueError("v2 archive or v3 runner hash differs")
    old_run_id = (old_protocol["candidate_id"] + "W" +
                  old_protocol["workload_id"] + "R1")
    old_run = HERE / "single_target_runs" / old_run_id
    failure = json.loads((old_run / "failure.json").read_text())
    if (failure["status"] != "PRODUCER_FAILURE" or
            failure["error_type"] != "AttributeError" or
            "CryptoMiniSatCli" not in failure["error"]):
        raise ValueError("v2 predecessor did not preserve its failure")
    if ("e.CryptoMiniSatCli" not in OLD_RUNNER.read_text() or
            "e.CryptoMinisatCli" not in NEW_RUNNER.read_text()):
        raise ValueError("resource-monitor correction is absent")

    manifest = replace_hash(old_manifest, old_hash, new_hash)
    core = manifest["candidate_record"]
    identity = hashlib.sha256(canonical(core).encode()).hexdigest()
    candidate_id = (
        "IC1N131Ckb1fb%dPDP15satRCdirectLAgaussTDdirectISO0h%s" %
        (core["factor_base"]["actual_usable_points_before_sign_frobenius_folding"],
         identity[:12]))
    manifest["candidate_id"] = candidate_id
    manifest["candidate_identity_sha256"] = identity
    manifest["kind"] = "ecc2k130_sparse_seed_d10_m15_candidate_manifest_v3"
    manifest["provenance"]["resource_monitor_fix"] = {
        "failed_run_id": old_run_id,
        "v2_runner_sha256": old_hash,
        "description": "The v2 parent RSS monitor referenced the wrong case-sensitive class name; v3 calls the existing CryptoMinisatCli.processRssBytes method.",
    }
    NEW_MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")

    protocol = replace_hash(old_protocol, old_hash, new_hash)
    protocol["candidate_id"] = candidate_id
    protocol["candidate_manifest_sha256"] = sha(NEW_MANIFEST)
    protocol["kind"] = "ecc2k130_sparse_seed_d10_m15_single_target_protocol_v3"
    protocol["earlier_failed_run_ids"] = [old_protocol["predecessor_failed_run_id"],
                                          old_run_id]
    protocol["predecessor_failed_run_id"] = old_run_id
    NEW_PROTOCOL.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "FROZEN", "candidate_id": candidate_id,
                      "manifest_sha256": sha(NEW_MANIFEST),
                      "protocol_sha256": sha(NEW_PROTOCOL)}))


if __name__ == "__main__":
    main()
