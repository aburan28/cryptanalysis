#!/usr/bin/env python3
"""Freeze the d10/m15 root-count correctness fix as a new IC candidate."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD_MANIFEST = HERE / "d10_m15_candidate_manifest_v1.json"
OLD_PROTOCOL = HERE / "d10_m15_single_target_protocol_v1.json"
NEW_MANIFEST = HERE / "d10_m15_candidate_manifest_v2.json"
NEW_PROTOCOL = HERE / "d10_m15_single_target_protocol_v2.json"
OLD_RUNNER = HERE / "run_d10_m15_single_target_v1.py"
NEW_RUNNER = HERE / "run_d10_m15_single_target.py"
DIAGNOSTIC = HERE / "diagnose_target_formula_counts_20261009.json"


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
        raise FileExistsError("v2 freeze already exists")
    old_manifest = json.loads(OLD_MANIFEST.read_text())
    old_protocol = json.loads(OLD_PROTOCOL.read_text())
    diagnostic = json.loads(DIAGNOSTIC.read_text())
    old_runner_hash = sha(OLD_RUNNER)
    new_runner_hash = sha(NEW_RUNNER)
    if (old_runner_hash != old_protocol["source_sha256"]["runner"] or
            new_runner_hash == old_runner_hash or
            diagnostic["cases"]["official_q"]["roots"] != 1834 or
            diagnostic["cases"]["precomputation_001"]["roots"] != 1834 or
            diagnostic["expected_official_q"]["roots"] != 524):
        raise ValueError("v1 archive or independent root-count diagnostic differs")

    manifest = replace_hash(old_manifest, old_runner_hash, new_runner_hash)
    core = manifest["candidate_record"]
    counts = core["point_decomposition"]["formula_counts"]
    if counts != diagnostic["expected_official_q"]:
        raise ValueError("candidate formula counts differ from frozen formula receipt")
    counts["chain_equation_roots"] = 1834
    counts["roots_field_meaning"] = "four cofactor endpoints times 131 coordinate bits"
    identity = hashlib.sha256(canonical(core).encode()).hexdigest()
    candidate_id = (
        "IC1N131Ckb1fb%dPDP15satRCdirectLAgaussTDdirectISO0h%s" %
        (core["factor_base"]["actual_usable_points_before_sign_frobenius_folding"],
         identity[:12]))
    manifest["candidate_id"] = candidate_id
    manifest["candidate_identity_sha256"] = identity
    manifest["kind"] = "ecc2k130_sparse_seed_d10_m15_candidate_manifest_v2"
    manifest["provenance"]["correctness_fix"] = {
        "failed_run_id": (old_protocol["candidate_id"] + "W" +
                          old_protocol["workload_id"] + "R1"),
        "v1_runner_sha256": old_runner_hash,
        "root_count_diagnostic_sha256": sha(DIAGNOSTIC),
        "description": "The v1 formula receipt's roots field counts endpoint coordinate bits; the returned roots list counts fourteen 131-bit chain equations.",
    }
    NEW_MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")

    protocol = replace_hash(old_protocol, old_runner_hash, new_runner_hash)
    protocol["candidate_id"] = candidate_id
    protocol["candidate_manifest_sha256"] = sha(NEW_MANIFEST)
    protocol["kind"] = "ecc2k130_sparse_seed_d10_m15_single_target_protocol_v2"
    protocol["predecessor_failed_run_id"] = (
        old_protocol["candidate_id"] + "W" + old_protocol["workload_id"] + "R1")
    protocol["root_count_validation"] = {
        "endpoint_coordinate_bits": 524,
        "chain_equation_roots": 1834,
        "ordinary_query_count": 1,
    }
    NEW_PROTOCOL.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "FROZEN", "candidate_id": candidate_id,
                      "manifest_sha256": sha(NEW_MANIFEST),
                      "protocol_sha256": sha(NEW_PROTOCOL)}))


if __name__ == "__main__":
    main()
