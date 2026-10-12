#!/usr/bin/env python3
"""Compare bounded XOR-matrix settings on one frozen N83 target formula."""

import gzip
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/n83-geometric-m5-fixedtarget16-20261012"
sys.path.insert(0, str(ROOT / "experiments/m5-s3-gate-20261004"))
from run_gate import parse_model  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def parent_module():
    spec = importlib.util.spec_from_file_location("n83_fixed_target_parent", PARENT / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replay_model_on_parent(model, protocol):
    runner = parent_module()
    parent_protocol = json.loads((PARENT / "protocol.json").read_text())
    parent_result = json.loads((PARENT / "width16_ordinary.json").read_text())
    row = parent_protocol["base_rows"][0]
    onb = runner.field.Onb(83)
    curve = runner.curves.Curve(onb)
    order = parent_protocol["workload"]["subgroup_order"]
    public = tuple(protocol["public_point_onb_raw"])
    base_keys = runner.base_x_keys(row, onb, runner.OrbitKey(onb))
    kernel, _, _ = runner.kernel_of_cofactor(curve, onb, order, 4, 141783)
    raw_targets, _ = runner.raw_preimage_coset(onb, curve, order, 4, public, kernel)
    rotated_targets, target_xs = runner.normalized_target_coset(
        onb, curve, public, raw_targets)
    formula, leaves, selector = runner.build_affine_formula(
        16, row["offset_onb_coordinates"], target_xs, onb)
    assert runner.stats(formula) == parent_result["formula_shape"]
    assignment = dict(model)
    assignment[1] = True
    return runner.replay_normalized(
        onb, curve, order, 16, base_keys, public, raw_targets,
        rotated_targets, leaves, selector, assignment)


def solve(binary, xcnf, arm, protocol):
    command = [str(binary), "--verb", "1", "--threads", "1", "--maxconfl",
               str(protocol["max_conflicts"]), *arm["extra_flags"], str(xcnf)]
    started = time.perf_counter_ns()
    deadline = started + int(protocol["wall_seconds_per_arm"] * 1e9)
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    monitor = psutil.Process(process.pid)
    peak = 0
    while True:
        try:
            peak = max(peak, monitor.memory_info().rss)
        except psutil.NoSuchProcess:
            pass
        if peak > protocol["sampled_solver_rss_stop_bytes"]:
            process.kill()
            stdout, stderr = process.communicate()
            status = "sampled_rss_cap_exceeded"
            break
        remaining = (deadline - time.perf_counter_ns()) / 1e9
        if remaining <= 0:
            process.kill()
            stdout, stderr = process.communicate()
            status = "external_timeout"
            break
        try:
            stdout, stderr = process.communicate(timeout=min(0.05, remaining))
            status = ("sat" if process.returncode == 10 else
                      "unsat" if process.returncode == 20 else
                      "conflict_cap_indeterminate" if process.returncode == 15 and
                      "s INDETERMINATE" in stdout else "censored" if
                      process.returncode == 0 else "solver_failure")
            break
        except subprocess.TimeoutExpired:
            continue
    matches = re.findall(r"conflicts\s*[:=]\s*([0-9]+)", stdout,
                         flags=re.IGNORECASE)
    matrices = re.findall(r"Using\s+([0-9]+)\s+matrices", stdout)
    return {
        "status": status,
        "return_code": process.returncode,
        "wall_seconds": (time.perf_counter_ns() - started) / 1e9,
        "observed_peak_solver_rss_bytes": peak,
        "rss_sample_interval_ms": 50,
        "conflicts_reported": int(matches[-1]) if matches else None,
        "matrices_used_reported": [int(value) for value in matrices],
        "model": parse_model(stdout) if status == "sat" else None,
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
    }


def main():
    protocol_path = HERE / "protocol.json"
    output_path = HERE / "result.json"
    raw_path = HERE / "input.xcnf"
    assert not output_path.exists() and not raw_path.exists()
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101251"
    assert protocol["rss_monitor_library"] == f"psutil {psutil.__version__}"
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(PARENT / "protocol.json") == protocol["parent_protocol_sha256"]
    assert sha(PARENT / "width16_ordinary.json") == protocol[
        "parent_result_sha256"]
    archive = ROOT / protocol["xcnf_gzip"]
    assert sha(archive) == protocol["xcnf_gzip_sha256"]
    with gzip.open(archive, "rb") as stream:
        raw = stream.read()
    assert len(raw) == protocol["xcnf_raw_bytes"]
    assert hashlib.sha256(raw).hexdigest() == protocol["xcnf_raw_sha256"]
    raw_path.write_bytes(raw)
    binary = Path(protocol["solver_path"])
    assert sha(binary) == protocol["solver_sha256"]
    record = {
        "kind": "n83_fixed_target_xcnf_gaussian_matrix_diagnostic",
        "status": "running",
        "proposal_id": protocol["proposal_id"],
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "protocol_sha256": sha(protocol_path),
        "xcnf_raw_sha256": protocol["xcnf_raw_sha256"],
        "arms": [],
        "timing_tier": protocol["timing_tier"],
    }
    save(output_path, record)
    for arm in protocol["arms"]:
        result = solve(binary, raw_path, arm, protocol)
        stdout_path = HERE / f"{arm['name']}.stdout.txt"
        stderr_path = HERE / f"{arm['name']}.stderr.txt"
        stdout_path.write_text(result.pop("stdout"))
        stderr_path.write_text(result.pop("stderr"))
        model = result.pop("model")
        replay = None if model is None else replay_model_on_parent(
            model, protocol)
        record["arms"].append({
            "name": arm["name"], "extra_flags": arm["extra_flags"],
            **result,
            "stdout_file": stdout_path.name, "stdout_sha256": sha(stdout_path),
            "stderr_file": stderr_path.name, "stderr_sha256": sha(stderr_path),
            "model_present": model is not None,
            "replay": replay,
        })
        save(output_path, record)
        print(json.dumps({"arm": arm["name"], "status": result["status"],
                          "conflicts": result["conflicts_reported"],
                          "matrices": result["matrices_used_reported"][-1:]}),
              flush=True)
        if replay is not None and replay["status"] == "verified_five_point_relation":
            break
    raw_path.unlink()
    record["status"] = "verified_relation" if any(
        arm["replay"] is not None and
        arm["replay"]["status"] == "verified_five_point_relation"
        for arm in record["arms"]) else "bounded_diagnostic_complete"
    save(output_path, record)


if __name__ == "__main__":
    main()
