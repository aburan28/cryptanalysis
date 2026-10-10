#!/usr/bin/env python3
"""Run the frozen two-versus-five Gaussian matrix gate on exact XCNFs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import tempfile


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-equalb-gauss-gate-20261010"
sys.path.insert(0, str(PARENT))
import run_gate as parent  # noqa: E402


CONFIG = HERE / "CONFIG.json"


def load_config() -> dict:
    config = json.loads(CONFIG.read_text())
    if config["schema"] != "ecc2k130-equalb-gauss-count-config-v1":
        raise ValueError("unknown config schema")
    if parent.sha(PARENT / "CONFIG.json") != config["parent_config_sha256"]:
        raise ValueError("parent configuration changed")
    if parent.sha(PARENT / "run_gate.py") != config["parent_runner_sha256"]:
        raise ValueError("parent guarded runner changed")
    if config["base_flags"] != [
        "--threads=1", "--maxtime=60", "--verb=1", "--printsol=1",
        "--maxmatrixrows=9000", "--maxmatrixcols=14000",
        "--autodisablegauss=0",
    ]:
        raise ValueError("solver base flags changed")
    if config["variants"] != {
        "five": ["--maxnummatrices=5"],
        "two": ["--maxnummatrices=2"],
    }:
        raise ValueError("matrix-count policies changed")
    if config["run_order"] != [
        ["normal4_counter", "five"], ["normal4_counter", "two"],
        ["w24_balanced", "two"], ["w24_balanced", "five"],
    ]:
        raise ValueError("paired run order changed")
    ancestor = json.loads((PARENT / "CONFIG.json").read_text())
    for key in (
        "curve_id", "actual_usable_points_B", "ordinary_query_index",
        "summands", "target_lifts", "input_prefix_sha256", "solver_sha256",
        "solver_version", "threads", "solver_maxtime_seconds",
        "external_wall_cap_seconds", "rss_cap_bytes", "formulas",
    ):
        if config[key] != ancestor[key]:
            raise ValueError(f"parent input or resource changed: {key}")
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--run", action="store_true")
    parser.add_argument("--run-id", default="R1")
    args = parser.parse_args()
    if re.fullmatch(r"R[1-9][0-9]*", args.run_id) is None:
        parser.error("run ID must be R followed by a positive decimal integer")
    config = load_config()
    outdir = HERE / "runs" / args.run_id
    if args.run and outdir.exists():
        raise FileExistsError(f"refusing to overwrite {args.run_id}")

    with tempfile.TemporaryDirectory(prefix="ecc2k130-gauss-count-") as tmp:
        sources, solver = parent.source_check(config, Path(tmp))
        if args.check:
            print(json.dumps({
                "status": "SOURCE_CHECK_PASS", "config_sha256": parent.sha(CONFIG),
                "source_hashes": {name: row["raw_sha256"]
                                  for name, row in sources.items()},
                "solver_sha256": solver["solver_sha256"],
            }, sort_keys=True))
            return
        outdir.mkdir(parents=True)
        # The parent's tested process guard writes the executable runner hash.
        # Bind it to this experiment's configuration while preserving the
        # parent's exact RSS, wall, and exit-status handling.
        parent.CONFIG = CONFIG
        results = []
        for name, variant in config["run_order"]:
            receipt = parent.run_cell(config, sources[name], solver, name,
                                      variant, outdir)
            receipt["dispatch_sha256"] = parent.sha(Path(__file__))
            receipt["parent_runner_sha256"] = config["parent_runner_sha256"]
            receipt_path = outdir / f"{name}_{variant}.json"
            receipt_path.write_text(json.dumps(receipt, sort_keys=True,
                                               indent=2) + "\n")
            results.append({
                "formula": name, "variant": variant,
                "status": receipt["status"],
                "wall_seconds": receipt["wall_seconds"],
                "peak_observed_rss_bytes": receipt["peak_observed_rss_bytes"],
                "matrix_recovery_counts": receipt["matrix_recovery_counts"],
                "live_restart_rows": receipt["live_restart_rows"],
            })
            print(json.dumps(results[-1], sort_keys=True), flush=True)
        (outdir / "summary.json").write_text(json.dumps({
            "schema": "ecc2k130-equalb-gauss-count-summary-v1",
            "config_sha256": parent.sha(CONFIG),
            "dispatch_sha256": parent.sha(Path(__file__)),
            "parent_runner_sha256": config["parent_runner_sha256"],
            "results": results,
        }, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
