#!/usr/bin/env python3
"""Freeze and run an ordinary-query PDP holdout; this is not a DLP benchmark."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

from n53_group import Curve, Field, GENERATOR, R

HERE = Path(__file__).resolve().parent
CRYPTO = Path("/Volumes/SSD990/crypto")
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
SOURCE = HERE / "koblitz_w3_root_holdout.rs"
EXAMPLE = CRYPTO / "examples/koblitz_w3_root_holdout.rs"
BINARY = CRYPTO / "target/release/examples/koblitz_w3_root_holdout"
REPS = HERE / "runs/n53_w3_base_export_v1/representatives.json"
PARENT_CANDIDATE = "IC1N53Ckb1fb23426PDP4rootRCguidedLAgaussTDdirectISO0hd89d75bbe48f"
CURVE_ID = "EC1N53Ckb1hb75cbed53fce"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def panel(seed, count):
    curve = Curve(Field())
    points, audit, seen = [], [], set()
    for index in range(count):
        material = f"N53-W3-ROOT-ORDINARY-PDP-HOLDOUT-v1|{seed}|{index}".encode()
        scalar = 1 + int.from_bytes(hashlib.sha256(material).digest(), "big") % (R - 1)
        point = curve.mul(GENERATOR, scalar)
        if point is None or point in seen or not curve.on_curve(point):
            raise ValueError(f"invalid or duplicate fixture at {index}")
        seen.add(point)
        points.append(list(point))
        audit.append(scalar)
    prior = {tuple(json.loads(path.read_text())["record"]["target_point"])
             for path in HERE.glob("runs/n53_w3_root_pair_v*/workload.json")}
    if prior & seen:
        raise ValueError("holdout contains a prior one-target benchmark point")
    return points, audit


def run_bounded(command, out, limit):
    stdout_path, stderr_path = out / "solver.stdout.txt", out / "solver.stderr.txt"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        started = time.perf_counter_ns()
        proc = subprocess.Popen(list(map(str, command)), cwd=CRYPTO,
                                stdout=stdout, stderr=stderr)
        launch_end = time.perf_counter_ns()
        timed_out = False
        while True:
            pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
            if pid:
                exit_code = os.waitstatus_to_exitcode(status)
                proc.returncode = exit_code
                break
            if (time.perf_counter_ns() - launch_end) / 1e9 >= limit:
                timed_out = True
                proc.kill()
                _, status, usage = os.wait4(proc.pid, 0)
                exit_code = os.waitstatus_to_exitcode(status)
                proc.returncode = exit_code
                break
            time.sleep(0.01)
        ended = time.perf_counter_ns()
    return {"command": list(map(str, command)), "exit_code": exit_code,
            "external_timeout": timed_out, "process_launch_ns": launch_end - started,
            "process_wall_ns": ended - launch_end,
            "peak_rss_bytes": usage.ru_maxrss if platform.system() == "Darwin"
                              else usage.ru_maxrss * 1024,
            "child_user_cpu_s": usage.ru_utime, "child_system_cpu_s": usage.ru_stime,
            "external_wall_limit_seconds": limit,
            "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261004)
    parser.add_argument("--count", type=int, default=256)
    parser.add_argument("--wall-seconds", type=int, default=300)
    args = parser.parse_args()
    if not 1 <= args.count <= 1024 or args.wall_seconds < 1:
        raise ValueError("invalid count or wall limit")
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("holdout output is immutable")
    if sha(SOURCE) != sha(EXAMPLE):
        raise ValueError("compiled example source differs from archived source")
    points, audit = panel(args.seed, args.count)
    workload = {
        "curve_id": CURVE_ID, "subgroup_order": R, "generator": list(GENERATOR),
        "public_points": points, "target_count": args.count,
        "input_law": "sha256_seeded_nonzero_scalar_times_G; public points only to solver",
        "fixture_seed": args.seed,
        "precomputation_state": "target_independent_W3_base_and_root_index_ready",
        "cold_or_warm": "warm_index_multi_query_stage_diagnostic",
    }
    workload_id = hashlib.sha256(canonical(workload)).hexdigest()[:12]
    out.mkdir(parents=True)
    shutil.copy2(BINARY, out / "solver_binary")
    save(out / "workload.json", {"workload_id": workload_id, "record": workload})
    save(out / "fixture_audit.json", {"scalars_not_given_to_solver": audit})
    (out / "public_points.json").write_bytes(canonical(points) + b"\n")
    with (out / "sage_runtime_info.json").open("wb") as runtime:
        subprocess.run([str(SAGE), "--runtime-info"], stdout=runtime, check=True)
    command = [out / "solver_binary", out / "public_points.json", REPS,
               out / "result.jsonl"]
    execution = run_bounded(command, out, args.wall_seconds)
    lines = (out / "result.jsonl").read_text().splitlines() if (out / "result.jsonl").exists() else []
    parsed, malformed_lines = [], []
    for index, line in enumerate(lines):
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            malformed_lines.append(index)
    header = parsed[0] if parsed else None
    rows = parsed[1:] if header else []
    statuses = Counter(row.get("status", "MISSING_STATUS") for row in rows)
    complete = (execution["exit_code"] == 0 and not execution["external_timeout"]
                and not malformed_lines and header is not None
                and header.get("query_count") == args.count and len(rows) == args.count
                and all(row.get("query_index") == i and row.get("target_point") == points[i]
                        for i, row in enumerate(rows)))
    receipt = {
        "schema_version": 1, "kind": "n53_w3_root_ordinary_pdp_holdout",
        "status": "PANEL_COMPLETE_PENDING_SAGE_REPLAY" if complete else "PANEL_INCOMPLETE",
        "candidate_id": None, "parent_candidate_id": PARENT_CANDIDATE,
        "curve_id": CURVE_ID, "workload_id": workload_id,
        "stage_question": "operational full-index PDP completion on a frozen ordinary-query panel",
        "not_a_full_ic_dlp_or_cpu_speedup_measurement": True,
        "cpu_isolation_status": "unverified_mac_host",
        "source_sha256": {"rust_example": sha(SOURCE), "runner": sha(Path(__file__)),
                          "n53_group": sha(HERE / "n53_group.py"),
                          "representatives": sha(REPS),
                          "Cargo.lock": sha(CRYPTO / "Cargo.lock"),
                          "crypto_lib": sha(CRYPTO / "src/lib.rs"),
                          "binary_ecc_mod": sha(CRYPTO / "src/binary_ecc/mod.rs"),
                          "binary_ecc_curve": sha(CRYPTO / "src/binary_ecc/curve.rs"),
                          "binary_ecc_f2m": sha(CRYPTO / "src/binary_ecc/f2m.rs"),
                          "binary_ecc_poly_f2m": sha(CRYPTO / "src/binary_ecc/poly_f2m.rs"),
                          "binary_ecc_hyperelliptic": sha(CRYPTO / "src/binary_ecc/hyperelliptic.rs"),
                          "fast_arith": sha(CRYPTO / "src/cryptanalysis/koblitz_fast_arith.rs"),
                          "index_calculus": sha(CRYPTO / "src/cryptanalysis/koblitz_index_calculus.rs"),
                          "semaev_decomp": sha(CRYPTO / "src/cryptanalysis/semaev_decomp.rs")},
        "binary_sha256": sha(out / "solver_binary"),
        "runtime_info_sha256": sha(out / "sage_runtime_info.json"),
        "public_input_sha256": sha(out / "public_points.json"),
        "fixture_audit_sha256": sha(out / "fixture_audit.json"),
        "result_sha256": sha(out / "result.jsonl") if (out / "result.jsonl").exists() else None,
        "execution": execution, "header": header,
        "recorded_query_count": len(rows), "malformed_line_indices": malformed_lines,
        "unrecorded_query_count": args.count - len(rows), "status_counts": dict(statuses),
        "independent_sage_replay_status": None,
    }
    save(out / "receipt.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("status", "workload_id", "recorded_query_count",
                                                "unrecorded_query_count", "status_counts")}))


if __name__ == "__main__":
    main()
