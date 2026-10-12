#!/usr/bin/env python3
"""Replay frozen ordinary complements with deferred-y batch sizes."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1501 = PARENT / "q20261012_n83_complement_pair_probe"
Q1502 = PARENT / "q20261012_n83_signed_pair_batch"
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
BINARY = Path("/Volumes/SSD990/llm/tmp/q1501-build/native_deferred_y")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    protocol = read(HERE / "protocol.json")
    assert sha(HERE / "native_deferred_y.cpp") == protocol["native_source_sha256"]
    assert sha(BINARY) == protocol["binary_sha256"]
    assert sha(BASE) == protocol["base_point_file_sha256"]
    assert sha(Q1501 / "frozen_inputs.json") == protocol["frozen_inputs_sha256"]
    assert sha(Q1502 / "result.json") == protocol["baseline_result_sha256"]
    assert not (HERE / "result.json").exists()
    inputs = read(Q1501 / "frozen_inputs.json")
    baseline = read(Q1502 / "result.json")
    rows = []
    for batch in protocol["batch_pairs_screen"]:
        for label in ("selected", "holdout"):
            for index, comp in enumerate(inputs["inputs"][label]["complements"]):
                if batch != protocol["primary_batch_pairs"] and index != 0:
                    continue
                reference = next(r for r in baseline["rows"] if
                                 r["input"] == label and r["complement_index"] == index)
                assert reference["status"] == "COMPLETE"
                args = [str(BINARY), str(BASE), comp["x_onb_hex"],
                        comp["y_onb_hex"], str(protocol["scan_pairs_per_complement"]),
                        str(batch)]
                try:
                    p = subprocess.run(args, text=True, capture_output=True,
                                       timeout=protocol["seconds_timeout_per_cell"])
                    lines = p.stdout.splitlines()
                    result = json.loads(lines[-1]) if p.returncode == 0 else None
                    row = {"input": label,
                           "workload_id": inputs["inputs"][label]["workload_id"],
                           "complement_index": index, "signs": comp["signs"],
                           "batch_pairs": batch,
                           "status": "COMPLETE" if p.returncode == 0 else "PROCESS_FAILURE",
                           "return_code": p.returncode, "stderr": p.stderr,
                           "stdout_sha256": hashlib.sha256(p.stdout.encode()).hexdigest(),
                           "hits": lines[:-1] if result else [], "result": result,
                           "baseline_checksum_hex": reference["result"]["checksum_hex"],
                           "baseline_hits": reference["result"]["hits"],
                           "baseline_scan_seconds_exploratory":
                               reference["result"]["scan_seconds"]}
                    if result:
                        assert result["scanned"] == protocol["factor_base_actual_B"]
                        assert result["checksum_hex"] == row["baseline_checksum_hex"]
                        assert result["hits"] == row["baseline_hits"]
                except subprocess.TimeoutExpired as error:
                    row = {"input": label, "complement_index": index,
                           "batch_pairs": batch, "status": "TIMEOUT",
                           "timeout_seconds": protocol["seconds_timeout_per_cell"],
                           "stdout_partial": (error.stdout or b"").decode(errors="replace")}
                rows.append(row)
                print(label, index, batch, row["status"],
                      row.get("result", {}).get("scan_seconds"), flush=True)
                (HERE / "result.partial.json").write_text(json.dumps({
                    "proposal_id": "Q1505", "protocol_sha256": sha(HERE / "protocol.json"),
                    "rows": rows}, indent=2, sort_keys=True) + "\n")
    output = {"proposal_id": "Q1505", "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"],
              "factor_base_actual_B": protocol["factor_base_actual_B"],
              "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
              "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
              "protocol_sha256": sha(HERE / "protocol.json"),
              "run_source_sha256": sha(Path(__file__)), "rows": rows,
              "complete_n83_decomposition_work_log2": None,
              "complete_n131_solve_work_log2": None}
    (HERE / "result.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
