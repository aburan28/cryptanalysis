#!/usr/bin/env python3
"""Freeze and run free-selector Q1420 projective-S3 bilinear XCNFs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "runs/R1"
BILINEAR = HERE.parent / "ecc2k130-263-bilinear-leaf-20261010"
sys.path.insert(0, str(BILINEAR))
import bilinear  # noqa: E402


ref = bilinear.ref
finite = bilinear.finite
projective = bilinear.projective
POLICIES = ("source", "descendant_native")
VARIANTS = bilinear.VARIANTS


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, row):
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")


def checked_config():
    cfg = ref.read(HERE / "CONFIG.json")
    if (cfg["schema"] != "ecc2k130-263-bilinear-ordinary-q0-v1"
            or cfg["parent_commit"]
            != "038b540daa780b62420c1a213c19e0e83b776311"
            or cfg["workload_id"] != "eee7f6ee5f6b"
            or cfg["policies"] != list(POLICIES)
            or cfg["variants"] != list(VARIANTS)
            or cfg["run_order"] != [[policy, variant] for variant in VARIANTS
                                     for policy in POLICIES]
            or cfg["threads"] != 1 or cfg["internal_wall_seconds"] != 120
            or cfg["external_wall_seconds"] != 150
            or cfg["peak_rss_cap_bytes"] != 4 * (1 << 30)
            or any(ref.sha(ROOT / name) != digest
                   for name, digest in cfg["pins"].items())):
        raise ValueError("source, workload, or protocol differs from freeze")
    workload = ref.read(ref.INPUT / "primary_workload.json")
    prior = ref.read(projective.HERE / "runs/R1/audit.json")
    if (workload["workload_id"] != cfg["workload_id"]
            or workload["target_count"] != 1
            or prior["status"]
            != "PASS_PROJECTIVE_FORMULAS_AND_BOUNDED_SOLVER_TRANSCRIPTS"):
        raise ValueError("paired public query or baseline audit differs")
    for policy in POLICIES:
        if prior["policies"][policy]["pilot"]["status"] != "BOUNDED_UNKNOWN":
            raise ValueError("baseline status changed")
    return cfg


def paths(policy, variant):
    stem = f"{policy}_{variant}"
    return (RUN / f"{stem}.xcnf.gz", RUN / f"{stem}.inputs.json",
            RUN / f"{stem}.formula.json")


def build_formula(policy, variant, scratch):
    cfg = checked_config()
    if policy not in POLICIES or variant not in VARIANTS:
        raise ValueError("unfrozen cell")
    archive, named_path, receipt_path = paths(policy, variant)
    if any(path.exists() for path in (archive, named_path, receipt_path)):
        raise FileExistsError("formula input is already frozen")
    started = time.perf_counter()
    lifts = finite.target_lifts(policy)
    if lifts != [int(x) for x in cfg["target_x_choices"][policy]]:
        raise ValueError("public target lift set changed")
    projective.check_inputs(policy)
    with tempfile.TemporaryDirectory(prefix="ordinary-build-", dir=scratch) as temp:
        baseline_path = Path(temp) / "baseline.xcnf"
        prog, roots, leaves, _ = projective.build_ir(policy)
        baseline, _, _ = bilinear.control.encode_with_map(
            policy, prog, roots, leaves, lifts)
        baseline.writeDimacs(baseline_path)
        baseline_sha = ref.sha(baseline_path)
        if baseline_sha != cfg["baseline_raw_sha256"][policy]:
            raise ValueError("named-input encoder did not reproduce comparator")
        del baseline, prog, roots, leaves
        prog, roots, leaves, _ = bilinear.build_ir(policy, variant)
        ir_ops = prog.opCount(roots)
        formula, choice, literals = bilinear.control.encode_with_map(
            policy, prog, roots, leaves, lifts)
        raw_path = Path(temp) / "variant.xcnf"
        formula.writeDimacs(raw_path)
        raw_sha, raw_bytes = ref.sha(raw_path), raw_path.stat().st_size
        RUN.mkdir(parents=True, exist_ok=True)
        with raw_path.open("rb") as source, archive.open("xb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target,
                               mtime=0) as zipped:
                shutil.copyfileobj(source, zipped, length=1 << 20)
    named = {f"{name}:{bit}": lit for (name, bit), lit in literals.items()}
    save_json(named_path, named)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    row = {
        "schema": "ecc2k130-263-bilinear-ordinary-formula-v1",
        "status": "FORMULA_FROZEN",
        "policy": policy, "variant": variant, "candidate_id": None,
        "workload_id": cfg["workload_id"], "query_index": 0,
        "baseline_reproduced_sha256": baseline_sha,
        "target_x_choices": [str(x) for x in lifts],
        "target_selector_variables": choice,
        "actual_usable_points_B": cfg["usable_points_B_each"],
        "formula_raw_sha256": raw_sha, "formula_raw_bytes": raw_bytes,
        "formula_gzip_sha256": ref.sha(archive),
        "formula_gzip_bytes": archive.stat().st_size,
        "named_inputs_sha256": ref.sha(named_path),
        "named_inputs_count": len(named),
        "stats": formula.stats(), "ir_operations": ir_ops,
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "producer_sha256": ref.sha(Path(__file__)),
        "bilinear_sha256": ref.sha(BILINEAR / "bilinear.py"),
        "build_wall_seconds": time.perf_counter() - started,
        "peak_process_rss_bytes": peak,
    }
    save_json(receipt_path, row)
    print(json.dumps({"policy": policy, "variant": variant,
                      "baseline_sha256": baseline_sha,
                      "formula_sha256": raw_sha,
                      "stats": row["stats"],
                      "build_wall_seconds": row["build_wall_seconds"]},
                     sort_keys=True), flush=True)


def frozen_formula(policy, variant, cfg):
    archive, named_path, receipt_path = paths(policy, variant)
    row = ref.read(receipt_path)
    if (row["schema"] != "ecc2k130-263-bilinear-ordinary-formula-v1"
            or row["status"] != "FORMULA_FROZEN"
            or row["policy"] != policy or row["variant"] != variant
            or row["workload_id"] != cfg["workload_id"]
            or row["baseline_reproduced_sha256"]
            != cfg["baseline_raw_sha256"][policy]
            or row["target_x_choices"] != cfg["target_x_choices"][policy]
            or row["actual_usable_points_B"] != cfg["usable_points_B_each"]
            or row["formula_gzip_sha256"] != ref.sha(archive)
            or row["named_inputs_sha256"] != ref.sha(named_path)
            or row["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or row["producer_sha256"] != ref.sha(Path(__file__))
            or row["bilinear_sha256"] != ref.sha(BILINEAR / "bilinear.py")):
        raise ValueError("formula archive or receipt differs")
    return archive, named_path, receipt_path, row


def process_rss_bytes(pid):
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                            text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("RSS sampler unavailable: " + result.stderr.strip())
    value = result.stdout.strip()
    return int(value) * 1024 if value else 0


def run_solver(policy, variant, scratch):
    cfg = checked_config()
    archive, _, receipt_path, frozen = frozen_formula(policy, variant, cfg)
    stem = f"{policy}_{variant}"
    stdout_archive = RUN / f"{stem}.stdout.txt.gz"
    stderr_path = RUN / f"{stem}.stderr.txt"
    result_path = RUN / f"{stem}.solver.json"
    if any(path.exists() for path in (stdout_archive, stderr_path, result_path)):
        raise FileExistsError("solver evidence already exists")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 unavailable")
    solver = Path(solver_name).resolve()
    if ref.sha(solver) != cfg["solver_sha256"]:
        raise ValueError("solver binary changed")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")
    if process_rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS preflight returned no data")
    with tempfile.TemporaryDirectory(prefix="ordinary-run-", dir=scratch) as temp:
        raw = Path(temp) / "input.xcnf"
        with gzip.open(archive, "rb") as source, raw.open("xb") as target:
            shutil.copyfileobj(source, target, length=1 << 20)
        if (ref.sha(raw) != frozen["formula_raw_sha256"]
                or raw.stat().st_size != frozen["formula_raw_bytes"]):
            raise ValueError("solver input differs from precommitted formula")
        command = [str(solver), "--threads=1", "--maxtime=120",
                   "--verb=1", "--printsol=1", str(raw)]
        stdout_path = Path(temp) / "stdout.txt"
        started = time.perf_counter()
        peak, guard = 0, None
        with stdout_path.open("xb") as stdout, stderr_path.open("x") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            try:
                while process.poll() is None:
                    elapsed = time.perf_counter() - started
                    peak = max(peak, process_rss_bytes(process.pid))
                    if peak > cfg["peak_rss_cap_bytes"]:
                        guard = "RSS_CAP"
                    elif elapsed > cfg["external_wall_seconds"]:
                        guard = "WALL_CAP"
                    if guard:
                        os.killpg(process.pid, signal.SIGKILL)
                        break
                    time.sleep(0.25)
                exit_code = process.wait()
            except BaseException:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise
        wall = time.perf_counter() - started
        output = stdout_path.read_bytes()
        terminal = [line.strip() for line in output.decode(
            "utf-8", errors="replace").splitlines() if line.startswith("s ")]
        if guard == "RSS_CAP":
            status = "OOM_GUARD"
        elif guard == "WALL_CAP":
            status = "BOUNDED_UNKNOWN"
        elif terminal == ["s SATISFIABLE"] and exit_code == 10:
            status = "SAT_UNVERIFIED"
        elif terminal == ["s UNSATISFIABLE"] and exit_code == 20:
            status = "UNSAT"
        elif terminal == ["s INDETERMINATE"] and exit_code == 15:
            status = "BOUNDED_UNKNOWN"
        else:
            status = "PRODUCER_FAILURE"
        with stdout_archive.open("xb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target,
                               mtime=0) as zipped:
                zipped.write(output)
        child_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        if sys.platform != "darwin":
            child_peak *= 1024
        row = {
            "schema": "ecc2k130-263-bilinear-ordinary-solver-v1",
            "status": status, "candidate_id": None,
            "policy": policy, "variant": variant,
            "workload_id": cfg["workload_id"], "query_index": 0,
            "formula_sha256": ref.sha(raw),
            "formula_receipt_sha256": ref.sha(receipt_path),
            "config_sha256": ref.sha(HERE / "CONFIG.json"),
            "runner_sha256": ref.sha(Path(__file__)),
            "solver_sha256": ref.sha(solver), "solver_version": version,
            "command_flags": command[1:-1],
            "threads": cfg["threads"],
            "internal_wall_seconds": cfg["internal_wall_seconds"],
            "external_wall_seconds": cfg["external_wall_seconds"],
            "peak_rss_cap_bytes": cfg["peak_rss_cap_bytes"],
            "wall_seconds": wall,
            "peak_sampled_rss_bytes": peak,
            "peak_child_rss_bytes": child_peak,
            "guard": guard, "exit_code": exit_code,
            "terminal_status_lines": terminal,
            "stdout_raw_sha256": sha_bytes(output),
            "stdout_raw_bytes": len(output),
            "stdout_archive_sha256": ref.sha(stdout_archive),
            "stdout_archive_bytes": stdout_archive.stat().st_size,
            "stderr_sha256": ref.sha(stderr_path),
            "verified_decomposition": False,
            "novel_rank": None,
        }
        save_json(result_path, row)
    print(json.dumps({"policy": policy, "variant": variant,
                      "status": status, "wall_seconds": wall,
                      "guard": guard, "exit_code": exit_code},
                     sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "run"))
    parser.add_argument("--policy", choices=POLICIES, required=True)
    parser.add_argument("--variant", choices=VARIANTS, required=True)
    parser.add_argument("--scratch-dir", type=Path,
                        default=Path("/private/tmp"))
    args = parser.parse_args()
    if not args.scratch_dir.is_dir():
        parser.error("scratch directory does not exist")
    if args.action == "build":
        build_formula(args.policy, args.variant, args.scratch_dir)
    else:
        run_solver(args.policy, args.variant, args.scratch_dir)


if __name__ == "__main__":
    main()
