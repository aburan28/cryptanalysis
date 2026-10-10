#!/usr/bin/env python3
"""Run one hash-pinned Kissat cell and retain its full stage receipt."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import tempfile
import time

from converter import check_model, convert, sha

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def git_blob(repo: Path, commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), "show", f"{commit}:{path}"])


def source_input(repo: Path, cfg: dict, cell: str) -> tuple[bytes, bytes]:
    record = cfg["cells"][cell]
    packed = git_blob(repo, cfg["input_commit"], record["xcnf_path"])
    if sha(packed) != record["gzip_sha256"]:
        raise ValueError("compressed XCNF hash differs")
    raw = gzip.decompress(packed)
    if sha(raw) != record["raw_sha256"]:
        raise ValueError("raw XCNF hash differs")
    if record["unit_path"] is None:
        if record["unit_sha256"] is not None:
            raise ValueError("unexpected unit hash")
        units = b""
    else:
        units = git_blob(repo, cfg["input_commit"], record["unit_path"])
        if sha(units) != record["unit_sha256"]:
            raise ValueError("unit delta hash differs")
    return raw, units


def rss_bytes(pid: int) -> int:
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("RSS sampler failed: " + result.stderr.strip())
    return int(result.stdout.strip() or "0") * 1024


def save_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run_cell(repo: Path, cell: str, scratch: Path) -> dict:
    cfg = json.loads((HERE / "source.json").read_text())
    if cfg["schema"] != "ecc2k130-xcnf-kissat-bridge-v1" or cell not in cfg["cells"]:
        raise ValueError("unfrozen cell")
    output_dir = HERE / "runs/R1"
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = output_dir / f"{cell}.json"
    stdout_archive = output_dir / f"{cell}.stdout.txt.gz"
    stderr_path = output_dir / f"{cell}.stderr.txt"
    if any(path.exists() for path in (receipt_path, stdout_archive, stderr_path)):
        raise FileExistsError("cell evidence already exists")
    solver_name = shutil.which("kissat")
    if solver_name is None:
        raise FileNotFoundError("Kissat unavailable")
    solver = Path(solver_name).resolve()
    if sha(solver.read_bytes()) != cfg["kissat_sha256"]:
        raise ValueError("Kissat executable hash differs")
    version = subprocess.check_output([str(solver), "--version"], text=True).strip()
    if version != cfg["kissat_version"]:
        raise ValueError("Kissat version differs")
    if rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS sampler preflight failed before solver launch")
    started = time.monotonic_ns()
    raw, units = source_input(repo, cfg, cell)
    cnf, formula = convert(raw, units)
    prep_ms = (time.monotonic_ns() - started) / 1e6
    control = cell.endswith("control_z0")
    internal_s = 20 if control else 120
    external_s = 30 if control else 150
    cap_bytes = 4 * (1 << 30)
    with tempfile.TemporaryDirectory(prefix="ecc2k130-kissat-", dir=scratch) as name:
        temp = Path(name)
        cnf_file = temp / "input.cnf"
        cnf_file.write_bytes(cnf)
        if sha(cnf_file.read_bytes()) != formula["cnf_sha256"]:
            raise ValueError("materialized CNF differs")
        command = [str(solver), f"--time={internal_s}", str(cnf_file)]
        stdout_file = temp / "stdout.txt"
        temporary_stderr = temp / "stderr.txt"
        solver_start = time.monotonic_ns()
        peak_rss = 0
        guard = None
        with stdout_file.open("wb") as stdout, temporary_stderr.open("wb") as stderr:
            child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                     start_new_session=True)
            while True:
                pid, status, usage = os.wait4(child.pid, os.WNOHANG)
                if pid:
                    exit_code = os.waitstatus_to_exitcode(status)
                    break
                elapsed_s = (time.monotonic_ns() - solver_start) / 1e9
                try:
                    peak_rss = max(peak_rss, rss_bytes(child.pid))
                except RuntimeError:
                    guard = "RSS_SAMPLER_FAILURE"
                if peak_rss > cap_bytes:
                    guard = "RSS_CAP"
                elif elapsed_s > external_s:
                    guard = "WALL_CAP"
                if guard:
                    os.killpg(child.pid, signal.SIGKILL)
                    _, status, usage = os.wait4(child.pid, 0)
                    exit_code = os.waitstatus_to_exitcode(status)
                    break
                time.sleep(0.25)
        solver_wall_ms = (time.monotonic_ns() - solver_start) / 1e6
        output = stdout_file.read_bytes()
        error = temporary_stderr.read_bytes()
        terminals = [line.decode(errors="replace") for line in output.splitlines()
                     if line.startswith(b"s ")]
        if guard == "RSS_CAP":
            result = "OOM_GUARD"
        elif guard == "WALL_CAP" or terminals == ["s UNKNOWN"] and exit_code == 0:
            result = "BOUNDED_UNKNOWN"
        elif guard:
            result = "PRODUCER_FAILURE"
        elif terminals == ["s SATISFIABLE"] and exit_code == 10:
            result = "SAT_XCNF_MODEL_VERIFIED"
        elif terminals == ["s UNSATISFIABLE"] and exit_code == 20:
            result = "UNSAT_UNVERIFIED"
        else:
            result = "PRODUCER_FAILURE"
        model_replay = check_model(raw, units, output) if result == "SAT_XCNF_MODEL_VERIFIED" else None
        with stdout_archive.open("xb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target,
                               mtime=0) as zipped:
                zipped.write(output)
        stderr_path.write_bytes(error)
        child_maxrss = usage.ru_maxrss if platform.system() == "Darwin" else usage.ru_maxrss * 1024
        receipt = {
            "schema": "ecc2k130-xcnf-kissat-cell-v1",
            "cell": cell, "status": result, "candidate_id": None,
            "input_commit": cfg["input_commit"],
            "source_manifest_sha256": sha((HERE / "source.json").read_bytes()),
            "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes()),
            "converter_sha256": sha((HERE / "converter.py").read_bytes()),
            "runner_sha256": sha(Path(__file__).read_bytes()),
            "solver_sha256": cfg["kissat_sha256"],
            "solver_version": version, "command": command[:-1] + ["<hashed-CNF>"],
            "formula": formula, "preparation_wall_ms": prep_ms,
            "solver_wall_ms": solver_wall_ms,
            "solver_user_cpu_s": usage.ru_utime,
            "solver_system_cpu_s": usage.ru_stime,
            "sampled_peak_rss_bytes": peak_rss,
            "reported_child_peak_rss_bytes": child_maxrss,
            "rss_cap_bytes": cap_bytes, "internal_time_cap_s": internal_s,
            "external_wall_cap_s": external_s, "guard": guard,
            "exit_code": exit_code, "terminal": terminals,
            "stdout_sha256": sha(output),
            "stdout_gzip_sha256": sha(stdout_archive.read_bytes()),
            "stderr_sha256": sha(error),
            "model_replay": model_replay,
            "verified_group_relation": None,
            "novel_rank": None,
            "environment": {"platform": platform.platform(),
                            "machine": platform.machine(),
                            "python": platform.python_version(),
                            "cpu_isolation": "unverified"},
        }
        save_json(receipt_path, receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell", required=True)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--scratch-dir", type=Path, default=Path("/private/tmp"))
    args = parser.parse_args()
    receipt = run_cell(args.repo.resolve(), args.cell, args.scratch_dir)
    print(json.dumps({key: receipt[key] for key in (
        "cell", "status", "exit_code", "solver_wall_ms", "sampled_peak_rss_bytes")},
        sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
