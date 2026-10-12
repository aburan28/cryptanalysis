#!/usr/bin/env python3
"""Run frozen native Q1454 cap sweep, retaining terminal and phase receipts."""
from __future__ import annotations
import hashlib
import json
import subprocess
import time
from pathlib import Path
from export import INPUT_DIR, frozen_inputs

HERE = Path(__file__).resolve().parent
FREEZE = HERE / "freeze.json"
OUT = HERE / "native_measurement.json"
STDERR = HERE / "native_stderr.txt"
RAW = Path("/private/tmp/q1454_n53_sweep_raw.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not OUT.exists() and not RAW.exists()
    assert json.loads(FREEZE.read_text()) == frozen_inputs()
    protocol = json.loads((HERE / "protocol.json").read_text())
    exported = json.loads((HERE / "export_receipt.json").read_text())
    built = json.loads((HERE / "build_receipt.json").read_text())
    assert exported["freeze_sha256"] == built["freeze_sha256"] == sha(FREEZE)
    binary = Path(built["binary_path"])
    assert sha(binary) == built["binary_sha256"]
    for name, record in exported["files"].items():
        path = INPUT_DIR / name
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"]
    pdp = protocol["point_decomposition"]
    command = [str(binary), str(INPUT_DIR), exported["target_x_hex"],
               exported["target_y_hex"], str(protocol["factor_base_actual_B"]),
               str(protocol["factor_base_folded_columns_K"]),
               str(pdp["query_sample_cap"]), str(pdp["table_states"]),
               str(protocol["limits"]["external_wall_seconds"])]
    started = time.perf_counter_ns()
    with RAW.open("w") as output, STDERR.open("w") as error:
        result = subprocess.run(command, stdout=output, stderr=error,
                                timeout=protocol["limits"]["external_wall_seconds"] + 10)
    launcher_ns = time.perf_counter_ns() - started
    assert result.returncode == 0, f"native exit {result.returncode}: {STDERR.read_text()}"
    data = json.loads(RAW.read_text())
    assert data["status"] in ("completed_query_cap", "wall_cap_during_table",
                              "wall_cap_during_queries")
    assert data["peak_rss_bytes"] <= protocol["limits"]["peak_rss_mib"] * 1048576
    data["charged_pair_add_attempts"] = (data["table_states_generated"] +
        2 * data["query_samples_processed"] - data["query_skipped_identity_pairs"])
    data.update({"proposal_id": "Q1454", "candidate_id": None, "run_id": None,
                 "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
                 "isogeny": "none", "factor_base_actual_B": protocol["factor_base_actual_B"],
                 "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
                 "factor_base_enumerated_set_sha256": protocol[
                     "factor_base_enumerated_set_sha256"],
                 "freeze_sha256": sha(FREEZE),
                 "export_receipt_sha256": sha(HERE / "export_receipt.json"),
                 "build_receipt_sha256": sha(HERE / "build_receipt.json"),
                 "native_binary_sha256": sha(binary),
                 "raw_measurement_sha256": sha(RAW),
                 "launcher_wall_ns": launcher_ns,
                 "complete_solve_work_log2": None,
                 "degree131_challenge_gap_bits": None})
    OUT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print("MEASURED", data["status"], data["table_states_generated"],
          data["query_samples_processed"], len(data["matches"]))


if __name__ == "__main__":
    main()
