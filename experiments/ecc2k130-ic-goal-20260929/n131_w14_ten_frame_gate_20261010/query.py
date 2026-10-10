#!/usr/bin/env python3
"""Frozen one-point published ECC2K-130 W14 frame decomposition query."""
import argparse
import importlib.util
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("n131_w14_ten_frame_runner", HERE / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
OFFICIAL = HERE.parent / "n131_w2_m15_official_single_target_4g_20261003"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
PROTOCOL = HERE / "query_protocol.json"
CAP_SECONDS = 120
RSS_CAP_BYTES = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1",
         "--random=20261010", "--maxconfl=2000000"]


def sources():
    return {"runner": Path(__file__), "formula_runner": HERE / "run.py",
            "circuit": HERE / "circuit.py",
            "construction_protocol": HERE / "protocol.json",
            "construction_profile": HERE / "profile.json",
            "sage_replay": HERE / "sage_audit.json",
            "official_parameters": OFFICIAL / "official_fixed_parameters.json",
            "official_bridge": OFFICIAL / "bridge_audit.json",
            "support_masks": run.SUPPORT / "support_w14.tsv",
            "solver": SOLVER}


def published_q(field, curve):
    params = json.loads((OFFICIAL / "official_fixed_parameters.json").read_text())
    bridge = json.loads((OFFICIAL / "bridge_audit.json").read_text())
    assert bridge["status"] == "PASS"
    assert run.sha(OFFICIAL / "official_fixed_parameters.json") == bridge["input_sha256"]["official_fixed_parameters"]
    assert params["curve"]["polynomial"].lower() == "0x800000000000000000000000000002007"
    assert int(params["curve"]["subgroup_order"]) == run.R
    assert params["targets"][0]["id"] == "ecc2k-130"
    target = params["targets"][0]
    q = (int(target["x"], 16), int(target["y"], 16))
    assert curve.on_curve(q) and curve.mul(run.R, q) is None
    return q


def freeze():
    construction = json.loads((HERE / "profile.json").read_text())
    replay = json.loads((HERE / "sage_audit.json").read_text())
    assert construction["status"] == "PASS_FULL_FORMULA_CONSTRUCTED_GROUP_WITNESS"
    assert replay["status"] == "PASS_INDEPENDENT_SAGE_N131_GROUP_AND_FRAME_REPLAY"
    _, geometry, _, field, curve, _, _ = run.source()
    q = published_q(field, curve)
    record = {"status": "FROZEN_BEFORE_PUBLISHED_POINT_QUERY",
              "candidate_id": None, "curve_id": construction["curve_id"],
              "published_target_id": "ecc2k-130",
              "public_target_q_polynomial": list(q), "target_count": 1,
              "input_law": "one fixed published subgroup point; ten W14 masks, signs, and intermediates unpinned",
              "actual_factor_base_points_B": geometry["actual_subgroup_factor_base_points_B"],
              "effective_folded_columns_K": geometry["folded_columns_K"],
              "online_wall_cap_seconds": CAP_SECONDS,
              "rss_cap_bytes": RSS_CAP_BYTES,
              "solver_flags": FLAGS,
              "source_sha256": {name: run.sha(path) for name, path in sources().items()}}
    run.save(PROTOCOL, record)
    print(json.dumps({"status": record["status"], "target_q": list(q)}))


def query():
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_PUBLISHED_POINT_QUERY"
    assert protocol["source_sha256"] == {name: run.sha(path)
                                           for name, path in sources().items()}
    folder = HERE / "public_query"
    folder.mkdir(exist_ok=False)
    support, geometry, columns, field, curve, source_w, source_u = run.source()
    q = published_q(field, curve)
    assert list(q) == protocol["public_target_q_polynomial"]
    started = time.monotonic()
    targets = run.target_preimages(curve, q)
    target_us = [run.transformed(field, point) for point in targets]
    target_transport_seconds = time.monotonic() - started
    circuit = run.old.old.base.KaratsubaCircuit(131, run.LOW_TERMS)
    meta = run.method.build(circuit, field, source_w, source_u,
                            support["rotations"], columns, columns, target_us)
    formula = folder / "system.xcnf"
    circuit.write(formula)
    formula_seconds = time.monotonic() - started - target_transport_seconds
    stats = {"variables": circuit.next_var - 1,
             "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
             "and_gates": circuit.and_count,
             "duplicate_column_clauses": meta["duplicate_column_clauses"],
             "bytes": formula.stat().st_size, "sha256": run.sha(formula)}
    if time.monotonic() - started >= CAP_SECONDS - 5:
        raise TimeoutError("formula construction exhausted online cap")
    remaining = CAP_SECONDS - (time.monotonic() - started) - 1
    solver_cap = max(1, int(remaining) - 2)
    command = [str(SOLVER), *FLAGS, f"--maxtime={solver_cap}", str(formula)]
    stdout_path, stderr_path = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    parent = psutil.Process(os.getpid())
    peak_rss = peak_cpu = 0
    stop_reason = None
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        child = psutil.Process(process.pid)
        run.save(folder / "process.json",
                 {"pid": process.pid, "create_time_epoch": child.create_time(),
                  "started_utc": datetime.now(timezone.utc).isoformat(),
                  "protocol_sha256": run.sha(PROTOCOL), "command": command})
        solver_started = time.monotonic()
        while process.poll() is None:
            try:
                cpu = child.cpu_times()
                peak_cpu = max(peak_cpu, cpu.user + cpu.system)
                peak_rss = max(peak_rss, child.memory_info().rss +
                               parent.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak_rss > RSS_CAP_BYTES:
                stop_reason = "RSS_CAP"
                process.terminate()
                break
            if time.monotonic() - started >= CAP_SECONDS:
                stop_reason = "ONLINE_WALL_CAP"
                process.terminate()
                break
            if time.monotonic() - solver_started >= remaining:
                stop_reason = "SOLVER_WALL_CAP"
                process.terminate()
                break
            time.sleep(.1)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            stop_reason = (stop_reason or "DRAIN_TIMEOUT") + "_KILLED"
    solver_seconds = time.monotonic() - solver_started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    xcnf_check = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = run.old.old.base.read_model(output, stats["variables"])
        xcnf_check = run.old.old.base.check_xcnf(formula, model)
        status = "SAT_MODEL_PENDING_GROUP_REPLAY"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason in ("ONLINE_WALL_CAP", "SOLVER_WALL_CAP") or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    receipt = {"status": status, "candidate_id": None,
               "curve_id": protocol["curve_id"], "target_count": 1,
               "public_target_q_polynomial": list(q),
               "transported_raw_targets": [list(point) for point in targets],
               "formula": stats, "solver_command": command,
               "solver_status_lines": statuses, "model_lines": model_lines,
               "solver_exit_code": process.returncode,
               "stop_reason": stop_reason,
               "producer_xcnf_check": xcnf_check,
               "verified_relations": 0, "useful_rank": 0,
               "phase_seconds": {"target_transport": target_transport_seconds,
                                 "target_formula": formula_seconds,
                                 "solver": solver_seconds,
                                 "online_wall": time.monotonic() - started},
               "sampled_peak_combined_rss_bytes": peak_rss,
               "sampled_solver_cpu_seconds": peak_cpu,
               "source_sha256": {"protocol": run.sha(PROTOCOL),
                                 "formula": run.sha(formula),
                                 "stdout": run.sha(stdout_path),
                                 "stderr": run.sha(stderr_path),
                                 "process": run.sha(folder / "process.json")}}
    run.save(folder / "result.json", receipt)
    print(json.dumps({"status": status,
                      "online_seconds": receipt["phase_seconds"]["online_wall"],
                      "formula": stats,
                      "peak_rss_bytes": peak_rss}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "query"))
    {"freeze": freeze, "query": query}[parser.parse_args().mode]()
