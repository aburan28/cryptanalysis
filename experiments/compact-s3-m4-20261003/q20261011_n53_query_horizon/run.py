#!/usr/bin/env python3
"""Freeze, build, and measure the Q1456 complete-index query horizon."""
from __future__ import annotations
import hashlib
import json
import platform
import random
import struct
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "q20261011_n53_native_pair"
FULL = HERE.parent / "q20261011_n53_native_full"
INPUT = PRIOR / "inputs"
TEMP = Path("/private/tmp/q1456_n53_horizon")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    exported = json.loads((PRIOR / "export_receipt.json").read_text())
    earlier = json.loads((FULL / "native_measurement.json").read_text())
    assert protocol["curve_id"] == exported["curve_id"] == earlier["curve_id"]
    assert protocol["workload_id"] == exported["workload_id"] == earlier["workload_id"]
    assert protocol["factor_base_enumerated_set_sha256"] == exported["factor_base_enumerated_set_sha256"]
    for name, record in exported["files"].items():
        path = INPUT / name
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"]
    assert not TEMP.exists() and not (HERE / "freeze.json").exists()
    TEMP.mkdir()
    for name in exported["files"]:
        if name != "queries.bin":
            (TEMP / name).symlink_to(INPUT / name)
    query_seed = protocol["point_decomposition"]["query_seed"]
    query_cap = protocol["point_decomposition"]["query_caps"][-1]
    rng = random.Random(query_seed)
    digest = hashlib.sha256()
    prefix = hashlib.sha256()
    with (TEMP / "queries.bin").open("wb") as stream:
        for i in range(query_cap):
            pair = struct.pack("<HH", rng.randrange(protocol["factor_base_actual_B"]),
                               rng.randrange(protocol["factor_base_actual_B"]))
            stream.write(pair)
            digest.update(pair)
            if i < 1500000:
                prefix.update(pair)
    assert prefix.hexdigest() == exported["files"]["queries.bin"]["sha256"]
    freeze = {
        "proposal_id": "Q1456", "candidate_id": None, "run_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "native_source_sha256": sha(HERE / "native_sweep.cpp"),
        "field_source_sha256": sha(PRIOR / "native_field53.hpp"),
        "run_source_sha256": sha(Path(__file__)),
        "q1454_export_receipt_sha256": sha(PRIOR / "export_receipt.json"),
        "q1455_measurement_sha256": sha(FULL / "native_measurement.json"),
        "query_count": query_cap,
        "query_file_sha256": digest.hexdigest(),
        "prefix_1500000_sha256": prefix.hexdigest(),
        "base_input_sha256": exported["files"]["base.bin"]["sha256"],
        "public_target": [exported["target_x_hex"], exported["target_y_hex"]],
    }
    (HERE / "freeze.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n")
    binary = TEMP / "native_sweep"
    command = ["/usr/bin/clang++", "-O3", "-std=c++17", "-o", str(binary),
               str(HERE / "native_sweep.cpp")]
    subprocess.run(command, check=True)
    build = {"compiler": subprocess.check_output([command[0], "--version"], text=True).splitlines()[0],
             "architecture": platform.machine(), "os": platform.platform(),
             "flags": command[1:3], "binary_sha256": sha(binary),
             "freeze_sha256": sha(HERE / "freeze.json")}
    (HERE / "build_receipt.json").write_text(json.dumps(build, indent=2, sort_keys=True) + "\n")
    native = [str(binary), str(TEMP), exported["target_x_hex"],
              exported["target_y_hex"], str(protocol["factor_base_actual_B"]),
              str(protocol["factor_base_folded_columns_K"]), str(query_cap),
              str(protocol["point_decomposition"]["table_states"]),
              str(protocol["limits"]["wall_seconds"])]
    raw = TEMP / "raw.json"
    started = time.perf_counter_ns()
    with raw.open("w") as output, (HERE / "native_stderr.txt").open("w") as error:
        result = subprocess.run(native, stdout=output, stderr=error,
                                timeout=protocol["limits"]["wall_seconds"] + 10)
    launcher_ns = time.perf_counter_ns() - started
    assert result.returncode == 0, (HERE / "native_stderr.txt").read_text()
    data = json.loads(raw.read_text())
    assert data["status"] in ("completed_query_cap", "wall_cap_during_queries",
                              "wall_cap_during_table")
    assert data["peak_rss_bytes"] <= protocol["limits"]["peak_rss_mib"] * 1048576
    data.update({"proposal_id": "Q1456", "candidate_id": None, "run_id": None,
                 "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
                 "isogeny": "none", "factor_base_actual_B": protocol["factor_base_actual_B"],
                 "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
                 "factor_base_enumerated_set_sha256": protocol["factor_base_enumerated_set_sha256"],
                 "freeze_sha256": sha(HERE / "freeze.json"),
                 "build_receipt_sha256": sha(HERE / "build_receipt.json"),
                 "raw_sha256": sha(raw), "launcher_wall_ns": launcher_ns,
                 "charged_pair_add_attempts": data["table_states_generated"] +
                    2 * data["query_samples_processed"] - data["query_skipped_identity_pairs"],
                 "complete_solve_work_log2": None, "degree131_challenge_gap_bits": None})
    (HERE / "native_measurement.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(data["status"], data["query_samples_processed"], len(data["matches"]))


if __name__ == "__main__":
    main()
