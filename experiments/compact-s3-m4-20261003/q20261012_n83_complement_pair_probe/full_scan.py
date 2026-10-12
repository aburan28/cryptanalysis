#!/usr/bin/env python3
"""Complete fixed-first-pair scan over the frozen N83 base."""
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
    protocol = json.loads((HERE / "full_protocol.json").read_text())
    freeze = HERE / "frozen_inputs.json"
    inputs = json.loads(freeze.read_text())
    assert sha(freeze) == protocol["input_freeze_sha256"]
    assert sha(BINARY) == protocol["binary_sha256"]
    assert sha(BASE) == inputs["base_point_file_sha256"]
    assert protocol["scan_limit_per_complement"] == inputs["factor_base_actual_B"]
    assert not (HERE / "full_result.json").exists()
    rows = []
    for label in ("selected", "holdout"):
        for i, comp in enumerate(inputs["inputs"][label]["complements"]):
            args = [str(BINARY), str(BASE), comp["x_onb_hex"],
                    comp["y_onb_hex"], str(protocol["scan_limit_per_complement"]),
                    str(protocol["batch_size"])]
            try:
                p = subprocess.run(args, text=True, capture_output=True,
                                   timeout=protocol["seconds_timeout_per_cell"])
                lines = p.stdout.splitlines()
                result = json.loads(lines[-1]) if p.returncode == 0 else None
                row = {"input": label, "workload_id": inputs["inputs"][label]["workload_id"],
                       "complement_index": i, "signs": comp["signs"],
                       "status": "COMPLETE" if p.returncode == 0 else "PROCESS_FAILURE",
                       "return_code": p.returncode, "stderr": p.stderr,
                       "stdout_sha256": hashlib.sha256(p.stdout.encode()).hexdigest(),
                       "hits": lines[:-1] if result is not None else [],
                       "result": result}
            except subprocess.TimeoutExpired as error:
                row = {"input": label, "complement_index": i,
                       "signs": comp["signs"], "status": "TIMEOUT",
                       "timeout_seconds": protocol["seconds_timeout_per_cell"],
                       "stdout_partial": (error.stdout or b"").decode(errors="replace")}
            rows.append(row)
            print(label, i, row["status"], row.get("result"), flush=True)
            (HERE / "full_result.partial.json").write_text(json.dumps({
                "proposal_id": "Q1501", "protocol_sha256": sha(HERE / "full_protocol.json"),
                "rows": rows}, indent=2, sort_keys=True) + "\n")
    result = {"proposal_id": "Q1501", "candidate_id": None, "run_id": None,
              "curve_id": inputs["curve_id"],
              "factor_base_actual_B": inputs["factor_base_actual_B"],
              "factor_base_folded_columns_K": inputs["factor_base_folded_columns_K"],
              "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
              "protocol_sha256": sha(HERE / "full_protocol.json"),
              "full_scan_source_sha256": sha(Path(__file__)), "rows": rows,
              "complete_n83_decomposition_work_log2": None,
              "complete_n131_solve_work_log2": None}
    (HERE / "full_result.json").write_text(json.dumps(
        result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
