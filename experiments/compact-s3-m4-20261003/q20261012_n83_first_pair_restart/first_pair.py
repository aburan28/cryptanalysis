#!/usr/bin/env python3
"""Measure work to first exact S3 pair across frozen N83 leaf restarts."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import platform
import re
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1481 = PARENT / "q20261011_n83_leaf_masks"
Q1479 = PARENT / "q20261011_n83_distinct_roots"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1488_first_pair_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def replace_once(data: str, old: str, new: str) -> str:
    assert data.count(old) == 1, old[:80]
    return data.replace(old, new)


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    previous = json.loads((Q1481 / "freeze.json").read_text())
    parent_build = json.loads((Q1481 / "build_receipt.json").read_text())
    source = Path(parent_build["patched_source_path"])
    assert sha(source) == parent_build["patched_wdsat_c_sha256"]
    assert protocol["phases"] == list(range(9))
    assert previous["inputs"]["selected"]["workload_id"] == protocol[
        "selected_workload_id"]
    assert previous["inputs"]["holdout"]["workload_id"] == protocol[
        "holdout_workload_id"]
    frozen = {
        "proposal_id": "Q1488", "candidate_id": None, "run_id": None,
        "files_sha256": {n: sha(HERE / n) for n in
                         ("protocol.json", "first_pair.py", "validate.py")},
        "q1481_freeze_sha256": sha(Q1481 / "freeze.json"),
        "q1481_build_sha256": sha(Q1481 / "build_receipt.json"),
        "q1481_root_samples_sha256": sha(Q1481 / "root_samples.json"),
        "q1479_analyze_source_sha256": sha(Q1479 / "analyze.py"),
        "q1481_phase_receipts_sha256": {
            f"{n}_phase{i}": sha(Q1481 / "runs" / f"{n}_phase{i}" / "receipt.json")
            for n in ("selected", "holdout") for i in range(9)},
        "parent_source_path": str(source),
        "parent_source_sha256": sha(source),
        "parent_config_sha256": sha(source.parent / "config.h"),
        "mask_schedule": previous["mask_schedule"],
        "inputs": previous["inputs"],
    }
    save(HERE / "freeze.json", frozen)
    print("Q1488 frozen", sha(HERE / "freeze.json")[:12])


def patch(source: Path) -> str:
    path = source / "wdsat.c"
    data = path.read_text()
    data = replace_once(data, "static void q1479_capture_pair1(void) {",
                        "static void q1479_capture_pair1(int_t branch_count) {")
    data = replace_once(data, "static void q1478_snapshot(void) {",
                        "static void q1478_snapshot(int_t branch_count) {")
    data = replace_once(data, "            q1479_capture_pair1();",
                        "            q1479_capture_pair1(branch_count);")
    data = replace_once(data, "    q1478_snapshot();",
                        "    q1478_snapshot(count);")
    old = '''    fprintf(stderr, "Q1479_PAIR1 %u %s\\n", q1479_count, bits);
    fflush(stderr);'''
    new = '''    fprintf(stderr, "Q1479_PAIR1 %u %s\\n", q1479_count, bits);
    if (q1479_count == 1)
        fprintf(stderr, "Q1488_FIRST_PAIR %lld %llu %llu %s\\n",
                (long long)branch_count, q1473_cnf_calls,
                q1473_xor_calls, bits);
    fflush(stderr);'''
    data = replace_once(data, old, new)
    path.write_text(data)
    return sha(path)


def build() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    parent = json.loads((Q1481 / "build_receipt.json").read_text())
    assert frozen["files_sha256"]["first_pair.py"] == sha(Path(__file__))
    source = Path(frozen["parent_source_path"])
    assert sha(source) == frozen["parent_source_sha256"] == parent[
        "patched_wdsat_c_sha256"]
    BUILD.mkdir(parents=True)
    shutil.copytree(source.parent, BUILD / "src")
    modified = patch(BUILD / "src")
    process = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                             capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(process.stdout)
    (HERE / "build.stderr.txt").write_text(process.stderr)
    binary = BUILD / "wdsat_solver"
    assert process.returncode == 0 and binary.exists(), process.stderr[-2000:]
    save(HERE / "build_receipt.json", {
        "proposal_id": "Q1488", "candidate_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "q1481_build_sha256": sha(Q1481 / "build_receipt.json"),
        "patched_wdsat_c_sha256": modified,
        "patched_source_path": str(BUILD / "src/wdsat.c"),
        "binary_path": str(binary), "binary_sha256": sha(binary),
        "config_sha256": sha(BUILD / "src/config.h"),
        "compiler": subprocess.check_output(["gcc", "--version"],
                                             text=True).splitlines()[0],
        "architecture": platform.machine(), "os": platform.platform(),
        "return_code": process.returncode,
        "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
        "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
        "source_sha256": sha(Path(__file__)),
    })
    print("Q1488 built", sha(binary)[:12])


def cpu_limit(soft: int, hard: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def run_cell(name: str, phase: int, protocol: dict, frozen: dict,
             build_receipt: dict) -> dict:
    folder = HERE / "runs" / f"{name}_phase{phase}"
    assert not folder.exists()
    folder.mkdir(parents=True)
    cell = frozen["inputs"][name]
    archive = Path(cell["derived_path"])
    assert sha(archive) == cell["derived_sha256"]
    data = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(data).hexdigest() == cell["derived_raw_sha256"]
    binary = Path(build_receipt["binary_path"])
    assert sha(binary) == build_receipt["binary_sha256"]
    env = os.environ.copy()
    env.update(Q1469_ORDER_MODE=protocol["branch_order"],
               Q1472_PHASE_INDEX="0", Q1473_SELECTOR_PHASE="0",
               Q1481_LEAF_MASK=str(phase))
    stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    started, usage0 = time.monotonic(), resource.getrusage(resource.RUSAGE_CHILDREN)
    marker_seen = wall_cap = False
    with tempfile.TemporaryDirectory(prefix="q1488_", dir="/Volumes/SSD990/llm/tmp") as tmp:
        system = Path(tmp) / "system.xcnf"
        system.write_bytes(data)
        with stdout.open("wb") as out, stderr.open("wb") as err:
            child = subprocess.Popen([str(binary), "-i", str(system)],
                                     stdout=out, stderr=err, env=env,
                                     preexec_fn=cpu_limit(
                                         protocol["cpu_soft_seconds_per_cell"],
                                         protocol["cpu_hard_seconds_per_cell"]))
            deadline = time.monotonic() + protocol["wall_seconds_per_cell"]
            pattern = re.compile(rb"^Q1488_FIRST_PAIR \d+ \d+ \d+ [01]{166}$", re.M)
            while child.poll() is None:
                if pattern.search(stderr.read_bytes()):
                    marker_seen = True
                    child.terminate()
                    break
                if time.monotonic() >= deadline:
                    wall_cap = True
                    child.terminate()
                    break
                time.sleep(0.05)
            try:
                code = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                code = child.wait(timeout=5)
    elapsed = time.monotonic() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    log = stderr.read_text(errors="replace")
    markers = [(int(a), int(b), int(c), bits) for a, b, c, bits in
               re.findall(r"^Q1488_FIRST_PAIR (\d+) (\d+) (\d+) ([01]{166})$",
                          log, re.M)]
    assert len(markers) <= 1
    marker_seen = marker_seen or bool(markers)
    mask_count = len(frozen["mask_schedule"][str(phase)]["flip_ids"])
    marker_ok = (log.splitlines().count(
        f"Q1469_ORDER {protocol['branch_order']} 168") == 1 and
        log.splitlines().count("Q1472_PHASE 0 0") == 1 and
        log.splitlines().count("Q1473_SELECTOR_PHASE 0 2140 2141") == 1 and
        log.splitlines().count(f"Q1481_MASK {phase} {mask_count}") == 1)
    search_started = "Q1458_SEARCH_START" in log
    if markers and search_started and marker_ok:
        status = "FIRST_PAIR_TERMINATED"
    elif wall_cap and search_started:
        status = "WALL_CAP_SEARCH_STARTED"
    elif wall_cap:
        status = "CENSORED_BEFORE_SEARCH"
    elif code in (-signal.SIGXCPU, -signal.SIGKILL):
        status = "CPU_CAP_SEARCH_STARTED" if search_started else "CPU_CAP_BEFORE_SEARCH"
    elif code == 0 and stdout.stat().st_size:
        status = "MODEL_REQUIRES_REPLAY"
    else:
        status = "PRODUCER_FAILURE"
    pair = markers[0] if markers else None
    row = {
        "proposal_id": "Q1488", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": cell["workload_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "isogeny": "none", "input": name, "phase": phase,
        "flip_count": mask_count, "status": status, "return_code": code,
        "marker_ok": marker_ok, "search_started": search_started,
        "marker_seen": marker_seen, "wall_cap": wall_cap,
        "first_pair_branch": pair[0] if pair else None,
        "first_pair_cnf_calls": pair[1] if pair else None,
        "first_pair_xor_calls": pair[2] if pair else None,
        "first_pair_bits": pair[3] if pair else None,
        "first_pair_combined_calls": pair[1] + pair[2] if pair else None,
        "solver_wall_seconds_exploratory": elapsed,
        "solver_user_cpu_seconds_exploratory": usage.ru_utime - usage0.ru_utime,
        "solver_system_cpu_seconds_exploratory": usage.ru_stime - usage0.ru_stime,
        "child_peak_rss_cumulative_bytes_darwin": usage.ru_maxrss,
        "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
        "binary_sha256": build_receipt["binary_sha256"],
        "input_sha256": cell["derived_sha256"],
        "freeze_sha256": sha(HERE / "freeze.json"),
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    }
    save(folder / "receipt.json", row)
    print("Q1488", name, phase, status, row["first_pair_branch"],
          row["first_pair_combined_calls"], flush=True)
    return row


def run() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build_receipt = json.loads((HERE / "build_receipt.json").read_text())
    assert all(sha(HERE / name) == digest for name, digest in
               frozen["files_sha256"].items())
    rows = [run_cell(name, phase, protocol, frozen, build_receipt)
            for name in ("selected", "holdout") for phase in protocol["phases"]]
    save(HERE / "drive_receipt.json", {
        "proposal_id": "Q1488", "candidate_id": None, "run_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "rows": [{"input": r["input"], "phase": r["phase"],
                  "status": r["status"],
                  "receipt_sha256": sha(HERE / "runs" /
                                        f"{r['input']}_phase{r['phase']}" /
                                        "receipt.json")} for r in rows],
        "new_ordinary_attempts": len(rows),
        "solver_wall_phase_sum_seconds_exploratory": sum(
            r["solver_wall_seconds_exploratory"] for r in rows),
        "solver_user_cpu_sum_seconds_exploratory": sum(
            r["solver_user_cpu_seconds_exploratory"] for r in rows),
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    })


def analyze() -> None:
    assert not (HERE / "analysis.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    older = json.loads((Q1481 / "root_samples.json").read_text())
    spec = importlib.util.spec_from_file_location(
        "q1479_root_replay", Q1479 / "analyze.py")
    assert spec and spec.loader
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    onb = prior.CountedOnb(83)
    points, samples = {}, {}
    for item in drive["rows"]:
        name, phase = item["input"], item["phase"]
        key = f"{name}_phase{phase}"
        folder = HERE / "runs" / key
        row = json.loads((folder / "receipt.json").read_text())
        assert sha(folder / "receipt.json") == item["receipt_sha256"]
        exact = prior.replay_pair(onb, row["first_pair_bits"]) if row[
            "first_pair_bits"] else None
        if exact:
            assert exact["root_coords"] == older[key][0]["root_coords"]
            assert row["first_pair_bits"] == older[key][0]["leaf_bits"]
        samples[key] = exact
        baseline = json.loads((Q1481 / "runs" / key / "receipt.json").read_text())
        cap_work = baseline["work_at_cap"]
        assert cap_work is not None
        points[key] = {
            "workload_id": row["workload_id"], "status": row["status"],
            "first_pair_branch": row["first_pair_branch"],
            "first_pair_combined_calls": row["first_pair_combined_calls"],
            "full_32768_branch_combined_calls": cap_work[1] + cap_work[2],
            "root_count": exact["root_count"] if exact else None,
            "root_field_api_entries": exact["field_api_entries"] if exact else None,
            "receipt_sha256": item["receipt_sha256"],
            "q1481_receipt_sha256": frozen["q1481_phase_receipts_sha256"][key],
        }
    sample_path = HERE / "root_samples.json"
    save(sample_path, samples)
    completed = [p for p in points.values() if p["status"] == "FIRST_PAIR_TERMINATED"]
    result = {
        "proposal_id": "Q1488", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
        "controlled_change": protocol["controlled_change"],
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "root_samples_sha256": sha(sample_path),
        "analysis_source_sha256": sha(Path(__file__)),
        "points": points,
        "first_pair_completed_attempts": len(completed),
        "selected_unique_pairs": len({older[f"selected_phase{i}"][0]["leaf_bits"]
                                     for i in protocol["phases"]})
            if all(samples[f"selected_phase{i}"] for i in protocol["phases"]) else None,
        "natural_relation_yield": None, "novel_rank_per_query": None,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    }
    save(HERE / "analysis.json", result)
    print("Q1488", {k: (p["first_pair_branch"], p["first_pair_combined_calls"],
                        p["root_count"]) for k, p in points.items()})


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {
            "freeze", "build", "run", "analyze"}:
        raise SystemExit("usage: first_pair.py {freeze|build|run|analyze}")
    globals()[sys.argv[1]]()
