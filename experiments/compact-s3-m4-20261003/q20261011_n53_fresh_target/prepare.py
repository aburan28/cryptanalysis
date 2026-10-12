#!/usr/bin/env python3
"""Freeze the fresh target's precomputed base and first five million queries."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
PAIR = PARENT / "q20261011_n53_native_pair"
SETUP = PARENT / "q20261011_n53_full_pipeline"
HORIZON = PARENT / "q20261011_n53_query_horizon"
SETUP_TEMP = Path("/private/tmp/q1457_n53_setup")
TEMP = Path("/private/tmp/q1461_n53_target")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not TEMP.exists() and not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    public = json.loads((HERE / "public_target.json").read_text())
    fixture = json.loads((HERE / "target_fixture.json").read_text())
    setup_replay = json.loads((SETUP / "independent_replay.json").read_text())
    setup_measure = json.loads((SETUP / "native_measurement.json").read_text())
    exported = json.loads((PAIR / "export_receipt.json").read_text())
    horizon = json.loads((HORIZON / "freeze.json").read_text())
    assert setup_replay["status"] == "PASS"
    assert setup_replay["factor_base_log_status"] == "solved_and_replayed"
    assert setup_replay["matrix_rank"] == protocol["factor_base_folded_columns_K"] == 227
    assert setup_replay["replayed_log_columns"] == 227
    assert setup_measure["status"] == "completed_query_cap"
    assert protocol["curve_id"] == public["curve_id"] == exported["curve_id"]
    assert public["workload_id"] == fixture["workload_id"]
    assert sha(SETUP_TEMP / "queries.bin") == json.loads((SETUP / "freeze.json").read_text())["query_file_sha256"]
    TEMP.mkdir()
    for name, record in exported["files"].items():
        if name == "queries.bin":
            continue
        source = PAIR / "inputs" / name
        assert sha(source) == record["sha256"]
        (TEMP / name).symlink_to(source)
    count = protocol["point_decomposition"]["target_query_cap"]
    with (SETUP_TEMP / "queries.bin").open("rb") as source, (TEMP / "queries.bin").open("wb") as target:
        remaining = count * 4
        digest = hashlib.sha256()
        while remaining:
            chunk = source.read(min(1048576, remaining))
            assert chunk
            target.write(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
    assert digest.hexdigest() == horizon["query_file_sha256"]
    freeze = {"proposal_id": "Q1461", "candidate_id": None,
              "curve_id": protocol["curve_id"], "isogeny": "none",
              "workload_id": public["workload_id"],
              "protocol_sha256": sha(HERE / "protocol.json"),
              "prepare_source_sha256": sha(Path(__file__)),
              "fixture_source_sha256": sha(HERE / "fixture.py"),
              "native_source_sha256": sha(HERE / "native_first.cpp"),
              "field_source_sha256": sha(PAIR / "native_field53.hpp"),
              "public_target_sha256": sha(HERE / "public_target.json"),
              "target_fixture_sha256": sha(HERE / "target_fixture.json"),
              "q1457_replay_sha256": sha(SETUP / "independent_replay.json"),
              "q1457_measurement_sha256": sha(SETUP / "native_measurement.json"),
              "q1454_export_sha256": sha(PAIR / "export_receipt.json"),
              "query_count": count, "query_file_sha256": digest.hexdigest(),
              "base_input_sha256": exported["files"]["base.bin"]["sha256"],
              "public_target_onb_xy": public["target_onb_xy"]}
    (HERE / "freeze.json").write_text(json.dumps(freeze, indent=2,
                                                  sort_keys=True) + "\n")
    print("FROZEN Q1461", count, public["workload_id"])


if __name__ == "__main__":
    main()
