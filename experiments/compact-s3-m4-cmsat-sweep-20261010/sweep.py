#!/usr/bin/env python3
"""Freeze and run a bounded parameter sweep on archived balanced-S3 XCNFs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-20261003"
Q1419 = PARENT / "q1419_partial_pin/protocol.json"
PROPOSAL = "Q20261010125300"
INPUTS = {
    "n53_ordinary": "runs/n53_q1410_ordinary.xcnf.gz",
    "n83_ordinary": "runs/n83_q1408_ordinary.xcnf.gz",
    "n83_satisfiable_control": "runs/n83_q1408_planted_unpinned.xcnf.gz",
}
SETTINGS = {
    "default": [],
    "gauss_10000": ["--maxmatrixcols", "10000", "--autodisablegauss", "0"],
    "branch_vsids": ["--branchstr", "vsids"],
    "branch_vmtf": ["--branchstr", "vmtf"],
    "restart_geom": ["--restart", "geom"],
    "restart_luby": ["--restart", "luby"],
}
MAX_CONFLICTS = 200_000
WALL_CAP_SECONDS = 30.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write_new(path: Path, value: dict) -> None:
    assert not path.exists(), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def freeze() -> None:
    parent = read(Q1419)
    binary = Path(shutil.which("cryptominisat5") or "")
    assert binary.is_file()
    profiles = {}
    for n in (53, 83):
        p = parent["profiles"][str(n)]
        profiles[str(n)] = {
            "curve_id": p["curve_id"],
            "field_degree_n": n,
            "actual_usable_points_B": p["factor_base_actual_B"],
            "folded_columns_K": p["folded_columns_K"],
            "factor_base_enumerated_set_sha256":
                p["factor_base_enumerated_set_sha256"],
            "factor_base_receipt_sha256": p["factor_base_archive"]["sha256"],
            "isogeny": "none",
        }
        assert sha(ROOT / p["factor_base_archive"]["path"]) == (
            profiles[str(n)]["factor_base_receipt_sha256"])
    inputs = {name: {"path": str(PARENT / rel),
                     "compressed_sha256": sha(PARENT / rel),
                     "raw_sha256": hashlib.sha256(
                         gzip.decompress((PARENT / rel).read_bytes())).hexdigest()}
              for name, rel in INPUTS.items()}
    frozen = {
        "schema": "q20261010125300-cmsat-sweep-freeze-v1",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "isogeny": "none", "parent_q1419_protocol_sha256": sha(Q1419),
        "source_sha256": {name: sha(HERE / name)
                          for name in ("sweep.py", "audit.py", "PROTOCOL.md")},
        "solver_path": str(binary), "solver_sha256": sha(binary),
        "solver_version": subprocess.check_output(
            [str(binary), "--version"], text=True).strip(),
        "profiles": profiles, "inputs": inputs,
        "settings": SETTINGS, "cell_order": [[name, setting]
            for name in INPUTS for setting in SETTINGS],
        "max_conflicts": MAX_CONFLICTS,
        "external_wall_cap_seconds": WALL_CAP_SECONDS,
        "solver_seed": 0, "solver_threads": 1,
        "input_laws": {"n53_ordinary": "archived fixed ordinary public target",
                       "n83_ordinary": "archived fixed ordinary public target",
                       "n83_satisfiable_control":
                           "archived known-satisfiable constructed public target"},
    }
    write_new(HERE / "freeze.json", frozen)
    print(json.dumps({"status": "FROZEN", "sha256": sha(HERE / "freeze.json")}))


def check_freeze() -> dict:
    frozen = read(HERE / "freeze.json")
    assert frozen["proposal_id"] == PROPOSAL
    assert frozen["parent_q1419_protocol_sha256"] == sha(Q1419)
    for name, digest in frozen["source_sha256"].items():
        assert digest == sha(HERE / name)
    assert frozen["solver_sha256"] == sha(Path(frozen["solver_path"]))
    for name, entry in frozen["inputs"].items():
        path = Path(entry["path"])
        assert entry["compressed_sha256"] == sha(path)
        assert entry["raw_sha256"] == hashlib.sha256(
            gzip.decompress(path.read_bytes())).hexdigest()
        assert name in INPUTS
    assert frozen["settings"] == SETTINGS
    assert frozen["max_conflicts"] == MAX_CONFLICTS
    assert frozen["external_wall_cap_seconds"] == WALL_CAP_SECONDS
    return frozen


def execute(command: list[str], stdout_path: Path, stderr_path: Path) -> dict:
    started = time.monotonic()
    timed_out = False
    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        process = subprocess.Popen(command, stdout=out, stderr=err)
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic() - started >= WALL_CAP_SECONDS:
                timed_out = True
                process.kill()
                pid, status, usage = os.wait4(process.pid, 0)
                break
            time.sleep(0.02)
    return {"return_code": os.waitstatus_to_exitcode(status),
            "wall_seconds_exploratory": time.monotonic() - started,
            "external_timeout": timed_out,
            "peak_child_rss_ru_maxrss": usage.ru_maxrss,
            "peak_child_rss_unit": "bytes" if platform.system() == "Darwin"
                                   else "kilobytes"}


def run() -> None:
    frozen = check_freeze()
    runs = HERE / "runs"
    runs.mkdir(exist_ok=True)
    for name, setting in frozen["cell_order"]:
        label = f"{name}__{setting}"
        receipt_path = runs / f"{label}.json"
        if receipt_path.exists():
            continue
        with tempfile.TemporaryDirectory(prefix="q1253-s3-", dir="/private/tmp") as tmp:
            formula = Path(tmp) / "system.xcnf"
            started = time.monotonic()
            formula.write_bytes(gzip.decompress(
                Path(frozen["inputs"][name]["path"]).read_bytes()))
            decompress_seconds = time.monotonic() - started
            command = [frozen["solver_path"], "--verb", "1", "--threads", "1",
                       "--random", "0", "--maxconfl", str(MAX_CONFLICTS),
                       *SETTINGS[setting], str(formula)]
            stdout_path = runs / f"{label}.stdout"
            stderr_path = runs / f"{label}.stderr"
            assert not stdout_path.exists() and not stderr_path.exists()
            execution = execute(command, stdout_path, stderr_path)
            stdout = stdout_path.read_text(errors="replace")
            stderr = stderr_path.read_text(errors="replace")
            status = ("SAT" if execution["return_code"] == 10
                      else "UNSAT" if execution["return_code"] == 20
                      else "BOUNDED_UNKNOWN")
            if execution["external_timeout"]:
                assert status == "BOUNDED_UNKNOWN"
            matches = re.findall(r"Conflicts in UIP\s*:\s*([0-9]+)", stdout)
            conflicts = int(matches[-1]) if matches else None
            out_gz = stdout_path.with_suffix(".stdout.gz")
            err_gz = stderr_path.with_suffix(".stderr.gz")
            out_gz.write_bytes(gzip.compress(stdout.encode(), mtime=0))
            err_gz.write_bytes(gzip.compress(stderr.encode(), mtime=0))
            stdout_path.unlink()
            stderr_path.unlink()
            receipt = {
                "schema": "q20261010125300-cmsat-cell-v1",
                "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
                "isogeny": "none", "input_name": name, "setting": setting,
                "curve_id": frozen["profiles"][name[1:3]]["curve_id"],
                "actual_usable_points_B": frozen["profiles"][name[1:3]][
                    "actual_usable_points_B"],
                "folded_columns_K": frozen["profiles"][name[1:3]][
                    "folded_columns_K"],
                "factor_base_enumerated_set_sha256": frozen["profiles"][
                    name[1:3]]["factor_base_enumerated_set_sha256"],
                "freeze_sha256": sha(HERE / "freeze.json"),
                "formula_raw_sha256": frozen["inputs"][name]["raw_sha256"],
                "solver_sha256": frozen["solver_sha256"],
                "command_flags": command[1:-1], "status": status,
                "conflicts_reported": conflicts,
                "formula_decompression_seconds_exploratory": decompress_seconds,
                "stdout_gzip_sha256": sha(out_gz),
                "stderr_gzip_sha256": sha(err_gz),
                "stdout_bytes": len(stdout.encode()),
                "stderr_bytes": len(stderr.encode()),
                "stderr_nonempty": bool(stderr.strip()),
                **execution,
            }
            write_new(receipt_path, receipt)
            print(json.dumps({"cell": label, "status": status,
                              "conflicts": conflicts,
                              "wall_seconds": round(execution[
                                  "wall_seconds_exploratory"], 3)}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run"))
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    elif args.action == "check":
        check_freeze()
        print("PASS: frozen sources and inputs")
    else:
        run()


if __name__ == "__main__":
    main()
