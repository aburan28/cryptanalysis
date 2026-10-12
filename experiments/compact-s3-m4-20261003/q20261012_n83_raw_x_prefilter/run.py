#!/usr/bin/env python3
"""Run frozen Q1512 controls and ordinary raw-x Bloom parameter sweep."""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
Q1505_CONTROL = PARENT / "q20261012_n83_deferred_y_scan/control_result.json"
BINARY = Path("/Volumes/SSD990/llm/tmp/q1512-native-prefilter")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_cell(protocol, x, y, pair_count, batch, bits, hashes):
    args = [str(BINARY), str(BASE), x, y, str(pair_count), str(batch),
            str(bits), str(hashes)]
    started = time.perf_counter_ns()
    try:
        process = subprocess.run(args, capture_output=True, text=True,
                                 timeout=protocol["wall_cap_seconds_per_cell"])
        wall_ns = time.perf_counter_ns() - started
        lines = process.stdout.splitlines()
        data = json.loads(lines[-1]) if process.returncode == 0 else None
        return {"status": "COMPLETE" if process.returncode == 0 else "PROCESS_FAILURE",
                "command": args, "exit_code": process.returncode,
                "process_wall_ns": wall_ns, "stdout": process.stdout,
                "stderr": process.stderr, "native": data}
    except subprocess.TimeoutExpired as exc:
        return {"status": "TIMEOUT", "command": args,
                "wall_cap_seconds": protocol["wall_cap_seconds_per_cell"],
                "process_wall_ns": time.perf_counter_ns() - started,
                "partial_stdout": (exc.stdout or b"").decode(errors="replace"),
                "partial_stderr": (exc.stderr or b"").decode(errors="replace")}


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["proposal_id"] == "Q1512"
    assert not (HERE / "result.json").exists()
    assert sha(HERE / "native_prefilter.cpp") == protocol["source_sha256"]
    assert sha(BINARY) == protocol["binary_sha256"]
    assert sha(BASE) == protocol["base_point_file_sha256"]
    available = os.statvfs(HERE).f_bavail * os.statvfs(HERE).f_frsize
    assert available > 1024 ** 3
    parent_controls = json.loads(Q1505_CONTROL.read_text())["controls"]
    controls = []
    for old in parent_controls:
        row = run_cell(protocol, old["target_x_onb_hex"],
                       old["target_y_onb_hex"], 1, 1, 28, 4)
        row["expected_sign"] = old["sign"]
        assert row["status"] == "COMPLETE", row
        assert row["native"]["hits"] >= 1
        assert any(line.startswith(f"hit 0 {old['sign']} ")
                   for line in row["stdout"].splitlines())
        controls.append(row)
    rows = []
    selected = protocol["ordinary_inputs"]["selected"]
    for bits, hashes in protocol["screen_modes"]:
        row = run_cell(protocol, selected["x_onb_hex"], selected["y_onb_hex"],
                       protocol["screen_pair_count"], protocol["batch_pairs"],
                       bits, hashes)
        row.update({"panel": "screen", "input": "selected",
                    "workload_id": selected["workload_id"],
                    "complement_index": 0, "bloom_log2_bits": bits,
                    "bloom_hashes": hashes})
        rows.append(row)
        print("screen", bits, hashes, row["status"],
              row.get("native", {}).get("scan_seconds"), flush=True)
        (HERE / "result.partial.json").write_text(json.dumps(
            {"proposal_id": "Q1512", "controls": controls, "rows": rows},
            indent=2, sort_keys=True) + "\n")
    for label, bits, hashes in protocol["full_modes_in_run_order"]:
        item = protocol["ordinary_inputs"][label]
        row = run_cell(protocol, item["x_onb_hex"], item["y_onb_hex"],
                       protocol["full_pair_count"], protocol["batch_pairs"],
                       bits, hashes)
        row.update({"panel": "full", "input": label,
                    "workload_id": item["workload_id"],
                    "complement_index": 0, "bloom_log2_bits": bits,
                    "bloom_hashes": hashes})
        rows.append(row)
        print("full", label, bits, hashes, row["status"],
              row.get("native", {}).get("scan_seconds"), flush=True)
        (HERE / "result.partial.json").write_text(json.dumps(
            {"proposal_id": "Q1512", "controls": controls, "rows": rows},
            indent=2, sort_keys=True) + "\n")
    result = {"proposal_id": "Q1512", "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"], "isogeny": "none",
              "factor_base_actual_B": protocol["factor_base_actual_B"],
              "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
              "factor_base_enumerated_set_sha256": protocol["factor_base_enumerated_set_sha256"],
              "protocol_sha256": sha(HERE / "protocol.json"),
              "run_source_sha256": sha(Path(__file__)),
              "controls": controls, "rows": rows,
              "complete_n83_decomposition_work_log2": None,
              "complete_n131_solve_operation_log2": None}
    (HERE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
