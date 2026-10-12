#!/usr/bin/env python3
"""Frozen selected-point sweep of exact common-root implication subsets."""
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
Q1486 = PARENT / "q20261011_n83_common_bit_propagation"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1487_common_subset_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def replace_once(data: str, old: str, new: str) -> str:
    assert data.count(old) == 1, old[:80]
    return data.replace(old, new)


def mask_positions(common: list[int], variant: dict) -> list[int]:
    k, mode = variant["k"], variant["mode"]
    assert 1 <= k <= len(common)
    if mode == "first":
        return common[:k]
    if mode == "last":
        return common[-k:]
    if mode == "middle":
        assert k == 1
        return [common[len(common) // 2]]
    if mode == "spread":
        assert k > 1
        return [common[j * (len(common) - 1) // (k - 1)] for j in range(k)]
    raise ValueError(mode)


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    previous = json.loads((Q1486 / "freeze.json").read_text())
    parent_build = json.loads((Q1486 / "build_receipt.json").read_text())
    source = Path(parent_build["patched_source_path"])
    assert sha(source) == parent_build["patched_wdsat_c_sha256"]
    roots = previous["supported_middle_root_coords"]
    root_bits = ["".join("1" if value >> i & 1 else "0" for i in range(83))
                 for value in roots]
    common = [i for i in range(83) if root_bits[0][i] == root_bits[1][i]]
    assert len(common) == 49
    variants = {}
    for spec in protocol["selected_variants"]:
        indexes = mask_positions(common, spec)
        assert len(indexes) == len(set(indexes)) == spec["k"]
        variants[spec["id"]] = {
            "positions": indexes,
            "mask_bits": "".join("1" if i in indexes else "0" for i in range(83)),
        }
    assert len(variants) == len(protocol["selected_variants"])
    frozen = {
        "proposal_id": "Q1487", "candidate_id": None, "run_id": None,
        "files_sha256": {n: sha(HERE / n) for n in
                         ("protocol.json", "sweep.py", "validate.py")},
        "q1486_freeze_sha256": sha(Q1486 / "freeze.json"),
        "q1486_build_sha256": sha(Q1486 / "build_receipt.json"),
        "q1486_analysis_source_sha256": sha(Q1486 / "analyze.py"),
        "q1486_phase4_receipts_sha256": {
            n: sha(Q1486 / "runs" / f"{n}_phase4" / "receipt.json")
            for n in ("selected", "holdout")},
        "parent_source_path": str(source),
        "parent_source_sha256": sha(source),
        "parent_config_sha256": sha(source.parent / "config.h"),
        "supported_pair1_bits": previous["supported_pair1_bits"],
        "supported_middle_root_coords": roots,
        "common_positions": common,
        "variants": variants,
        "inputs": {n: previous["inputs"][n] for n in ("selected", "holdout")},
        "mask_schedule": previous["mask_schedule"],
    }
    assert frozen["inputs"]["selected"]["workload_id"] == protocol[
        "selected_workload_id"]
    assert frozen["inputs"]["holdout"]["workload_id"] == protocol[
        "holdout_workload_id"]
    save(HERE / "freeze.json", frozen)
    print("Q1487 frozen", sha(HERE / "freeze.json")[:12])


def patch(source: Path) -> str:
    path = source / "wdsat.c"
    data = path.read_text()
    anchor = "static int_t q1486_next_common_literal(void) {"
    loader = '''/* Q1487: restrict exact implications to a frozen 83-bit subset. */
static char q1487_mask[84];
static bool q1487_mask_loaded = false;
static void q1487_load_mask(void) {
    if (q1487_mask_loaded) return;
    const char *raw = getenv("Q1487_MASK");
    if (!raw || strlen(raw) != 83) {
        fprintf(stderr, "Q1487_BAD_MASK\\n"); fflush(stderr); exit(64);
    }
    int count = 0;
    for (int i = 0; i < 83; ++i) {
        if (raw[i] != '0' && raw[i] != '1') {
            fprintf(stderr, "Q1487_BAD_MASK\\n"); fflush(stderr); exit(64);
        }
        if (raw[i] == '1') {
            if (q1483_root_bits[0][i] != q1483_root_bits[1][i]) {
                fprintf(stderr, "Q1487_NONCOMMON_BIT\\n"); fflush(stderr); exit(64);
            }
            ++count;
        }
        q1487_mask[i] = raw[i];
    }
    q1487_mask[83] = 0;
    q1487_mask_loaded = true;
    fprintf(stderr, "Q1487_MASK %d %s\\n", count, q1487_mask);
    fflush(stderr);
}
'''
    data = replace_once(data, anchor, loader + anchor)
    data = replace_once(data, "    ++q1486_checks;\n    for (int i = 0; i < 10; ++i) {",
                        "    ++q1486_checks;\n    q1487_load_mask();\n"
                        "    for (int i = 0; i < 10; ++i) {")
    data = replace_once(
        data,
        "if (q1483_root_bits[0][i] == q1483_root_bits[1][i] &&\n"
        "            _cnf_is_undef(var))",
        "if (q1487_mask[i] == '1' &&\n"
        "            q1483_root_bits[0][i] == q1483_root_bits[1][i] &&\n"
        "            _cnf_is_undef(var))")
    path.write_text(data)
    return sha(path)


def build() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    parent_build = json.loads((Q1486 / "build_receipt.json").read_text())
    assert frozen["files_sha256"]["sweep.py"] == sha(Path(__file__))
    source = Path(frozen["parent_source_path"])
    assert sha(source) == frozen["parent_source_sha256"] == parent_build[
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
        "proposal_id": "Q1487", "candidate_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "q1486_build_sha256": sha(Q1486 / "build_receipt.json"),
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
    print("Q1487 built", sha(binary)[:12])


def cpu_limit(soft: int, hard: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def marker(log: str, label: str, count: int) -> tuple[int, ...] | None:
    found = [tuple(map(int, m.split())) for m in re.findall(
        rf"^{label} ({count} [0-9 ]+)$", log, re.M)]
    assert len(found) <= 1, (label, found)
    return found[0] if found else None


def run_cell(name: str, variant: str, protocol: dict, frozen: dict,
             build_receipt: dict) -> dict:
    folder = HERE / "runs" / f"{name}_{variant}"
    assert not folder.exists()
    folder.mkdir(parents=True)
    cell = frozen["inputs"][name]
    archive = Path(cell["derived_path"])
    assert sha(archive) == cell["derived_sha256"]
    data = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(data).hexdigest() == cell["derived_raw_sha256"]
    binary = Path(build_receipt["binary_path"])
    assert sha(binary) == build_receipt["binary_sha256"]
    mask = frozen["variants"][variant]["mask_bits"]
    env = os.environ.copy()
    env.update(Q1469_ORDER_MODE=protocol["branch_order"],
               Q1472_PHASE_INDEX="0", Q1473_SELECTOR_PHASE="0",
               Q1481_LEAF_MASK=str(protocol["polarity_phase"]),
               Q1487_MASK=mask)
    stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    started, usage0 = time.monotonic(), resource.getrusage(resource.RUSAGE_CHILDREN)
    checkpoint_seen = wall_cap = False
    with tempfile.TemporaryDirectory(prefix="q1487_", dir="/Volumes/SSD990/llm/tmp") as tmp:
        system = Path(tmp) / "system.xcnf"
        system.write_bytes(data)
        with stdout.open("wb") as out, stderr.open("wb") as err:
            child = subprocess.Popen([str(binary), "-i", str(system)],
                                     stdout=out, stderr=err, env=env,
                                     preexec_fn=cpu_limit(
                                         protocol["cpu_soft_seconds_per_cell"],
                                         protocol["cpu_hard_seconds_per_cell"]))
            deadline = time.monotonic() + protocol["wall_seconds_per_cell"]
            pattern = re.compile(rb"^Q1479_SUMMARY " + str(
                protocol["branch_checkpoint"]).encode() + rb" ", re.M)
            while child.poll() is None:
                if pattern.search(stderr.read_bytes()):
                    checkpoint_seen = True
                    child.terminate()
                    break
                if time.monotonic() >= deadline:
                    wall_cap = True
                    child.terminate()
                    break
                time.sleep(0.2)
            try:
                code = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                code = child.wait(timeout=5)
    elapsed = time.monotonic() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    log = stderr.read_text(errors="replace")
    cap = protocol["branch_checkpoint"]
    work = marker(log, "Q1473_WORK", cap)
    distinct = marker(log, "Q1479_SUMMARY", cap)
    propagation = marker(log, "Q1486_PROPAGATE", cap)
    mask_markers = re.findall(r"^Q1487_MASK (\d+) ([01]{83})$", log, re.M)
    marker_ok = (len(mask_markers) == 1 and
                 mask_markers[0] == (str(mask.count("1")), mask) and
                 log.splitlines().count(
                     f"Q1469_ORDER {protocol['branch_order']} 168") == 1 and
                 log.splitlines().count("Q1472_PHASE 0 0") == 1 and
                 log.splitlines().count("Q1473_SELECTOR_PHASE 0 2140 2141") == 1)
    search_started = "Q1458_SEARCH_START" in log
    if work and distinct and propagation and search_started and marker_ok:
        status = "CHECKPOINT_TERMINATED"
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
    found = re.findall(r"^Q1479_PAIR1 \d+ ([01]{166})$", log, re.M)
    assert len(found) == len(set(found))
    row = {
        "proposal_id": "Q1487", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": cell["workload_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "isogeny": "none", "input": name, "variant": variant,
        "selected_positions": frozen["variants"][variant]["positions"],
        "mask_bits": mask, "status": status, "return_code": code,
        "marker_ok": marker_ok, "search_started": search_started,
        "checkpoint_seen": checkpoint_seen, "wall_cap": wall_cap,
        "branch_lower_bound": cap if work else 0,
        "work_at_cap": work, "distinct_summary_at_cap": distinct,
        "propagation_at_cap": propagation, "sampled_pair1_count": len(found),
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
    print("Q1487", name, variant, status,
          work[1] + work[2] if work else None,
          distinct[1] if distinct else None, flush=True)
    return row


def run() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build_receipt = json.loads((HERE / "build_receipt.json").read_text())
    assert all(sha(HERE / name) == digest for name, digest in
               frozen["files_sha256"].items())
    rows = []
    for spec in protocol["selected_variants"]:
        rows.append(run_cell("selected", spec["id"], protocol, frozen,
                             build_receipt))
    eligible = [r for r in rows if r["status"] == "CHECKPOINT_TERMINATED"]
    ordered = sorted(eligible, key=lambda r: (
        -r["distinct_summary_at_cap"][1],
        r["work_at_cap"][1] + r["work_at_cap"][2],
        r["variant"]))
    promoted = [r["variant"] for r in ordered[:2]]
    for variant in promoted:
        rows.append(run_cell("holdout", variant, protocol, frozen, build_receipt))
    save(HERE / "drive_receipt.json", {
        "proposal_id": "Q1487", "candidate_id": None, "run_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "selected_variants": [s["id"] for s in protocol["selected_variants"]],
        "promoted_variants": promoted, "selection_eligible_count": len(eligible),
        "rows": [{"input": r["input"], "variant": r["variant"],
                  "status": r["status"],
                  "receipt_sha256": sha(HERE / "runs" /
                                        f"{r['input']}_{r['variant']}" /
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
    print("Q1487 promoted", promoted)


def analyze() -> None:
    assert not (HERE / "analysis.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    spec = importlib.util.spec_from_file_location(
        "q1486_root_replay", Q1486 / "analyze.py")
    assert spec and spec.loader
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    onb = prior.CountedOnb(83)
    points, samples = {}, {}
    cap = protocol["branch_checkpoint"]
    for item in drive["rows"]:
        name, variant = item["input"], item["variant"]
        folder = HERE / "runs" / f"{name}_{variant}"
        row = json.loads((folder / "receipt.json").read_text())
        assert sha(folder / "receipt.json") == item["receipt_sha256"]
        log = (folder / "solver.stderr.txt").read_text()
        work = marker(log, "Q1473_WORK", cap)
        distinct = marker(log, "Q1479_SUMMARY", cap)
        propagation = marker(log, "Q1486_PROPAGATE", cap)
        bits = re.findall(r"^Q1479_PAIR1 \d+ ([01]{166})$", log, re.M)
        exact = [prior.exact_roots(onb, value) for value in bits]
        assert len(exact) == row["sampled_pair1_count"]
        key = f"{name}_{variant}"
        samples[key] = exact
        points[key] = {
            "workload_id": row["workload_id"], "status": row["status"],
            "variant": variant, "selected_bit_count": len(row["selected_positions"]),
            "combined_cnf_xor_calls_at_cap": work[1] + work[2] if work else None,
            "distinct_pair1_count_at_cap": distinct[1] if distinct else None,
            "forced_literals_at_cap": propagation[3] if propagation else None,
            "sampled_root_count_distribution": {
                str(k): sum(x["root_count"] == k for x in exact) for k in (0, 1, 2)},
            "sampled_root_field_api_entries": sum(x["field_api_entries"] for x in exact),
            "sample_cap_reached": len(exact) == protocol[
                "distinct_pair1_sample_cap_per_cell"],
            "receipt_sha256": item["receipt_sha256"],
        }
    sample_path = HERE / "root_samples.json"
    save(sample_path, samples)
    save(HERE / "analysis.json", {
        "proposal_id": "Q1487", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
        "controlled_change": protocol["controlled_change"],
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "root_samples_sha256": sha(sample_path),
        "analysis_source_sha256": sha(Path(__file__)),
        "selected_variants": drive["selected_variants"],
        "promoted_variants": drive["promoted_variants"],
        "points": points, "natural_relation_yield": None,
        "novel_rank_per_query": None,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    })
    print("Q1487 analysis", {k: (v["combined_cnf_xor_calls_at_cap"],
                                  v["distinct_pair1_count_at_cap"])
                              for k, v in points.items()})


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {
            "freeze", "build", "run", "analyze"}:
        raise SystemExit("usage: sweep.py {freeze|build|run|analyze}")
    globals()[sys.argv[1]]()
