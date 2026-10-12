#!/usr/bin/env python3
"""Replay bounded exact second-pair scans and retain every cell."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
BINARY = Path("/Volumes/SSD990/llm/tmp/q1501-build/native_probe")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    freeze = HERE / "frozen_inputs.json"
    data = json.loads(freeze.read_text())
    assert sha(BASE) == data["base_point_file_sha256"]
    assert sha(HERE / "native_probe.cpp") == data["native_source_sha256"]
    assert sha(HERE / "prepare.py") == data["prepare_source_sha256"]
    assert BINARY.exists()
    rows = []
    for label, input_row in data["inputs"].items():
        for i, comp in enumerate(input_row["complements"]):
            for batch in data["batch_sizes"]:
                args = [str(BINARY), str(BASE), comp["x_onb_hex"],
                        comp["y_onb_hex"],
                        str(data["scan_limit_per_complement"]), str(batch)]
                p = subprocess.run(args, text=True, capture_output=True,
                                   timeout=90)
                row = {"input": label, "workload_id": input_row["workload_id"],
                       "complement_index": i, "signs": comp["signs"],
                       "batch": batch, "return_code": p.returncode,
                       "stderr": p.stderr, "stdout_sha256":
                       hashlib.sha256(p.stdout.encode()).hexdigest(),
                       "result": None}
                if p.returncode == 0:
                    lines = p.stdout.splitlines()
                    row["result"] = json.loads(lines[-1])
                    row["hits"] = lines[:-1]
                    assert row["result"]["scanned"] == data["scan_limit_per_complement"]
                    assert row["result"]["hits"] == len(row["hits"])
                rows.append(row)
                print(label, i, batch, row["result"], flush=True)
    result = {"proposal_id": "Q1501", "candidate_id": None,
              "run_id": None, "curve_id": data["curve_id"],
              "factor_base_actual_B": data["factor_base_actual_B"],
              "factor_base_folded_columns_K": data["factor_base_folded_columns_K"],
              "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
              "freeze_sha256": sha(freeze), "binary_sha256": sha(BINARY),
              "run_source_sha256": sha(Path(__file__)), "rows": rows,
              "complete_n83_decomposition_work_log2": None,
              "complete_n131_solve_work_log2": None}
    (HERE / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
