#!/usr/bin/env python3
"""Independently audit archived formulas and both guarded solver runs."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path: Path, compressed: bool = False) -> str:
    h = hashlib.sha256()
    opener = gzip.open if compressed else Path.open
    with opener(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise AssertionError(reason)


def audit_cell(config: dict, run_id: str, name: str, variant: str) -> dict:
    stem = f"{name}_{variant}"
    directory = HERE / "runs" / run_id
    receipt = json.loads((directory / f"{stem}.json").read_text())
    stdout_path = directory / f"{stem}.stdout.txt"
    stderr_path = directory / f"{stem}.stderr.txt"
    output = stdout_path.read_text(errors="replace")
    errors = stderr_path.read_text(errors="replace")
    require(digest(stdout_path) == receipt["stdout_sha256"], f"stdout hash: {run_id}/{stem}")
    require(digest(stderr_path) == receipt["stderr_sha256"], f"stderr hash: {run_id}/{stem}")
    require(receipt["config_sha256"] == digest(HERE / "CONFIG.json"),
            f"config hash: {run_id}/{stem}")
    require(receipt["source"]["raw_sha256"] == config["formulas"][name]["raw_sha256"],
            f"source hash: {run_id}/{stem}")
    require(receipt["solver"]["solver_sha256"] == config["solver_sha256"],
            f"solver hash: {run_id}/{stem}")
    if run_id == "R2":
        require(receipt["runner_sha256"] == digest(HERE / "run_gate.py"),
                f"runner hash: {run_id}/{stem}")
    require(receipt["command"][1:-1] == config["base_flags"] + config["variants"][variant],
            f"solver flags: {run_id}/{stem}")
    require(receipt["verified_relation"] is False and receipt["novel_rank"] is None,
            f"unexpected relation claim: {run_id}/{stem}")
    restarts = [line for line in output.splitlines()
                if line.lstrip().startswith("c rst")]
    require(receipt["live_restart_rows"] == len(restarts), f"restart rows: {run_id}/{stem}")
    require(receipt["last_live_restart_row"] == (restarts[-1] if restarts else None),
            f"last restart: {run_id}/{stem}")
    recovered = [int(x) for x in re.findall(r"Using (\d+) matrices recovered", output)]
    require(recovered == receipt["matrix_recovery_counts"], f"matrices: {run_id}/{stem}")
    good = [(int(rows), int(cols)) for rows, cols in re.findall(
        r"Good\s+matrix\s+\d+.*?(\d{3,5}) x\s*(\d{3,5})", output, re.S)]
    calls = re.findall(r"elim called\s*:\s*(\d+[KM]?)", output)
    nonzero_calls = [value for value in calls if not re.fullmatch(r"0+", value)]
    if run_id == "R1":
        require(receipt["status"] == "PRODUCER_FAILURE"
                and "PermissionError" in receipt["producer_error"]
                and "ps" in receipt["producer_error"], f"R1 failure: {stem}")
    else:
        require(receipt["status"] == "BOUNDED_UNKNOWN", f"R2 status: {stem}")
        require(recovered and max(recovered) == 5 and len(restarts) > 0,
                f"R2 did not reach live search: {stem}")
        require(bool(re.search(r"s (SATISFIABLE|UNSATISFIABLE)", output)) is False,
                f"unexpected terminal answer: {stem}")
        if variant == "default":
            require(receipt["guard"] == "WALL_CAP" and receipt["exit_code"] == -9,
                    f"default terminal: {stem}")
            require(good and max(rows for rows, _ in good) < 2000,
                    f"default matrix dimensions: {stem}")
        else:
            require(receipt["guard"] is None and "s INDETERMINATE" in output,
                    f"large matrix terminal: {stem}")
            require(good and max(rows for rows, _ in good) >= 8000 and nonzero_calls,
                    f"large matrices inactive: {stem}")
    return {
        "run_id": run_id, "formula": name, "variant": variant,
        "status": receipt["status"], "wall_seconds": receipt["wall_seconds"],
        "peak_observed_rss_bytes": receipt["peak_observed_rss_bytes"],
        "matrix_recovery_counts": recovered,
        "largest_good_matrix": list(max(good)) if good else None,
        "nonzero_elimination_call_lines": nonzero_calls,
        "live_restart_rows": len(restarts), "guard": receipt["guard"],
        "exit_code": receipt["exit_code"], "stderr_bytes": len(errors.encode()),
        "stdout_sha256": digest(stdout_path),
    }


def main() -> None:
    config = json.loads((HERE / "CONFIG.json").read_text())
    sources = {}
    for name, item in config["formulas"].items():
        archive = ROOT / item["archive"]
        formula_receipt = ROOT / item["formula_receipt"]
        require(digest(archive) == item["archive_sha256"], f"archive: {name}")
        require(digest(archive, compressed=True) == item["raw_sha256"], f"raw: {name}")
        bound = json.loads(formula_receipt.read_text())
        require(bound["formula_sha256"] == item["raw_sha256"], f"receipt: {name}")
        sources[name] = {"archive_sha256": item["archive_sha256"],
                         "raw_sha256": item["raw_sha256"]}
    cells = [audit_cell(config, run_id, name, variant)
             for run_id in ("R1", "R2") for name, variant in config["run_order"]]
    report = {"schema": "ecc2k130-equalb-gauss-gate-audit-v1",
              "config_sha256": digest(HERE / "CONFIG.json"),
              "sources": sources, "cells": cells, "status": "PASS"}
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
