#!/usr/bin/env python3
"""One-worker capped public-point query for the bilinear W14 formula."""

import argparse
import gzip
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
OFFICIAL = HERE.parent / "n131_w2_m15_official_single_target_4g_20261003"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
CAP_SECONDS = 120
RSS_CAP = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1",
         "--random=20261010", "--maxconfl=2000000"]

import importlib.util
spec = importlib.util.spec_from_file_location("n131_w14_diagonal_bilinear_run", HERE / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def public_target(curve):
    params = json.loads((OFFICIAL / "official_fixed_parameters.json").read_text())
    bridge = json.loads((OFFICIAL / "bridge_audit.json").read_text())
    assert bridge["status"] == "PASS"
    assert bridge["input_sha256"]["official_fixed_parameters"] == run.sha(
        OFFICIAL / "official_fixed_parameters.json")
    assert params["targets"][0]["id"] == "ecc2k-130"
    q = tuple(int(params["targets"][0][key], 16) for key in ("x", "y"))
    assert curve.on_curve(q) and curve.mul(run.R, q) is None
    return q


def sources():
    return {"query": Path(__file__), "run": HERE / "run.py",
            "circuit": HERE / "circuit.py", "construction_protocol": HERE / "protocol.json",
            "construction_profile": HERE / "profile.json",
            "sage_runtime_info": HERE / "sage_runtime_info.json",
            "previous_sage_group_audit": run.PREVIOUS / "sage_audit.json",
            "official_parameters": OFFICIAL / "official_fixed_parameters.json",
            "official_bridge": OFFICIAL / "bridge_audit.json",
            "solver": SOLVER}


def freeze():
    construction = json.loads((HERE / "profile.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert construction["status"] == "PASS_FULL_BILINEAR_FORMULA_CONSTRUCTED_GROUP_WITNESS"
    assert runtime["status"] == "verified"
    _, _, curve, _, control = run.source()
    q = public_target(curve)
    assert q != tuple(control["target_q"])
    record = {"status": "FROZEN_BEFORE_BILINEAR_PUBLISHED_QUERY",
              "candidate_id": None, "curve_id": construction["curve_id"],
              "target_id": "ecc2k-130", "target_q": list(q),
              "target_count": 1,
              "input_law": "one fixed published subgroup point; ten W14 diagonal masks and eight intermediate pair or upper reciprocals unpinned",
              "actual_projected_factor_base_B": 82200,
              "folded_columns_K": 8160,
              "query_wall_cap_seconds": CAP_SECONDS,
              "rss_cap_bytes": RSS_CAP,
              "solver_flags": FLAGS,
              "source_sha256": {name: run.sha(path) for name, path in sources().items()}}
    run.save(HERE / "query_protocol.json", record)
    print(json.dumps({"status": record["status"], "target_q": list(q)}))


def query():
    protocol_path = HERE / "query_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_BILINEAR_PUBLISHED_QUERY"
    assert protocol["source_sha256"] == {name: run.sha(path)
                                           for name, path in sources().items()}
    result_dir = HERE / "public_query"
    result_dir.mkdir(exist_ok=False)
    _, _, curve, _, _ = run.source()
    q = public_target(curve)
    assert list(q) == protocol["target_q"]
    started = time.monotonic()
    instance, meta, lifts = run.formula_for(q)
    formula = Path("/private/tmp/n131_w14_diagonal_bilinear_public.xcnf")
    if formula.exists():
        raise FileExistsError(formula)
    instance.write(formula)
    build_seconds = time.monotonic() - started
    formula_record = {"variables": instance.next_var-1,
                      "clauses": len(instance.clauses),
                      "xor_rows": len(instance.xors),
                      "and_gates": instance.and_count,
                      "bilinear_pair_ands": meta["bilinear_pair_ands"],
                      "duplicate_column_clauses": meta["duplicate_column_clauses"],
                      "bytes": formula.stat().st_size,
                      "sha256": run.sha(formula)}
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    if build_seconds >= CAP_SECONDS-5 or peak_rss > RSS_CAP:
        raise RuntimeError("formula construction exceeded query gate")
    remaining = CAP_SECONDS-build_seconds-1
    command = [str(SOLVER), *FLAGS,
               f"--maxtime={max(1,int(remaining)-2)}", str(formula)]
    stdout_path, stderr_path = result_dir / "solver.stdout.txt", result_dir / "solver.stderr.txt"
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        process = psutil.Process(child.pid)
        stop_reason = None
        cpu_seconds = 0.0
        solve_started = time.monotonic()
        while child.poll() is None:
            try:
                peak_rss = max(peak_rss, parent.memory_info().rss+process.memory_info().rss)
                cpu = process.cpu_times()
                cpu_seconds = max(cpu_seconds, cpu.user+cpu.system)
            except psutil.NoSuchProcess:
                pass
            if peak_rss > RSS_CAP:
                stop_reason = "RSS_CAP"
            elif time.monotonic()-started >= CAP_SECONDS:
                stop_reason = "QUERY_WALL_CAP"
            elif time.monotonic()-solve_started >= remaining:
                stop_reason = "SOLVER_WALL_CAP"
            if stop_reason:
                child.terminate()
                break
            time.sleep(.1)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            stop_reason = (stop_reason or "DRAIN_TIMEOUT")+"_KILLED"
    solve_seconds = time.monotonic()-solve_started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    check = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = run.base.read_model(output, formula_record["variables"])
        check = run.base.check_xcnf(formula, model)
        status = "SAT_MODEL_PENDING_INDEPENDENT_GROUP_REPLAY"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason in ("QUERY_WALL_CAP", "SOLVER_WALL_CAP") or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    with formula.open("rb") as inp, gzip.open(result_dir / "system.xcnf.gz", "xb", compresslevel=6) as out:
        while block := inp.read(1 << 20):
            out.write(block)
    formula.unlink()
    receipt = {"status": status, "candidate_id": None,
               "curve_id": protocol["curve_id"], "target_count": 1,
               "target_q": list(q), "raw_target_preimages": [list(p) for p in lifts],
               "formula": formula_record, "solver_command": command,
               "solver_status_lines": statuses, "model_lines": model_lines,
               "solver_exit_code": child.returncode, "stop_reason": stop_reason,
               "producer_xcnf_check": check,
               "verified_relations": 0, "useful_rank": 0,
               "phase_seconds": {"target_formula": build_seconds, "solver": solve_seconds,
                                 "query_wall": time.monotonic()-started},
               "sampled_peak_combined_rss_bytes": peak_rss,
               "sampled_solver_cpu_seconds": cpu_seconds,
               "sha256": {"protocol": run.sha(protocol_path),
                          "stdout": run.sha(stdout_path),
                          "stderr": run.sha(stderr_path),
                          "formula_gzip": run.sha(result_dir / "system.xcnf.gz")}}
    run.save(result_dir / "result.json", receipt)
    print(json.dumps({"status": status,
                      "query_seconds": receipt["phase_seconds"]["query_wall"],
                      "formula": formula_record,
                      "peak_rss_bytes": peak_rss}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze","query"))
    {"freeze":freeze,"query":query}[parser.parse_args().mode]()
