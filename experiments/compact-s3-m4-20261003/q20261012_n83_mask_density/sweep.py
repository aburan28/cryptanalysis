#!/usr/bin/env python3
"""Freeze and measure N83 leaf-mask density at the first S3 pair boundary."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import platform
import random
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
Q1488 = PARENT / "q20261012_n83_first_pair_restart"
Q1479 = PARENT / "q20261011_n83_distinct_roots"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1491_mask_density_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def schedule(protocol: dict) -> dict:
    lo, hi = protocol["leaf_variable_ids_inclusive"]
    population = list(range(lo, hi + 1))
    out = {}
    for j, count in enumerate(protocol["flip_counts"]):
        assert 0 < count < len(population)
        for rep in range(protocol["replicas_per_count"]):
            phase = 9 + j * protocol["replicas_per_count"] + rep
            seed = protocol["seed_base"] + phase
            out[str(phase)] = {"flip_count": count, "replica": rep,
                               "seed": seed,
                               "flip_ids": sorted(random.Random(seed).sample(
                                   population, count))}
    assert len(out) == len(set(tuple(x["flip_ids"]) for x in out.values()))
    return out


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = load(HERE / "protocol.json")
    parent = load(Q1488 / "build_receipt.json")
    parent_freeze = load(Q1488 / "freeze.json")
    source = Path(parent["patched_source_path"])
    assert sha(source) == parent["patched_wdsat_c_sha256"]
    assert parent_freeze["inputs"]["selected"]["workload_id"] == protocol[
        "selected_workload_id"]
    assert parent_freeze["inputs"]["holdout"]["workload_id"] == protocol[
        "holdout_workload_id"]
    save(HERE / "freeze.json", {
        "proposal_id": "Q1491", "candidate_id": None, "run_id": None,
        "files_sha256": {n: sha(HERE / n) for n in
                         ("protocol.json", "sweep.py", "validate.py")},
        "q1488_build_receipt_sha256": sha(Q1488 / "build_receipt.json"),
        "q1488_freeze_sha256": sha(Q1488 / "freeze.json"),
        "q1479_replay_source_sha256": sha(Q1479 / "analyze.py"),
        "parent_source_path": str(source),
        "parent_source_sha256": sha(source),
        "parent_config_sha256": sha(source.parent / "config.h"),
        "inputs": parent_freeze["inputs"],
        "mask_schedule": schedule(protocol),
    })
    print("Q1491 frozen", sha(HERE / "freeze.json")[:12])


def patch(src: Path, masks: dict) -> str:
    path = src / "wdsat.c"
    data = path.read_text()
    old = "phase < 0 || phase > 8"
    assert data.count(old) == 1
    data = data.replace(old, f"phase < 0 || phase > {max(map(int, masks))}")
    anchor = "static unsigned char q1481_mark[__ID_SIZE__];"
    assert data.count(anchor) == 1
    arrays = "\n".join(
        f"static const int_t q1491_mask_{i}[] = {{" +
        ", ".join(map(str, masks[str(i)]["flip_ids"])) + "};"
        for i in sorted(map(int, masks)))
    data = data.replace(anchor, arrays + "\n" + anchor)
    choice_anchor = "    default: exit(64);"
    assert data.count(choice_anchor) == 1
    choices = "\n".join(
        f"    case {i}: flips = q1491_mask_{i}; "
        f"length = sizeof(q1491_mask_{i}) / sizeof(q1491_mask_{i}[0]); break;"
        for i in sorted(map(int, masks)))
    data = data.replace(choice_anchor, choices + "\n" + choice_anchor)
    path.write_text(data)
    return sha(path)


def build() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = load(HERE / "freeze.json")
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    source = Path(frozen["parent_source_path"])
    assert sha(source) == frozen["parent_source_sha256"]
    BUILD.mkdir(parents=True)
    shutil.copytree(source.parent, BUILD / "src")
    modified = patch(BUILD / "src", frozen["mask_schedule"])
    process = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                             capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(process.stdout)
    (HERE / "build.stderr.txt").write_text(process.stderr)
    binary = BUILD / "wdsat_solver"
    assert process.returncode == 0 and binary.exists(), process.stderr[-2000:]
    save(HERE / "build_receipt.json", {
        "proposal_id": "Q1491", "candidate_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "patched_source_path": str(BUILD / "src/wdsat.c"),
        "patched_source_sha256": modified,
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
    print("Q1491 built", sha(binary)[:12])


def cpu_limit(soft: int, hard: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def run_cell(input_name: str, phase: int, protocol: dict, frozen: dict,
             built: dict) -> dict:
    folder = HERE / "runs" / f"{input_name}_phase{phase}"
    assert not folder.exists()
    folder.mkdir(parents=True)
    cell = frozen["inputs"][input_name]
    archive = Path(cell["derived_path"])
    assert sha(archive) == cell["derived_sha256"]
    raw = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
    binary = Path(built["binary_path"])
    assert sha(binary) == built["binary_sha256"]
    env = os.environ.copy()
    env.update(Q1469_ORDER_MODE=protocol["branch_order"],
               Q1472_PHASE_INDEX="0", Q1473_SELECTOR_PHASE="0",
               Q1481_LEAF_MASK=str(phase))
    stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    started, usage0 = time.monotonic(), resource.getrusage(resource.RUSAGE_CHILDREN)
    marker_seen = wall_cap = False
    with tempfile.TemporaryDirectory(prefix="q1491_", dir="/Volumes/SSD990/llm/tmp") as tmp:
        system = Path(tmp) / "system.xcnf"
        system.write_bytes(raw)
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
    mask_count = frozen["mask_schedule"][str(phase)]["flip_count"]
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
        "proposal_id": "Q1491", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": cell["workload_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "isogeny": "none", "input": input_name, "phase": phase,
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
        "binary_sha256": built["binary_sha256"],
        "input_sha256": cell["derived_sha256"],
        "freeze_sha256": sha(HERE / "freeze.json"),
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    }
    save(folder / "receipt.json", row)
    print("Q1491", input_name, phase, status,
          row["first_pair_combined_calls"], flush=True)
    return row


def replay(row: dict) -> dict:
    spec = importlib.util.spec_from_file_location("q1479_replay", Q1479 / "analyze.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    onb = module.CountedOnb(83)
    result = module.replay_pair(onb, row["first_pair_bits"])
    return result


def summarize(rows: list[dict], protocol: dict) -> dict:
    counts = protocol["flip_counts"]
    out = {}
    for count in counts:
        sub = [r for r in rows if r["flip_count"] == count]
        completed = [r for r in sub if r["status"] == "FIRST_PAIR_TERMINATED"]
        positives = [r for r in completed if r["root_count"] == 2]
        calls = sum(r["first_pair_combined_calls"] for r in completed)
        out[str(count)] = {
            "attempts": len(sub), "completed": len(completed),
            "two_root_pairs": len(positives),
            "distinct_pairs": len({r["first_pair_bits"] for r in completed}),
            "combined_cnf_xor_calls_completed": calls,
            "combined_cnf_xor_calls_per_two_root_pair":
                calls / len(positives) if positives and len(completed) == len(sub)
                else None,
            "censored_or_failed_attempts": len(sub) - len(completed),
        }
    return out


def run() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    protocol, frozen, built = (load(HERE / n) for n in
                               ("protocol.json", "freeze.json", "build_receipt.json"))
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    assert sha(HERE / "freeze.json") == built["freeze_sha256"]
    rows = []
    for phase in sorted(map(int, frozen["mask_schedule"])):
        row = run_cell("selected", phase, protocol, frozen, built)
        if row["status"] == "FIRST_PAIR_TERMINATED":
            row["root_count"] = replay(row)["root_count"]
        rows.append(row)
    selected = summarize(rows, protocol)
    eligible = [(values["combined_cnf_xor_calls_per_two_root_pair"], int(count))
                for count, values in selected.items()
                if values["combined_cnf_xor_calls_per_two_root_pair"] is not None]
    best = min(eligible)[1] if eligible else None
    holdout = []
    if best is not None:
        for phase in sorted(map(int, frozen["mask_schedule"])):
            if frozen["mask_schedule"][str(phase)]["flip_count"] == best:
                row = run_cell("holdout", phase, protocol, frozen, built)
                if row["status"] == "FIRST_PAIR_TERMINATED":
                    row["root_count"] = replay(row)["root_count"]
                holdout.append(row)
    save(HERE / "drive_receipt.json", {
        "proposal_id": "Q1491", "candidate_id": None, "run_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "build_receipt_sha256": sha(HERE / "build_receipt.json"),
        "selected_count": best, "selected_summary": selected,
        "selected_attempts": len(rows), "holdout_attempts": len(holdout),
        "solver_wall_sum_seconds_exploratory": sum(
            r["solver_wall_seconds_exploratory"] for r in rows + holdout),
        "rows": [{"input": r["input"], "phase": r["phase"],
                  "receipt_sha256": sha(HERE / "runs" /
                                        f"{r['input']}_phase{r['phase']}" /
                                        "receipt.json")}
                 for r in rows + holdout],
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    })
    print("Q1491 selected count", best, selected, flush=True)


def analyze() -> None:
    protocol, frozen, drive = (load(HERE / n) for n in
                               ("protocol.json", "freeze.json", "drive_receipt.json"))
    assert drive["freeze_sha256"] == sha(HERE / "freeze.json")
    rows = []
    for item in drive["rows"]:
        path = HERE / "runs" / f"{item['input']}_phase{item['phase']}" / "receipt.json"
        assert sha(path) == item["receipt_sha256"]
        row = load(path)
        assert row["freeze_sha256"] == drive["freeze_sha256"]
        if row["status"] == "FIRST_PAIR_TERMINATED":
            assert row["marker_ok"] and row["search_started"]
            row["root_count"] = replay(row)["root_count"]
        rows.append(row)
    selected = [r for r in rows if r["input"] == "selected"]
    holdout = [r for r in rows if r["input"] == "holdout"]
    assert summarize(selected, protocol) == drive["selected_summary"]
    assert len(selected) == drive["selected_attempts"]
    assert len(holdout) == drive["holdout_attempts"]
    matching_holdout_pairs = sum(
        row["first_pair_bits"] is not None and row["first_pair_bits"] ==
        next(x for x in selected if x["phase"] == row["phase"])["first_pair_bits"]
        for row in holdout)
    result = {
        "proposal_id": "Q1491", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "point_decomposition_stage_code": "PDP4sat", "isogeny": "none",
        "selected_workload_id": protocol["selected_workload_id"],
        "holdout_workload_id": protocol["holdout_workload_id"],
        "selected_summary": drive["selected_summary"],
        "promoted_flip_count": drive["selected_count"],
        "holdout_summary": summarize(holdout, protocol) if holdout else None,
        "selected_unique_pairs": len({r["first_pair_bits"] for r in selected
                                      if r["first_pair_bits"] is not None}),
        "holdout_pair_matches_selected": matching_holdout_pairs,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "analysis_source_sha256": sha(Path(__file__)),
        "natural_relation_yield": None,
        "novel_rank_per_query": None,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    }
    save(HERE / "analysis.json", result)
    print("Q1491 analyzed", result["promoted_flip_count"],
          result["selected_unique_pairs"])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "build", "run", "analyze"):
        raise SystemExit("usage: sweep.py {freeze|build|run|analyze}")
    globals()[sys.argv[1]]()
