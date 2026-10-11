#!/usr/bin/env python3
"""Canonical N41 candidate IDs and archived-target diagnostic run records."""

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n41_coupled_sixpair_full_ic_20261010"
PREFIX = "IC1N41Ckb1fb384PDP12mitmRCsampleLAgaussTDdirectISO0h"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def save(name, value):
    with (HERE / name).open("x") as out:
        json.dump(value, out, sort_keys=True, indent=2)
        out.write("\n")


def main():
    prior = json.loads((PRIOR / "candidate_manifest.json").read_text())
    workload = json.loads((PRIOR / "fresh/canonical_workload.json").read_text())
    assert workload["workload_id"] == hashlib.sha256(canonical(workload["identity_record"])).hexdigest()[:12]
    helper = HERE.parent / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
    # Existing identity already binds the audited relation-preparation code.
    shared_hashes = prior["identity_record"]["implementation"]["source_and_binary_sha256"]
    shared_hashes = {key: value for key, value in shared_hashes.items()
                     if key in ("collection_join_binary", "collection_join_cpp",
                                "collector_python", "factor_log_audit_sage",
                                "native_curve_helper_cpp")}
    assert shared_hashes["native_curve_helper_cpp"] == digest(helper)
    variants = (
        ("unbatched", "orbit_worker.cpp", "orbit_worker", "protocol.json",
         "audit_sage.py", "native.json", "hit.json"),
        ("batch", "orbit_worker_batch.cpp", "orbit_worker_batch", "batch_protocol.json",
         "audit_batch.py", "batch_native.json", "batch_hit.json"),
    )
    records = []
    for label, source, binary, protocol, audit, native, hit in variants:
        identity = copy.deepcopy(prior["identity_record"])
        identity["point_decomposition"].update({
            "implementation": "native_cpp17_arm64_frobenius_orbit" + ("_batch_inverse" if label == "batch" else ""),
            "source_sha256": digest(HERE / source),
            "summation_chain": "six signed W6 pair lists with two same-seed right blocks; sample one right-block product and match its complement against all 41 Frobenius conjugates of the public target in the reusable left index",
        })
        identity["target_descent"].update({
            "policy": "direct twelve-point relation for one target conjugate; multiply prepared factor-log sum by the inverse Frobenius eigenvalue power and replay original target",
            "source_sha256": digest(HERE / source),
        })
        identity["implementation"] = {
            "algorithm_flags": ["-std=c++17", "-O3", "-Wall", "-Wextra"],
            "compiler": "Apple clang arm64 C++17",
            "source_and_binary_sha256": {
                **shared_hashes,
                "orbit_worker_cpp": digest(HERE / source),
                "orbit_worker_binary": digest(HERE / binary),
                "orbit_protocol": digest(HERE / protocol),
                "orbit_audit": digest(HERE / audit),
            },
        }
        full = hashlib.sha256(canonical(identity)).hexdigest()
        candidate_id = PREFIX + full[:12]
        save(f"candidate_{label}.json", {
            "candidate_id": candidate_id,
            "identity_sha256": full,
            "identity_record": identity,
        })
        measurement = json.loads((HERE / native).read_text())
        assert measurement["status"] == "VERIFIED_SCALAR"
        assert sum(measurement["exclusive_phase_ns"].values()) == measurement["online_ns"]
        records.append({
            "candidate_id": candidate_id,
            "workload_id": workload["workload_id"],
            "run_id": f"{candidate_id}W{workload['workload_id']}R1",
            "curve_id": workload["curve_id"],
            "target": workload["identity_record"]["targets"][0],
            "target_count": 1,
            "workload_status": "archived_target_mechanism_diagnostic",
            "online_ns": measurement["online_ns"],
            "exclusive_phase_ns": measurement["exclusive_phase_ns"],
            "target_independent_setup_ns": measurement["setup_ns"],
            "accepted_right_samples": measurement["accepted_probes"],
            "charged_orbit_lookups": measurement["orbit_lookups"],
            "peak_rss_bytes": measurement["peak_rss_bytes"],
            "recovered_scalar": measurement["recovered_scalar"],
            "independent_relation_and_scalar_replay": True,
            "timing_class": "exploratory_unisolated_host",
            "promoted_online_speedup": None,
            "source_sha256": {
                "candidate_manifest": digest(HERE / f"candidate_{label}.json"),
                "workload_manifest": digest(PRIOR / "fresh/canonical_workload.json"),
                "native_result": digest(HERE / native),
                "hit": digest(HERE / hit),
            },
        })
    save("diagnostic_runs.json", {"status": "CANONICAL_ARCHIVED_TARGET_DIAGNOSTICS",
                                  "runs": records, "source_sha256": {"script": digest(__file__)}})
    print(json.dumps({"candidate_ids": [row["candidate_id"] for row in records],
                      "workload_id": workload["workload_id"]}))


if __name__ == "__main__":
    main()
