#!/usr/bin/env python3
"""Validate Q1461 frozen target, scalar replay, candidate ID, and phase accounting."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SETUP = PARENT / "q20261011_n53_full_pipeline"
PAIR = PARENT / "q20261011_n53_native_pair"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    public = json.loads((HERE / "public_target.json").read_text())
    fixture = json.loads((HERE / "target_fixture.json").read_text())
    measured = json.loads((HERE / "native_measurement.json").read_text())
    recovery = json.loads((HERE / "recovery.json").read_text())
    manifest = json.loads((HERE / "candidate_manifest.json").read_text())
    pipeline = json.loads((HERE / "pipeline_receipt.json").read_text())
    setup_measure = json.loads((SETUP / "native_measurement.json").read_text())
    setup_replay = json.loads((SETUP / "independent_replay.json").read_text())
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert freeze["prepare_source_sha256"] == sha(HERE / "prepare.py")
    assert freeze["fixture_source_sha256"] == sha(HERE / "fixture.py")
    assert freeze["native_source_sha256"] == sha(HERE / "native_first.cpp")
    assert freeze["field_source_sha256"] == sha(PAIR / "native_field53.hpp")
    assert freeze["public_target_sha256"] == sha(HERE / "public_target.json")
    assert freeze["target_fixture_sha256"] == sha(HERE / "target_fixture.json")
    assert freeze["q1457_replay_sha256"] == sha(SETUP / "independent_replay.json")
    assert freeze["q1457_measurement_sha256"] == sha(SETUP / "native_measurement.json")
    assert build["freeze_sha256"] == measured["freeze_sha256"] == sha(HERE / "freeze.json")
    assert build["binary_sha256"] == sha(Path(build["binary_path"]))
    assert measured["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
    assert measured["raw_sha256"] == sha(HERE / "native_raw.json")
    assert measured["stderr_sha256"] == sha(HERE / "native_stderr.txt")
    assert measured["runner_sha256"] == sha(HERE / "run.py")
    assert recovery["measurement_sha256"] == sha(HERE / "native_measurement.json")
    assert recovery["setup_logs_sha256"] == sha(SETUP / "independent_replay.json")
    assert recovery["source_sha256"] == sha(HERE / "recover.py")
    assert setup_replay["status"] == "PASS" and setup_replay["matrix_rank"] == 227
    assert setup_replay["replayed_log_columns"] == 227
    assert measured["status"] == "first_match" and measured["return_code"] == 0
    assert recovery["status"] == "SCALAR_RECOVERED_AND_REPLAYED"
    assert recovery["scalar"] == fixture["scalar"] == pipeline["recovered_scalar"]
    assert public["workload_id"] == fixture["workload_id"] == pipeline["workload_id"]
    assert digest(fixture["workload_record"]) == fixture["workload_hash_full"]
    assert fixture["workload_hash_full"][:12] == public["workload_id"]
    assert pipeline["candidate_manifest_sha256"] == sha(HERE / "candidate_manifest.json")
    record = manifest["canonical_candidate_record"]
    assert digest(record) == manifest["canonical_candidate_sha256"]
    assert manifest["candidate_id"] == (
        "IC1N53Ckb1fb24062PDP4mitmRCenumLAgaussTDdirectISO0h" +
        manifest["canonical_candidate_sha256"][:12])
    curve = dict(record["curve"])
    curve_id = curve.pop("curve_id")
    assert digest({"field": record["field"], "curve": curve}) == manifest["curve_id_verified_sha256"]
    assert curve_id == protocol["curve_id"]
    assert pipeline["candidate_id"] == manifest["candidate_id"]
    assert pipeline["run_id"] == manifest["candidate_id"] + "W" + public["workload_id"] + "R1"
    assert pipeline["setup_query_count"] == setup_measure["query_samples_processed"] == 30000000
    assert pipeline["target_query_count"] == measured["native"]["query_samples_processed"]
    assert pipeline["setup_final_rank"] == 227 and pipeline["target_verified_relation_count"] >= 1
    charged = sum(pipeline["target_dependent_exclusive_phases_ns_exploratory"].values())
    assert charged == pipeline["target_online_phase_sum_ns_exploratory"]
    assert pipeline["contiguous_one_target_online_wall_ns"] is None
    assert pipeline["counted_pair_add_attempts_combined"] == (
        setup_measure["charged_pair_add_attempts"] + measured["charged_pair_add_attempts"])
    assert pipeline["complete_solve_work_log2"] is None
    assert pipeline["rho_online_ms"] is None and pipeline["online_speedup"] is None
    print("PASS Q1461", pipeline["candidate_id"],
          pipeline["target_query_count"], pipeline["target_online_phase_sum_ns_exploratory"])


if __name__ == "__main__":
    main()
