#!/usr/bin/env python3
"""Independently bind and classify the two-versus-five matrix transcripts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = HERE.parent / "ecc2k130-equalb-gauss-gate-20261010"


def digest(path: Path, compressed: bool = False) -> str:
    h = hashlib.sha256()
    opener = gzip.open if compressed else Path.open
    with opener(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise AssertionError(reason)


def classify(output: str, receipt: dict) -> str:
    if receipt["producer_error"]:
        return "PRODUCER_FAILURE"
    if receipt["guard"] == "RSS_CAP":
        return "OOM_GUARD"
    if receipt["guard"] == "WALL_CAP":
        return "BOUNDED_UNKNOWN"
    if "s SATISFIABLE" in output:
        return "SAT_UNVERIFIED"
    if "s UNSATISFIABLE" in output:
        return "UNSAT_UNVERIFIED"
    if "s INDETERMINATE" in output or "s UNKNOWN" in output:
        return "BOUNDED_UNKNOWN"
    return "PRODUCER_FAILURE"


def audit_cell(config: dict, directory: Path, name: str,
               variant: str) -> dict:
    stem = f"{name}_{variant}"
    receipt = json.loads((directory / f"{stem}.json").read_text())
    stdout_path = directory / f"{stem}.stdout.txt"
    stderr_path = directory / f"{stem}.stderr.txt"
    output = stdout_path.read_text(errors="replace")
    require(digest(stdout_path) == receipt["stdout_sha256"], f"stdout: {stem}")
    require(digest(stderr_path) == receipt["stderr_sha256"], f"stderr: {stem}")
    require(receipt["config_sha256"] == digest(HERE / "CONFIG.json"),
            f"config: {stem}")
    require(receipt["runner_sha256"] == config["parent_runner_sha256"],
            f"parent runner: {stem}")
    require(receipt["dispatch_sha256"] == digest(HERE / "run_count.py"),
            f"dispatch: {stem}")
    require(receipt["command"][1:-1] ==
            config["base_flags"] + config["variants"][variant],
            f"flags: {stem}")
    require(receipt["source"]["raw_sha256"] ==
            config["formulas"][name]["raw_sha256"], f"formula: {stem}")
    require(receipt["solver"]["solver_sha256"] == config["solver_sha256"],
            f"binary: {stem}")
    require(receipt["status"] == classify(output, receipt), f"status: {stem}")
    require(receipt["candidate_id"] is None and
            receipt["verified_relation"] is False and
            receipt["novel_rank"] is None, f"premature claim: {stem}")
    require(receipt["rss_cap_bytes"] == config["rss_cap_bytes"] and
            receipt["solver_maxtime_seconds"] == config["solver_maxtime_seconds"] and
            receipt["external_wall_cap_seconds"] ==
            config["external_wall_cap_seconds"], f"resource envelope: {stem}")
    restarts = [line for line in output.splitlines()
                if line.lstrip().startswith("c rst")]
    recovered = [int(value) for value in
                 re.findall(r"Using (\d+) matrices recovered", output)]
    require(receipt["matrix_recovery_counts"] == recovered, f"matrix count: {stem}")
    require(receipt["live_restart_rows"] == len(restarts), f"restarts: {stem}")
    require(receipt["last_live_restart_row"] ==
            (restarts[-1] if restarts else None), f"last restart: {stem}")
    require(all(value <= (2 if variant == "two" else 5)
                for value in recovered), f"matrix limit: {stem}")
    good = [(int(rows), int(cols)) for rows, cols in re.findall(
        r"Good\s+matrix\s+\d+.*?(\d{3,5}) x\s*(\d{3,5})", output, re.S)]
    calls = re.findall(r"elim called\s*:\s*(\d+[KM]?)", output)
    active = any(value not in ("0", "0K", "0M") for value in calls)
    if receipt["status"] != "PRODUCER_FAILURE":
        require(bool(restarts) and bool(recovered), f"search not entered: {stem}")
    return {
        "formula": name, "variant": variant, "status": receipt["status"],
        "wall_seconds": receipt["wall_seconds"],
        "peak_observed_rss_bytes": receipt["peak_observed_rss_bytes"],
        "matrix_recovery_counts": recovered,
        "largest_good_matrix": list(max(good)) if good else None,
        "active_elimination": active,
        "elimination_call_lines": calls,
        "live_restart_rows": len(restarts),
        "guard": receipt["guard"], "exit_code": receipt["exit_code"],
        "stdout_sha256": digest(stdout_path),
        "stderr_sha256": digest(stderr_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="R1")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if re.fullmatch(r"R[1-9][0-9]*", args.run_id) is None:
        parser.error("invalid run ID")
    config = json.loads((HERE / "CONFIG.json").read_text())
    require(digest(PARENT / "CONFIG.json") == config["parent_config_sha256"],
            "parent config")
    require(digest(PARENT / "run_gate.py") == config["parent_runner_sha256"],
            "parent runner")
    for name, item in config["formulas"].items():
        archive = ROOT / item["archive"]
        receipt = json.loads((ROOT / item["formula_receipt"]).read_text())
        require(digest(archive) == item["archive_sha256"], f"archive: {name}")
        require(digest(archive, compressed=True) == item["raw_sha256"],
                f"raw formula: {name}")
        require(receipt["formula_sha256"] == item["raw_sha256"] and
                receipt["ordinary_query_index"] == 0 and
                receipt["actual_usable_points_B"] ==
                config["actual_usable_points_B"], f"formula receipt: {name}")
    directory = HERE / "runs" / args.run_id
    cells = [audit_cell(config, directory, name, variant)
             for name, variant in config["run_order"]]
    summary = json.loads((directory / "summary.json").read_text())
    require(summary["config_sha256"] == digest(HERE / "CONFIG.json") and
            summary["dispatch_sha256"] == digest(HERE / "run_count.py") and
            summary["parent_runner_sha256"] == config["parent_runner_sha256"],
            "summary source identity")
    require([(row["formula"], row["variant"], row["status"])
             for row in summary["results"]] ==
            [(row["formula"], row["variant"], row["status"])
             for row in cells], "summary cells")
    ratios = {}
    for name in config["formulas"]:
        by_variant = {row["variant"]: row for row in cells
                      if row["formula"] == name}
        a, b = by_variant["two"], by_variant["five"]
        if (a["status"] != "PRODUCER_FAILURE" and
                b["status"] != "PRODUCER_FAILURE" and
                b["peak_observed_rss_bytes"] > 0):
            ratios[name] = a["peak_observed_rss_bytes"] / b["peak_observed_rss_bytes"]
        else:
            ratios[name] = None
    report = {
        "schema": "ecc2k130-equalb-gauss-count-audit-v1",
        "status": "PASS_EVIDENCE_BINDING",
        "config_sha256": digest(HERE / "CONFIG.json"),
        "cells": cells, "paired_rss_two_over_five": ratios,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        if args.out.exists():
            raise FileExistsError(args.out)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
