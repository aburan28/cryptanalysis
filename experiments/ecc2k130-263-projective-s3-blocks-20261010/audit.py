#!/usr/bin/env python3
"""Replay archived block-isolation inputs, solver models, and group sums."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import tempfile

import common


ref = common.ref


def unit_literals(raw):
    result = []
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 2 or fields[1] != b"0":
            raise ValueError("unit delta has a malformed DIMACS clause")
        literal = int(fields[0])
        if literal == 0:
            raise ValueError("unit delta has a zero literal")
        result.append(literal)
    if result != sorted(set(result)):
        raise ValueError("unit delta is not sorted and unique")
    return set(result)


def search_counts(output):
    result = {}
    for name in ("conflicts", "restarts"):
        values = re.findall(r"^c " + name + r"\s*:\s*(\d+)",
                            output, re.MULTILINE)
        result[name] = int(values[-1]) if values else None
    # An external SIGKILL has no final statistics. Keep the final printed
    # restart row as a rounded progress observation, never an exact count.
    restart_rows = [line for line in output.splitlines()
                    if line.startswith("c rst ")]
    if restart_rows:
        fields = restart_rows[-1].split()
        if (len(fields) < 7 or not fields[5].isdigit()
                or not re.fullmatch(r"\d+(?:\.\d+)?[KMG]?", fields[6])):
            raise ValueError("last restart progress row is malformed")
        result["last_restart_index"] = int(fields[5])
        result["last_printed_conflicts"] = fields[6]
    else:
        result["last_restart_index"] = None
        result["last_printed_conflicts"] = None
    result["search_started"] = bool(restart_rows)
    return result


def check_partition(policy, run_dir, config, inputs, build, witness):
    cells_path = run_dir / (policy + "_cells.json")
    cells = ref.read(cells_path)
    if (cells["schema"] != "ecc2k130-263-projective-s3-search-block-cells-v1"
            or cells["status"] != "PASS_EXACT_INPUT_PARTITION"
            or cells["policy"] != policy
            or cells["config_sha256"] != ref.sha(common.HERE / "CONFIG.json")
            or cells["common_source_sha256"] != ref.sha(
                common.HERE / "common.py")
            or cells["producer_sha256"] != ref.sha(common.HERE / "make_cells.py")
            or cells["parent_base_raw_sha256"] != build["formula_sha256"]
            or cells["parent_base_gzip_sha256"] != config["parent_sha256"][
                f"runs/R1/{policy}_control_base.xcnf.gz"]
            or cells["parent_base_receipt_sha256"] != ref.sha(
                common.PARENT / "runs/R1" /
                (policy + "_control_base.json"))
            or cells["parent_input_vars_sha256"] != ref.sha(
                common.PARENT / "runs/R1" /
                (policy + "_control_base.inputs.json"))):
        raise ValueError("cell manifest or parent binding changed")
    parent_dir = common.PARENT / "runs/R1"
    parent_cells = ref.read(parent_dir / (policy + "_cells.json"))
    for key, mode in (("parent_positive_unit_delta_sha256", "positive"),
                      ("parent_mask_only_unit_delta_sha256", "free")):
        path = parent_dir / (policy + "_" + mode + ".units.txt")
        if (cells[key] != ref.sha(path)
                or parent_cells["cells"][mode]["unit_delta_sha256"]
                != ref.sha(path)):
            raise ValueError("parent unit partition identity changed")
    positive = unit_literals((parent_dir / (policy + "_positive.units.txt")).read_bytes())
    mask_only = unit_literals((parent_dir / (policy + "_free.units.txt")).read_bytes())
    leaf_vars = {value for name, value in inputs.items()
                 if name.startswith(("x", "z")) and name[1].isdigit()}
    intermediate_vars = {value for name, value in inputs.items()
                         if (name.startswith("t") and name[1].isdigit())
                         or name.startswith("f:")}
    if (len(positive) != 2246 or len(mask_only) != 146
            or len(leaf_vars) != 6 * 2 * 131
            or len(intermediate_vars) != 4 * 132):
        raise ValueError("parent input block geometry changed")
    expected = {
        "intermediate_free": {lit for lit in positive
                              if abs(lit) in leaf_vars
                              or lit in mask_only},
        "leaf_free": {lit for lit in positive
                      if abs(lit) in intermediate_vars
                      or lit in mask_only},
    }
    observed = {}
    for mode in config["modes"]:
        path = run_dir / (policy + "_" + mode + ".units.txt")
        observed[mode] = unit_literals(path.read_bytes())
        if (observed[mode] != expected[mode]
                or ref.sha(path) != cells["cells"][mode]["unit_delta_sha256"]
                or cells["cells"][mode]["selected_target_choice"] != 0):
            raise ValueError("new unit delta does not fix its declared block")
    if (observed["intermediate_free"] | observed["leaf_free"] != positive
            or observed["intermediate_free"] & observed["leaf_free"]
            != mask_only):
        raise ValueError("new control partition differs from parent")
    return cells, cells_path


def archive_output(prefix, solver, archive_source_sha):
    receipt_path = prefix.with_suffix(".stdout.archive.json")
    compressed = prefix.with_suffix(".stdout.txt.gz")
    receipt = ref.read(receipt_path)
    if (receipt["schema"]
            != "ecc2k130-263-projective-s3-search-block-archive-v1"
            or receipt["status"] != "PASS_LOSSLESS_ARCHIVE"
            or receipt["kind"] != "solver_stdout"
            or receipt["raw_sha256"] != solver["stdout_sha256"]
            or receipt["gzip_sha256"] != ref.sha(compressed)
            or receipt["gzip_bytes"] != compressed.stat().st_size
            or receipt["source_sha256"] != archive_source_sha
            or receipt["solver_receipt_sha256"] != ref.sha(
                prefix.with_suffix(".solver.json"))):
        raise ValueError("solver stdout archive receipt differs")
    with gzip.open(compressed, "rb") as stream:
        raw = stream.read()
    if (hashlib.sha256(raw).hexdigest() != solver["stdout_sha256"]
            or len(raw) != solver["stdout_bytes"]
            or len(raw) != receipt["raw_bytes"]):
        raise ValueError("solver stdout decompression differs")
    return raw.decode("utf-8", errors="replace")


def check_cell(policy, mode, run_dir, scratch_dir, config, witness, build,
               base, inputs, cells, cells_path):
    prefix = run_dir / (policy + "_" + mode)
    row = cells["cells"][mode]
    delta = prefix.with_suffix(".units.txt")
    units = delta.read_bytes()
    with tempfile.TemporaryDirectory(prefix="s3-block-audit-",
                                     dir=scratch_dir) as scratch:
        formula = Path(scratch) / "reconstructed.xcnf"
        vars_, total, count = common.parent_audit.compose_cell(
            base, units, formula)
        if (ref.sha(formula) != row["xcnf_sha256"]
                or formula.stat().st_size != row["xcnf_bytes"]
                or vars_ != row["vars"]
                or total != row["total_constraints"]
                or count != row["unit_count"]
                or count != (1718 if mode == "intermediate_free" else 674)):
            raise ValueError("reconstructed solver input differs")
        solver = ref.read(prefix.with_suffix(".solver.json"))
        output = archive_output(prefix, solver,
                                ref.sha(common.HERE / "archive_evidence.py"))
        lines = [line.strip() for line in output.splitlines()
                 if line.startswith("s ")]
        if (solver["schema"]
            != "ecc2k130-263-projective-s3-search-block-solver-v1"
            or solver["policy"] != policy or solver["mode"] != mode
            or solver["formula_sha256"] != row["xcnf_sha256"]
            or solver["cell_receipt_sha256"] != ref.sha(cells_path)
            or solver["solver_sha256"] != config["solver_sha256"]
            or solver["runner_sha256"] != ref.sha(common.HERE / "run_cell.py")
            or solver["config_sha256"] != ref.sha(common.HERE / "CONFIG.json")
            or solver["common_source_sha256"] != ref.sha(
                common.HERE / "common.py")
            or solver["stderr_sha256"]
            != ref.sha(prefix.with_suffix(".stderr.txt"))
            or solver["terminal_status_lines"] != lines
            or solver["threads"] != 1
            or solver["solver_maxtime_seconds"] != 120
            or solver["external_wall_cap_seconds"] != 150
            or solver["rss_cap_bytes"] != 4 * (1 << 30)
            or solver["wall_seconds"] > 152
            or solver["peak_observed_rss_bytes"] > 4 * (1 << 30)
            or solver["peak_child_rss_bytes"] <= 0
            or solver["command"][1:5] != [
                "--threads=1", "--maxtime=120", "--verb=1", "--printsol=1"]):
            raise ValueError("solver receipt or raw transcript differs")
        status = solver["status"]
        if status == "SAT_UNVERIFIED":
            if lines != ["s SATISFIABLE"] or solver["exit_code"] != 10:
                raise ValueError("SAT terminal line or code differs")
            values = common.model.parse_assignment(output, vars_)
            constraints = common.model.verify_xcnf(formula, values)
            group_replay = common.model.replay_signs(
                policy, inputs, build["target_selector_variables"],
                witness, values)
            status = "SAT_VERIFIED_GROUP"
        else:
            constraints = group_replay = None
            if status == "BOUNDED_UNKNOWN":
                if (solver["guard"] != "WALL_CAP"
                        and (lines != ["s INDETERMINATE"]
                             or solver["exit_code"] != 15)):
                    raise ValueError("bounded status lacks recorded cap")
            elif status == "OOM_GUARD":
                if solver["guard"] != "RSS_CAP":
                    raise ValueError("OOM status lacks RSS guard")
            elif status == "UNSAT":
                raise ValueError("loosened parent SAT witness returned UNSAT")
            elif status != "PRODUCER_FAILURE":
                raise ValueError("unknown solver status")
        return {
            "status": status,
            "solver_status": solver["status"],
            "exit_code": solver["exit_code"],
            "guard": solver["guard"],
            "wall_seconds": solver["wall_seconds"],
            "peak_observed_rss_bytes": solver["peak_observed_rss_bytes"],
            "peak_child_rss_bytes": solver["peak_child_rss_bytes"],
            "search_counts": search_counts(output),
            "exact_input_sha256": row["xcnf_sha256"],
            "unit_count": count,
            "stdout_sha256": solver["stdout_sha256"],
            "all_constraints_checked": constraints,
            "exact_group_replay": group_replay,
        }


def parent_baseline(policy):
    parent_dir = common.PARENT / "runs/R1"
    prefix = parent_dir / (policy + "_free")
    solver = ref.read(prefix.with_suffix(".solver.json"))
    raw, _ = common.parent_audit.archive_bytes(
        prefix.with_suffix(".stdout.txt"), solver["stdout_sha256"],
        prefix.with_suffix(".stdout.archive.json"),
        ref.sha(common.PARENT / "archive_evidence.py"))
    return {
        "status": "BOUNDED_UNKNOWN",
        "wall_seconds": solver["wall_seconds"],
        "peak_child_rss_bytes": solver["peak_child_rss_bytes"],
        "search_counts": search_counts(raw.decode("utf-8", errors="replace")),
        "exact_input_sha256": solver["formula_sha256"],
    }


def diagnosis(cells):
    if any(row["status"] == "BOUNDED_UNKNOWN"
           and not row["search_counts"]["search_started"]
           for row in cells.values()):
        return "INCOMPLETE_SEARCH_ACTIVITY"
    left = cells["intermediate_free"]["status"]
    right = cells["leaf_free"]["status"]
    if (left, right) == ("SAT_VERIFIED_GROUP", "SAT_VERIFIED_GROUP"):
        return "JOINT_RELEASE_SEARCH_GAP"
    if (left, right) == ("SAT_VERIFIED_GROUP", "BOUNDED_UNKNOWN"):
        return "LEAF_COORDINATE_PROPAGATION_CANDIDATE"
    if (left, right) == ("BOUNDED_UNKNOWN", "SAT_VERIFIED_GROUP"):
        return "INTERMEDIATE_PROPAGATION_CANDIDATE"
    if (left, right) == ("BOUNDED_UNKNOWN", "BOUNDED_UNKNOWN"):
        return "BOTH_RELEASED_BLOCKS_BOUND_SEARCH"
    return "INCOMPLETE_DIAGNOSTIC"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scratch-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite audit result")
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    config, parent_config, parent_result = common.load_config()
    policies = {}
    for policy in config["policies"]:
        witness, build, base, inputs, base_row = common.parent_inputs(
            policy, config, parent_config)
        cells, cells_path = check_partition(policy, args.run_dir, config,
                                            inputs, build, witness)
        results = {mode: check_cell(
            policy, mode, args.run_dir, args.scratch_dir, config, witness,
            build, base, inputs, cells, cells_path)
            for mode in config["modes"]}
        policies[policy] = {
            "parent_base": base_row,
            "parent_mask_only": parent_baseline(policy),
            "cells": results,
            "diagnosis": diagnosis(results),
        }
    intact = all(row["diagnosis"] not in (
        "INCOMPLETE_DIAGNOSTIC", "INCOMPLETE_SEARCH_ACTIVITY")
                 for row in policies.values())
    result = {
        "schema": "ecc2k130-263-projective-s3-search-block-audit-v1",
        "status": ("PASS_PAIRED_BLOCK_DIAGNOSTIC" if intact else
                   "INCOMPLETE_PAIRED_BLOCK_DIAGNOSTIC"),
        "candidate_id": None,
        "proposal_id": config["proposal_id"],
        "parent_commit": config["parent_commit"],
        "parent_audit_sha256": config["parent_sha256"]["runs/R1/audit.json"],
        "config_sha256": ref.sha(common.HERE / "CONFIG.json"),
        "policies": policies,
        "natural_relation_yield": None,
        "novel_rank": None,
        "online_ic_time": None,
        "rho_ratio": None,
        "auditor_sha256": ref.sha(Path(__file__)),
    }
    common.write_json(args.out, result)
    print(json.dumps({"status": result["status"],
                      "diagnosis": {p: r["diagnosis"]
                                    for p, r in policies.items()}},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
