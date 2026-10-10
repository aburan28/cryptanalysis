#!/usr/bin/env python3
"""Replay exact leaf-split inputs, complete SAT models, and group sums."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import re
import tempfile

import split


ref = split.ref


def read_units(raw):
    values = []
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 2 or fields[1] != b"0":
            raise ValueError("malformed unit clause")
        literal = int(fields[0])
        if literal == 0:
            raise ValueError("zero fixed literal")
        values.append(literal)
    if (values != sorted(values)
            or len({abs(lit) for lit in values}) != len(values)):
        raise ValueError("fixed literals are not sorted and unique")
    return values


def released_named_bits(mode, inputs):
    name, leaf = mode[0], int(mode[1:])
    return {inputs[f"{name}{leaf}:{bit}"] for bit in range(ref.DEGREE)}


def progress(output):
    rows = [line for line in output.splitlines() if line.startswith("c rst ")]
    conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", output,
                           re.MULTILINE)
    return {"restart_rows": len(rows),
            "last_restart_row": rows[-1] if rows else None,
            "final_conflicts": int(conflicts[-1]) if conflicts else None}


def audit_cell(policy, mode, cfg, parent_cfg, block_cfg, sat_cfg, scratch):
    witness, build, base, inputs, base_row, positive = split.parent_inputs(
        policy, cfg, parent_cfg, block_cfg, sat_cfg)
    cells_path = split.RUN / f"{policy}_cells.json"
    cells = ref.read(cells_path)
    if (cells["schema"] != "ecc2k130-263-leaf-inverse-frontier-cells-v1"
            or cells["status"] != "PASS_EXACT_SINGLE_COORDINATE_INPUTS"
            or cells["policy"] != policy
            or cells["config_sha256"] != ref.sha(split.HERE / "CONFIG.json")
            or cells["producer_sha256"] != ref.sha(split.HERE / "split.py")
            or cells["parent_base_sha256"] != base_row["raw_sha256"]
            or cells["parent_base_gzip_sha256"] != base_row["gzip_sha256"]
            or cells["parent_positive_units_sha256"] != ref.sha(
                split.prior.SAT / "runs/R1" /
                f"{policy}_positive.units.txt")
            or cells["parent_frontier_audit_sha256"] != ref.sha(
                split.PARENT / "runs/R1/audit.json")):
        raise ValueError("cell source or parent archive differs")
    row = cells["cells"][mode]
    prefix = split.RUN / f"{policy}_{mode}"
    delta_path = prefix.with_suffix(".units.txt")
    raw_units = delta_path.read_bytes()
    units = read_units(raw_units)
    released = released_named_bits(mode, inputs)
    all_units = set(positive)
    if (len(released) != cfg["released_coordinate_bits"]
            or set(units) != {lit for lit in all_units
                              if abs(lit) not in released}
            or released != {abs(lit) for lit in all_units} -
                {abs(lit) for lit in units}
            or row["released_input_count"] != len(released)
            or row["unit_count"] != cfg["single_coordinate_fixed_units"]
            or row["unit_delta_sha256"] != split.sha_bytes(raw_units)
            or row["target_choice"] != 0):
        raise ValueError("unit delta does not release exactly one coordinate")
    with tempfile.TemporaryDirectory(prefix="leaf-split-audit-",
                                     dir=scratch) as temporary:
        formula = Path(temporary) / "reconstructed.xcnf"
        vars_, total, count = split.prior.parent.parent_audit.compose_cell(
            base, raw_units, formula)
        if (ref.sha(formula) != row["formula_sha256"]
                or formula.stat().st_size != row["formula_bytes"]
                or vars_ != row["variables"]
                or total != row["total_constraints"]
                or count != row["unit_count"]):
            raise ValueError("reconstructed full XCNF differs")
        solver_path = prefix.with_suffix(".solver.json")
        solver = ref.read(solver_path)
        archive = prefix.with_suffix(".stdout.txt.gz")
        stderr = prefix.with_suffix(".stderr.txt")
        with gzip.open(archive, "rb") as stream:
            raw_output = stream.read()
        output = raw_output.decode("utf-8", errors="replace")
        terminal = [line.strip() for line in output.splitlines()
                    if line.startswith("s ")]
        if (solver["schema"]
                != "ecc2k130-263-leaf-inverse-frontier-solver-v1"
                or solver["policy"] != policy or solver["mode"] != mode
                or solver["formula_sha256"] != row["formula_sha256"]
                or solver["cell_receipt_sha256"] != ref.sha(cells_path)
                or solver["config_sha256"] != ref.sha(
                    split.HERE / "CONFIG.json")
                or solver["runner_sha256"] != ref.sha(split.HERE / "split.py")
                or solver["solver_sha256"] != cfg["solver_sha256"]
                or solver["stdout_raw_sha256"]
                != split.sha_bytes(raw_output)
                or solver["stdout_raw_bytes"] != len(raw_output)
                or solver["stdout_archive_sha256"] != ref.sha(archive)
                or solver["stdout_archive_bytes"] != archive.stat().st_size
                or solver["stderr_sha256"] != ref.sha(stderr)
                or solver["terminal_status_lines"] != terminal
                or solver["command_flags"] != [
                    "--threads=1", "--maxtime=120", "--verb=1",
                    "--printsol=1"]
                or solver["threads"] != cfg["threads"]
                or solver["internal_wall_seconds"]
                != cfg["internal_wall_seconds"]
                or solver["external_wall_seconds"]
                != cfg["external_wall_seconds"]
                or solver["peak_rss_cap_bytes"]
                != cfg["peak_rss_cap_bytes"]
                or solver["wall_seconds"] > cfg["external_wall_seconds"] + 3
                or solver["peak_sampled_rss_bytes"]
                > cfg["peak_rss_cap_bytes"]
                or solver["peak_child_rss_bytes"] <= 0):
            raise ValueError("solver receipt or lossless transcript differs")
        status = solver["status"]
        trace = progress(output)
        if status == "SAT_UNVERIFIED":
            if terminal != ["s SATISFIABLE"] or solver["exit_code"] != 10:
                raise ValueError("SAT result lacks terminal certificate")
            assignment = split.prior.parent.model.parse_assignment(
                output, vars_)
            checks = split.prior.parent.model.verify_xcnf(
                formula, assignment)
            group = split.prior.parent.model.replay_signs(
                policy, inputs, build["target_selector_variables"],
                witness, assignment)
            status = "SAT_VERIFIED_GROUP"
        else:
            checks = group = None
            if status == "BOUNDED_UNKNOWN":
                if not (solver["guard"] == "WALL_CAP"
                        or (terminal == ["s INDETERMINATE"]
                            and solver["exit_code"] == 15)):
                    raise ValueError("bounded result lacks its recorded cap")
                if not trace["restart_rows"]:
                    raise ValueError("bounded search has no live progress")
            elif status == "OOM_GUARD":
                if solver["guard"] != "RSS_CAP":
                    raise ValueError("OOM status lacks RSS guard")
            elif status == "UNSAT":
                raise ValueError("relaxed positive witness returned UNSAT")
            elif status != "PRODUCER_FAILURE":
                raise ValueError("unknown solver status")
        return {
            "status": status,
            "raw_status": solver["status"],
            "exit_code": solver["exit_code"],
            "guard": solver["guard"],
            "wall_seconds": solver["wall_seconds"],
            "peak_sampled_rss_bytes": solver["peak_sampled_rss_bytes"],
            "formula_sha256": row["formula_sha256"],
            "solver_receipt_sha256": ref.sha(solver_path),
            "stdout_archive_sha256": ref.sha(archive),
            "progress": trace,
            "xcnf_checks": checks,
            "group_replay": group,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-dir", type=Path, default=Path("/private/tmp"))
    parser.add_argument("--out", type=Path, default=split.RUN / "audit.json")
    args = parser.parse_args()
    if not args.scratch_dir.is_dir():
        parser.error("scratch directory does not exist")
    cfg, parent_cfg, block_cfg, sat_cfg = split.config()
    cells = {}
    for entry in cfg["ordered_cells"]:
        policy, mode = entry.split("/")
        cells[entry] = audit_cell(policy, mode, cfg, parent_cfg, block_cfg,
                                  sat_cfg, args.scratch_dir)
    result = {
        "schema": "ecc2k130-263-leaf-inverse-frontier-audit-v1",
        "status": "PASS_EXACT_INPUTS_AND_TRANSCRIPTS",
        "candidate_id": None,
        "config_sha256": ref.sha(split.HERE / "CONFIG.json"),
        "protocol_sha256": ref.sha(split.HERE / "PROTOCOL.md"),
        "producer_sha256": ref.sha(split.HERE / "split.py"),
        "auditor_sha256": ref.sha(Path(__file__)),
        "parent_audit_sha256": ref.sha(
            split.PARENT / "runs/R1/audit.json"),
        "cells": cells,
    }
    split.write_json(args.out, result)
    print(json.dumps({"status": result["status"],
                      "cells": {key: row["status"] for key, row in cells.items()}},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
