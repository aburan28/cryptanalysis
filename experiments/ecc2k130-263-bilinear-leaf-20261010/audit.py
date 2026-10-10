#!/usr/bin/env python3
"""Archive-only replay of bilinear leaf XCNFs and solver transcripts."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

import experiment


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(experiment.bilinear.PARENT))
import audit as parent_audit  # noqa: E402
from verify_model import parse_assignment, replay_signs, verify_xcnf  # noqa: E402


ref = experiment.ref


def progress(output):
    restarts = [line for line in output.splitlines()
                if line.startswith("c rst ")]
    conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", output,
                           re.MULTILINE)
    return {"restart_rows": len(restarts),
            "last_restart_row": restarts[-1] if restarts else None,
            "final_conflicts": int(conflicts[-1]) if conflicts else None}


def audit_panel(policy, variant, cfg, parent_cfg, witness, scratch):
    control = witness["policies"][policy]
    archive, map_path, base_path = experiment.base_paths(policy, variant)
    base = ref.read(base_path)
    inputs = ref.read(map_path)
    target = control["target_x"]
    if (base["schema"] != "ecc2k130-263-bilinear-base-v1"
            or base["status"] != "CONTROL_FORMULA_BUILT"
            or base["policy"] != policy or base["variant"] != variant
            or base["target_x_choices"]
            != [str(target)] + [str(target ^ 1)] * 3
            or base["formula_gzip_sha256"] != ref.sha(archive)
            or base["formula_gzip_bytes"] != archive.stat().st_size
            or base["input_vars_sha256"] != ref.sha(map_path)
            or base["input_vars_count"] != len(inputs)
            or base["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or base["equivalence_sha256"]
            != ref.sha(experiment.RUN / "equivalence.json")
            or base["builder_sha256"] != ref.sha(HERE / "bilinear.py")
            or base["producer_sha256"] != ref.sha(HERE / "experiment.py")):
        raise ValueError("base receipt or source differs")
    cells_path = experiment.RUN / f"{policy}_{variant}_cells.json"
    cells = ref.read(cells_path)
    if (cells["schema"] != "ecc2k130-263-bilinear-cells-v1"
            or cells["status"] != "PASS_SIX_EXACT_INPUTS"
            or cells["policy"] != policy or cells["variant"] != variant
            or cells["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or cells["producer_sha256"] != ref.sha(HERE / "experiment.py")
            or cells["base_receipt_sha256"] != ref.sha(base_path)
            or cells["base_gzip_sha256"] != ref.sha(archive)
            or cells["input_vars_sha256"] != ref.sha(map_path)
            or set(cells["cells"]) != set(cfg["modes"])):
        raise ValueError("cell receipt differs")
    rows = {}
    with tempfile.TemporaryDirectory(prefix="bilinear-audit-",
                                     dir=scratch) as temporary:
        raw_base = Path(temporary) / "base.xcnf"
        with gzip.open(archive, "rb") as source, raw_base.open("xb") as target:
            shutil.copyfileobj(source, target, length=1 << 20)
        if (ref.sha(raw_base) != base["formula_raw_sha256"]
                or raw_base.stat().st_size != base["formula_raw_bytes"]):
            raise ValueError("lossless base XCNF archive differs")
        for mode in cfg["modes"]:
            row = cells["cells"][mode]
            prefix = experiment.RUN / f"{policy}_{variant}_{mode}"
            delta = prefix.with_suffix(".units.txt").read_bytes()
            expected = parent_audit.expected_unit_bytes(
                mode, control, inputs,
                base["target_selector_variables"], parent_cfg)
            if (delta != expected
                    or row["unit_delta_sha256"] != experiment.digest(delta)
                    or row["target_choice"] != int(mode == "negative")
                    or row["released_coordinate_bits"] != (
                        cfg["released_coordinate_bits"]
                        if mode in ("x0", "z0", "x5", "z5") else 0)):
                raise ValueError("semantic unit delta differs")
            full = Path(temporary) / f"{mode}.xcnf"
            variables, constraints, count = parent_audit.reconstruct(
                raw_base, delta, full)
            if (ref.sha(full) != row["formula_sha256"]
                    or full.stat().st_size != row["formula_bytes"]
                    or variables != row["variables"]
                    or constraints != row["total_constraints"]
                    or count != row["unit_count"]):
                raise ValueError("complete XCNF differs from precommitted input")
            solver_path = prefix.with_suffix(".solver.json")
            solver = ref.read(solver_path)
            stdout_archive = prefix.with_suffix(".stdout.txt.gz")
            stderr = prefix.with_suffix(".stderr.txt")
            with gzip.open(stdout_archive, "rb") as stream:
                raw_output = stream.read()
            output = raw_output.decode("utf-8", errors="replace")
            terminal = [line.strip() for line in output.splitlines()
                        if line.startswith("s ")]
            fixed = mode in ("positive", "negative")
            internal = (cfg["fixed_internal_wall_seconds"] if fixed
                        else cfg["released_internal_wall_seconds"])
            external = (cfg["fixed_external_wall_seconds"] if fixed
                        else cfg["released_external_wall_seconds"])
            if (solver["schema"] != "ecc2k130-263-bilinear-solver-v1"
                    or solver["policy"] != policy
                    or solver["variant"] != variant
                    or solver["mode"] != mode
                    or solver["formula_sha256"] != row["formula_sha256"]
                    or solver["cell_receipt_sha256"] != ref.sha(cells_path)
                    or solver["config_sha256"]
                    != ref.sha(HERE / "CONFIG.json")
                    or solver["runner_sha256"]
                    != ref.sha(HERE / "experiment.py")
                    or solver["solver_sha256"] != cfg["solver_sha256"]
                    or solver["stdout_raw_sha256"]
                    != experiment.digest(raw_output)
                    or solver["stdout_raw_bytes"] != len(raw_output)
                    or solver["stdout_archive_sha256"]
                    != ref.sha(stdout_archive)
                    or solver["stdout_archive_bytes"]
                    != stdout_archive.stat().st_size
                    or solver["stderr_sha256"] != ref.sha(stderr)
                    or solver["terminal_status_lines"] != terminal
                    or solver["command_flags"] != ["--threads=1",
                        f"--maxtime={internal}", "--verb=1", "--printsol=1"]
                    or solver["threads"] != cfg["threads"]
                    or solver["internal_wall_seconds"] != internal
                    or solver["external_wall_seconds"] != external
                    or solver["peak_rss_cap_bytes"]
                    != cfg["peak_rss_cap_bytes"]
                    or solver["wall_seconds"] > external + 3
                    or solver["peak_sampled_rss_bytes"]
                    > cfg["peak_rss_cap_bytes"]
                    or solver["peak_child_rss_bytes"] <= 0):
                raise ValueError("solver receipt or raw transcript differs")
            state = solver["status"]
            trace = progress(output)
            if state == "SAT_UNVERIFIED":
                if terminal != ["s SATISFIABLE"] or solver["exit_code"] != 10:
                    raise ValueError("SAT transcript is incomplete")
                assignment = parse_assignment(output, variables)
                checks = verify_xcnf(full, assignment)
                replay = replay_signs(
                    policy, inputs, base["target_selector_variables"],
                    control, assignment)
                state = "SAT_VERIFIED_GROUP"
            else:
                checks = replay = None
                if state == "UNSAT":
                    if (terminal != ["s UNSATISFIABLE"]
                            or solver["exit_code"] != 20):
                        raise ValueError("UNSAT lacks terminal result")
                elif state == "BOUNDED_UNKNOWN":
                    if not (solver["guard"] == "WALL_CAP"
                            or (terminal == ["s INDETERMINATE"]
                                and solver["exit_code"] == 15)):
                        raise ValueError("bounded result lacks recorded cap")
                    if trace["restart_rows"] == 0:
                        raise ValueError("bounded result lacks search progress")
                elif state == "OOM_GUARD":
                    if solver["guard"] != "RSS_CAP":
                        raise ValueError("RSS status lacks guard")
                elif state != "PRODUCER_FAILURE":
                    raise ValueError("unknown solver result")
            rows[mode] = {
                "status": state,
                "raw_status": solver["status"],
                "exit_code": solver["exit_code"],
                "guard": solver["guard"],
                "wall_seconds": solver["wall_seconds"],
                "peak_sampled_rss_bytes": solver["peak_sampled_rss_bytes"],
                "formula_sha256": row["formula_sha256"],
                "solver_receipt_sha256": ref.sha(solver_path),
                "stdout_archive_sha256": ref.sha(stdout_archive),
                "progress": trace,
                "xcnf_checks": checks,
                "group_replay": replay,
            }
    if rows["positive"]["status"] != "SAT_VERIFIED_GROUP":
        raise ValueError("positive control did not verify")
    if rows["negative"]["status"] != "UNSAT":
        raise ValueError("negative control did not prove UNSAT")
    return {"base_formula_sha256": base["formula_raw_sha256"],
            "base_stats": base["stats"],
            "ir_operations": base["ir_operations"],
            "cells": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-dir", type=Path, default=Path("/private/tmp"))
    args = parser.parse_args()
    if not args.scratch_dir.is_dir():
        parser.error("scratch directory does not exist")
    cfg, parent_cfg, witness = experiment.checked_config()
    parent_audit.checked_witness(parent_cfg)
    panels = {}
    for variant in cfg["variants"]:
        panels[variant] = {}
        for policy in cfg["policies"]:
            panels[variant][policy] = audit_panel(
                policy, variant, cfg, parent_cfg, witness,
                args.scratch_dir)
    result = {
        "schema": "ecc2k130-263-bilinear-audit-v1",
        "status": "PASS_EXACT_INPUTS_AND_TRANSCRIPTS",
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "builder_sha256": ref.sha(HERE / "bilinear.py"),
        "producer_sha256": ref.sha(HERE / "experiment.py"),
        "auditor_sha256": ref.sha(Path(__file__)),
        "equivalence_sha256": ref.sha(experiment.RUN / "equivalence.json"),
        "parent_witness_sha256": cfg["parent_witness_sha256"],
        "panels": panels,
    }
    path = experiment.RUN / "audit.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({variant: {policy: {mode: row["status"]
                                     for mode, row in panel["cells"].items()}
                                for policy, panel in policies.items()}
                      for variant, policies in panels.items()}, sort_keys=True),
          flush=True)


if __name__ == "__main__":
    main()
