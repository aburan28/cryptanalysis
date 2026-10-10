#!/usr/bin/env python3
"""Frozen one-worker gate for projected five-pair N41 XCNF."""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_w5_allpair_index_20261010"
PROJECTOR = HERE.parent / "xor_projection_20261009" / "project_xcnf.py"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
CAPS = {"all_fixed": 20, "public": 120}
RSS_CAP = 4 * 1024**3


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    paths = {"query": Path(__file__), "audit": HERE / "audit.py",
             "control": HERE / "control.py", "projector": PROJECTOR,
             "control_audit": HERE / "control_audit.json",
             "source_protocol": SOURCE / "protocol.json",
             "source_preflight": SOURCE / "preflight.json",
             "runtime": HERE / "sage_runtime_info.json", "solver": SOLVER}
    for mode in CAPS:
        paths[f"original_{mode}"] = SOURCE / (
            "public_allpair.xcnf" if mode == "public" else "all_fixed.xcnf")
        folder = HERE / mode
        for name in ("projected.xcnf", "result.json", "variable_map.json",
                     "lift_rows.jsonl"):
            paths[f"{mode}_{name}"] = folder / name
    return paths


def freeze():
    assert json.loads((HERE / "control_audit.json").read_text())["status"] == (
        "PASS_EXACT_XCNF_PROJECTION_AND_LIFT")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    record = {
        "status": "FROZEN_BEFORE_PROJECTED_SOLVER_QUERIES",
        "kind": "n41_w5_five_pair_upper_xor_projection_gate",
        "candidate_id": None, "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "public_target_q": [1458168294740, 1672312028033],
        "actual_factor_base_points_B": 170, "folded_columns_K": 14,
        "target_count": 1, "workers": 1, "rss_cap_bytes": RSS_CAP,
        "solver_caps_seconds": CAPS,
        "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                         "--random=20261010"],
        "source_sha256": {key: sha(path) for key, path in sources().items()},
    }
    with (HERE / "protocol.json").open("x") as out:
        json.dump(record, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": record["status"], "caps": CAPS}))


def run(mode):
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_PROJECTED_SOLVER_QUERIES"
    assert protocol["source_sha256"] == {key: sha(path) for key, path in sources().items()}
    folder = HERE / mode
    query = HERE / (mode + "_query")
    query.mkdir(exist_ok=False)
    cap = protocol["solver_caps_seconds"][mode]
    formula = folder / "projected.xcnf"
    command = [str(SOLVER), *protocol["solver_flags"],
               f"--maxtime={cap-2}", str(formula)]
    stdout = query / "solver.stdout.txt"
    stderr = query / "solver.stderr.txt"
    start = time.monotonic()
    peak = 0
    stop = None
    with stdout.open("xb") as out, stderr.open("xb") as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err,
                                start_new_session=True)
        child = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                peak = max(peak, child.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            elapsed = time.monotonic() - start
            if peak > RSS_CAP:
                stop = "RSS_CAP"
            elif elapsed >= cap:
                stop = "PARENT_WALL_CAP"
            if stop:
                proc.terminate()
                break
            time.sleep(0.1)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            stop = (stop or "DRAIN_TIMEOUT") + "_KILLED"
    wall = time.monotonic() - start
    output = stdout.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    restarts = sum(line.startswith("c rst") for line in output.splitlines())
    if statuses == ["s SATISFIABLE"] and model_lines:
        status = "SAT_MODEL_PENDING_LIFT_AND_SAGE"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    elif stop == "RSS_CAP":
        status = "OOM"
    elif stop == "PARENT_WALL_CAP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    record = {"status": status, "mode": mode, "candidate_id": None,
              "public_target_q": protocol["public_target_q"],
              "solver_command": command, "solver_exit_code": proc.returncode,
              "solver_status_lines": statuses, "model_lines": model_lines,
              "logged_restarts": restarts, "stop_reason": stop,
              "solver_wall_seconds": wall,
              "sampled_solver_peak_rss_bytes": peak,
              "verified_relations": 0, "useful_rank": 0,
              "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                "formula": sha(formula),
                                "stdout": sha(stdout), "stderr": sha(stderr)}}
    with (query / "result.json").open("x") as out:
        json.dump(record, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": status, "mode": mode, "wall_seconds": wall,
                      "restarts": restarts, "peak_rss_bytes": peak}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", *CAPS))
    args = parser.parse_args()
    freeze() if args.mode == "freeze" else run(args.mode)
