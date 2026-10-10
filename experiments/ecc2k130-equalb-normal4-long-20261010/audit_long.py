#!/usr/bin/env python3
"""Independently audit the frozen normal4 conflict-gate transcripts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COUNT = HERE.parent / "ecc2k130-equalb-gauss-count-20261010"
SOURCE = HERE.parent / "ecc2k130-equalb-gauss-gate-20261010"


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


def transcript(output: str) -> dict:
    restarts = [line for line in output.splitlines()
                if line.lstrip().startswith("c rst ")]
    matrix_counts = [int(value) for value in
                     re.findall(r"Using (\d+) matrices recovered", output)]
    good = []
    for line in output.splitlines():
        match = re.search(r"Good\s+matrix\s+\d+\s+(\d+)\s+x\s*(\d+)", line)
        if match:
            good.append((int(match.group(1)), int(match.group(2))))
    elimination_calls = re.findall(r"elim called\s*:\s*(\d+[KM]?)", output)
    return {
        "matrix_recovery_counts": matrix_counts,
        "largest_good_matrix": list(max(good)) if good else None,
        "elimination_call_lines": elimination_calls,
        "active_elimination":
            (any(value.rstrip("KM").strip("0") != ""
                 for value in elimination_calls) if elimination_calls else None),
        "live_restart_rows": len(restarts),
        "last_live_restart_row": restarts[-1] if restarts else None,
        "last_restart_conflict_label":
            restarts[-1].split()[6] if restarts else None,
    }


def status(output: str, receipt: dict) -> str:
    if receipt["producer_error"]:
        return "PRODUCER_FAILURE"
    if "s SATISFIABLE" in output:
        return "SAT_UNVERIFIED"
    if "s UNSATISFIABLE" in output:
        return "UNSAT_UNVERIFIED"
    if receipt["guard"] == "RSS_CAP":
        return "OOM_GUARD"
    if (receipt["guard"] == "WALL_CAP" or "s INDETERMINATE" in output
            or "s UNKNOWN" in output):
        return "BOUNDED_UNKNOWN"
    return "PRODUCER_FAILURE"


def audit_cell(config: dict, directory: Path, name: str, variant: str) -> dict:
    stem = f"{name}_{variant}"
    receipt = json.loads((directory / f"{stem}.json").read_text())
    stdout = directory / f"{stem}.stdout.txt"
    stderr = directory / f"{stem}.stderr.txt"
    output = stdout.read_text(errors="replace")
    require(digest(stdout) == receipt["stdout_sha256"], f"stdout: {stem}")
    require(digest(stderr) == receipt["stderr_sha256"], f"stderr: {stem}")
    require(receipt["config_sha256"] == digest(HERE / "CONFIG.json"),
            f"config: {stem}")
    require(receipt["runner_sha256"] == digest(HERE / "run_long.py"),
            f"runner: {stem}")
    require(receipt["source_runner_sha256"] == config["source_runner_sha256"],
            f"source runner: {stem}")
    require(receipt["source"]["raw_sha256"] ==
            config["formulas"][name]["raw_sha256"], f"raw formula: {stem}")
    require(receipt["source"]["formula_receipt_sha256"] ==
            config["formulas"][name]["formula_receipt_sha256"],
            f"formula receipt: {stem}")
    require(receipt["solver"]["solver_sha256"] == config["solver_sha256"],
            f"solver: {stem}")
    require(receipt["command"][1:-1] ==
            config["base_flags"] + config["variants"][variant],
            f"flags: {stem}")
    require(receipt["formula"] == name and receipt["variant"] == variant,
            f"identity: {stem}")
    require(receipt["candidate_id"] is None and
            receipt["verified_relation"] is False and
            receipt["novel_rank"] is None, f"premature relation: {stem}")
    for key in ("solver_maxtime_seconds", "solver_max_conflicts",
                "external_wall_cap_seconds", "sigint_grace_seconds",
                "rss_cap_bytes"):
        require(receipt[key] == config[key], f"resource {key}: {stem}")
    raw = transcript(output)
    for key, value in raw.items():
        require(receipt[key] == value, f"transcript {key}: {stem}")
    require(receipt["status"] == status(output, receipt), f"status: {stem}")
    require(receipt["rss_sample_count"] > 0, f"RSS unobserved: {stem}")
    if receipt["status"] != "PRODUCER_FAILURE":
        require(raw["matrix_recovery_counts"] and raw["live_restart_rows"] > 0,
                f"search not entered: {stem}")
        require(all(count <= (2 if variant == "two" else 5)
                    for count in raw["matrix_recovery_counts"]),
                f"matrix limit: {stem}")
    if receipt["guard"] == "WALL_CAP":
        require(receipt["signal_sent"] in ("SIGINT", "SIGINT_THEN_SIGKILL")
                and receipt["signal_at_seconds"] >=
                config["external_wall_cap_seconds"], f"wall guard: {stem}")
    if receipt["guard"] == "RSS_CAP":
        require(receipt["forced_kill"] and
                receipt["peak_observed_rss_bytes"] > config["rss_cap_bytes"],
                f"RSS guard: {stem}")
    if receipt["guard"] is None:
        require(receipt["signal_sent"] is None and not receipt["forced_kill"],
                f"unexpected signal: {stem}")
    return {
        "formula": name, "variant": variant, "status": receipt["status"],
        "wall_seconds": receipt["wall_seconds"],
        "peak_observed_rss_bytes": receipt["peak_observed_rss_bytes"],
        "rss_sample_count": receipt["rss_sample_count"],
        "guard": receipt["guard"], "exit_code": receipt["exit_code"],
        "signal_sent": receipt["signal_sent"],
        "forced_kill": receipt["forced_kill"],
        "stdout_sha256": digest(stdout), "stderr_sha256": digest(stderr),
        **raw,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="R1")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    config = json.loads((HERE / "CONFIG.json").read_text())
    require(config["schema"] == "ecc2k130-equalb-normal4-conflict-gate-v1",
            "config schema")
    require(args.run_id in config["run_ids"], "run ID")
    require(digest(COUNT / "CONFIG.json") == config["parent_config_sha256"],
            "parent config")
    require(digest(COUNT / "run_count.py") ==
            config["parent_dispatch_sha256"], "parent dispatcher")
    require(digest(SOURCE / "run_gate.py") ==
            config["source_runner_sha256"], "source runner")
    for name, item in config["formulas"].items():
        archive = ROOT / item["archive"]
        receipt_path = ROOT / item["formula_receipt"]
        require(digest(archive) == item["archive_sha256"], f"archive: {name}")
        require(digest(archive, compressed=True) == item["raw_sha256"],
                f"raw formula: {name}")
        require(digest(receipt_path) == item["formula_receipt_sha256"],
                f"formula receipt: {name}")
        receipt = json.loads(receipt_path.read_text())
        require(receipt["formula_sha256"] == item["raw_sha256"] and
                receipt["ordinary_query_index"] == 0 and
                receipt["actual_usable_points_B"] ==
                config["actual_usable_points_B"] and
                receipt["source_curve_id"] == config["curve_id"],
                f"formula provenance: {name}")
    directory = HERE / "runs" / args.run_id
    preflight = json.loads((directory / "preflight.json").read_text())
    require(preflight["status"] == "SOURCE_CHECK_PASS" and
            preflight["config_sha256"] == digest(HERE / "CONFIG.json") and
            preflight["runner_sha256"] == digest(HERE / "run_long.py"),
            "preflight")
    cells = [audit_cell(config, directory, name, variant)
             for name, variant in config["run_order"]]
    summary = json.loads((directory / "summary.json").read_text())
    require(summary["config_sha256"] == digest(HERE / "CONFIG.json") and
            summary["runner_sha256"] == digest(HERE / "run_long.py") and
            [(row["formula"], row["variant"], row["status"])
             for row in summary["cells"]] ==
            [(row["formula"], row["variant"], row["status"])
             for row in cells], "summary")
    by_variant = {cell["variant"]: cell for cell in cells}
    a, b = by_variant["two"], by_variant["five"]
    ratio = (a["peak_observed_rss_bytes"] /
             b["peak_observed_rss_bytes"]
             if b["peak_observed_rss_bytes"] > 0 else None)
    report = {
        "schema": "ecc2k130-equalb-normal4-conflict-audit-v1",
        "status": "PASS_EVIDENCE_BINDING",
        "config_sha256": digest(HERE / "CONFIG.json"),
        "cells": cells, "paired_rss_two_over_five": ratio,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        if args.out.exists():
            raise FileExistsError(args.out)
        args.out.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
