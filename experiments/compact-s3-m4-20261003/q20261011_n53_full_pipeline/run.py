#!/usr/bin/env python3
"""Measure frozen Q1457 generator-anchored relation collection."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent / "q20261011_n53_native_pair"
TEMP = Path("/private/tmp/q1457_n53_setup")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    out = HERE / "native_measurement.json"
    raw = TEMP / "native_raw.json"
    assert not out.exists() and not raw.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    exported = json.loads((PAIR / "export_receipt.json").read_text())
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    binary = Path(build["binary_path"])
    assert binary.exists() and sha(binary) == build["binary_sha256"]
    for name,record in exported["files"].items():
        if name == "queries.bin": continue
        path = TEMP / name
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"]
    queries = TEMP / "queries.bin"
    assert queries.stat().st_size == freeze["query_count"] * 4
    assert sha(queries) == freeze["query_file_sha256"]
    available = os.statvfs(HERE).f_bavail * os.statvfs(HERE).f_frsize
    assert available > 1024**3, f"less than 1 GiB output headroom: {available}"
    target = protocol["generator_onb_xy"]
    command = [str(binary),str(TEMP),format(target[0],"x"),format(target[1],"x"),
               str(protocol["factor_base_actual_B"]),
               str(protocol["factor_base_folded_columns_K"]),
               str(freeze["query_count"]),
               str(protocol["point_decomposition"]["table_states"]),
               str(protocol["limits"]["native_wall_seconds"])]
    started = time.perf_counter_ns()
    with raw.open("w") as output,(HERE / "native_stderr.txt").open("w") as error:
        result = subprocess.run(command,stdout=output,stderr=error,
                                timeout=protocol["limits"]["external_wall_seconds"])
    launcher_wall_ns = time.perf_counter_ns() - started
    assert result.returncode == 0,(HERE / "native_stderr.txt").read_text()
    data = json.loads(raw.read_text())
    assert data["status"] in ("completed_query_cap","wall_cap_during_queries",
                              "wall_cap_during_table")
    assert data["peak_rss_bytes"] <= protocol["limits"]["peak_rss_mib"]*1048576
    (HERE / "native_raw.json").write_bytes(raw.read_bytes())
    data.update({"proposal_id": "Q1457", "candidate_id": None,"run_id": None,
                 "curve_id": protocol["curve_id"], "isogeny": "none",
                 "factor_base_actual_B": protocol["factor_base_actual_B"],
                 "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
                 "factor_base_enumerated_set_sha256": protocol["factor_base_enumerated_set_sha256"],
                 "setup_target": "generator G", "setup_generator_onb_xy": target,
                 "freeze_sha256": sha(HERE / "freeze.json"),
                 "build_receipt_sha256": sha(HERE / "build_receipt.json"),
                 "raw_sha256": sha(raw), "launcher_wall_ns": launcher_wall_ns,
                 "charged_pair_add_attempts": data["table_states_generated"] +
                    2*data["query_samples_processed"] - data["query_skipped_identity_pairs"],
                 "complete_solve_work_log2": None,
                 "degree131_challenge_gap_bits": None})
    temporary = out.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    temporary.replace(out)
    print("Q1457",data["status"],data["query_samples_processed"],len(data["matches"]))


if __name__ == "__main__":
    main()
