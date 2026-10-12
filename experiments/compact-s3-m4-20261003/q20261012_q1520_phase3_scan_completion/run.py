#!/usr/bin/env python3
"""Resume exact Q1518 phase-three N83 complement scans without altering prior receipts."""
import argparse
import hashlib
import importlib.util
import json
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1518 = PARENT / "q20261012_q1518_inprocess_mask_sweep"
Q1512 = PARENT / "q20261012_n83_raw_x_prefilter"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


prior = module("q1518_run", Q1518 / "run.py")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def prepare(p):
    assert sha(Q1518 / "result.json") == p["q1518_first_pair_result_sha256"]
    assert sha(Q1518 / "scan_result.json") == p["q1518_scan_result_sha256"]
    assert sha(Q1512 / "build_receipt.json") == p["q1512_build_receipt_sha256"]
    assert sha(prior.BASE) == p["factor_base_point_file_sha256"]
    assert sha(prior.BASE_MANIFEST) == p["factor_base_manifest_sha256"]
    binary = Path(read(Q1512 / "build_receipt.json")["binary_path"])
    assert sha(binary) == p["binary_sha256"]
    first_pairs = read(Q1518 / "result.json")
    old = read(Q1518 / "scan_result.json")
    assert old["status"] == "INTERRUPTED_HOST_CONTENTION"
    completed = {(r["input"], r["pair_index"], *r["signs"])
                 for r in old["rows"] if r["status"] == "COMPLETE"}
    assert len(completed) == 14
    base = prior.BASE.read_bytes()
    keys = {int.from_bytes(base[i:i+21], "little") for i in range(0, len(base), 21)}
    onb = prior.base_runner.CountedOnb(83)
    curve = prior.base_runner.Curve(onb)
    orbit = prior.base_runner.OrbitKey(onb)
    order = int(read(prior.BASE_MANIFEST)["curve"]["subgroup_order"])
    tasks = []
    for label in ("selected", "holdout"):
        target = tuple(read(prior.base_runner.TARGETS[label])["public_target"])
        stage = next(r for r in first_pairs["rows"] if r["input"] == label
                     and r["phase"] == 3)
        assert stage["status"] == "EIGHT_PAIRS_TERMINATED"
        for index, item in enumerate(stage["exact_base_outcomes"]):
            if not item["both_exact_base_usable"]:
                continue
            leaves = prior.base_runner.base_pair(item["bits"], onb, curve,
                                                 orbit, keys, order)
            assert all(x["exact_base_member"] for x in leaves)
            for s0 in (1, -1):
                for s1 in (1, -1):
                    key = (label, index, s0, s1)
                    if key in completed:
                        continue
                    a = leaves[0]["point"] if s0 == 1 else curve.neg(leaves[0]["point"])
                    b = leaves[1]["point"] if s1 == 1 else curve.neg(leaves[1]["point"])
                    complement = curve.add(target, curve.neg(curve.add(a, b)))
                    assert complement is not None and curve.onCurve(complement)
                    tasks.append({"input": label, "workload_id": stage["workload_id"],
                                  "pair_index": index, "signs": [s0, s1],
                                  "complement_x_onb_hex": format(onb.toCoords(complement[0]), "x"),
                                  "complement_y_onb_hex": format(onb.toCoords(complement[1]), "x")})
    assert len(tasks) == p["planned_continuation_cells"] == 26
    return binary, tasks


def limit_cpu(soft, hard):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def one(p, binary, task):
    label, index, (s0, s1) = task["input"], task["pair_index"], task["signs"]
    folder = HERE / "runs" / label / f"pair{index}" / f"sign{s0}_{s1}"
    folder.mkdir(parents=True, exist_ok=False)
    stdout, stderr = folder / "stdout.txt", folder / "stderr.txt"
    command = [str(binary), str(prior.BASE), task["complement_x_onb_hex"],
               task["complement_y_onb_hex"], str(p["scan_pairs_per_complement"]),
               str(p["batch_pairs"]), str(p["bloom_log2_bits"]),
               str(p["bloom_hashes"])]
    started = time.monotonic()
    reason = None
    with stdout.open("wb") as out, stderr.open("wb") as err:
        child = subprocess.Popen(command, stdout=out, stderr=err,
                                 preexec_fn=limit_cpu(p["cpu_soft_seconds_per_cell"],
                                                      p["cpu_hard_seconds_per_cell"]))
        deadline, terminated = started + p["wall_seconds_per_cell"], None
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                child.returncode = os.waitstatus_to_exitcode(status)
                break
            now = time.monotonic()
            if terminated is None and now >= deadline:
                reason = "WALL_CAP"
                child.terminate()
                terminated = now
            elif terminated is not None and now - terminated > 5:
                child.kill()
            time.sleep(0.05)
    output = stdout.read_text(errors="replace")
    lines = output.splitlines()
    native = json.loads(lines[-1]) if child.returncode == 0 else None
    status_name = ("COMPLETE" if native else "WALL_CAP" if reason else
                   "CPU_CAP" if child.returncode in (-signal.SIGXCPU, -signal.SIGKILL)
                   else "PROCESS_FAILURE")
    if native:
        assert native["actual_B"] == p["factor_base_actual_B"]
        assert native["scanned"] == p["factor_base_actual_B"]
    return {**task, "status": status_name, "return_code": child.returncode,
            "termination_reason": reason, "command": command,
            "native_result": native, "native_hit_lines": lines[:-1] if native else [],
            "batch_mul_calls_excluding_inversion_internals":
                5 * p["scan_pairs_per_complement"] if native and native["hits"] == 0
                and native["exceptional_pairs"] == 0 else None,
            "wall_seconds_exploratory": time.monotonic() - started,
            "child_user_cpu_seconds": usage.ru_utime,
            "child_system_cpu_seconds": usage.ru_stime,
            "child_peak_rss_bytes_darwin": usage.ru_maxrss,
            "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-cells", type=int, default=8)
    args = parser.parse_args()
    assert 1 <= args.max_cells <= 26
    p = read(HERE / "protocol.json")
    binary, tasks = prepare(p)
    partial = HERE / "result.partial.json"
    rows = read(partial)["rows"] if partial.exists() else []
    assert not (HERE / "result.json").exists()
    keys = {(r["input"], r["pair_index"], *r["signs"]) for r in rows}
    assert len(keys) == len(rows)
    pending = [t for t in tasks if (t["input"], t["pair_index"], *t["signs"]) not in keys]
    for task in pending[:args.max_cells]:
        row = one(p, binary, task)
        folder = HERE / "runs" / row["input"] / f"pair{row['pair_index']}" / f"sign{row['signs'][0]}_{row['signs'][1]}"
        save(folder / "receipt.json", row)
        rows.append(row)
        save(partial, {"proposal_id": "Q1520", "rows": rows})
        print(row["input"], row["pair_index"], row["signs"], row["status"],
              row["native_result"]["hits"] if row["native_result"] else None,
              flush=True)
    if len(rows) == len(tasks):
        save(HERE / "result.json", {
            "proposal_id": "Q1520", "candidate_id": None, "run_id": None,
            "curve_id": p["curve_id"], "isogeny": "none",
            "point_decomposition_stage_code": "PDP4hybrid",
            "protocol_sha256": sha(HERE / "protocol.json"),
            "source_sha256": sha(Path(__file__)), "rows": rows,
            "complete_n83_decomposition_work_log2": None,
            "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()
