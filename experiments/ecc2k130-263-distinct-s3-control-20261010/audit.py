#!/usr/bin/env python3
"""Independently replay finite-witness inputs, SAT transcripts, and group sums."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import re
import shutil
import tempfile

import distinct
import verify_model as model


ref = distinct.ref


def checked_witness(cfg):
    archived = distinct.witness(cfg)
    geometry = ref.read(distinct.NATIVE / "runs/R1/geometry_controls.json")
    workload = ref.read(distinct.WORKLOAD / "primary_workload.json")
    from binary_group import add, on_curve, projective_x, s3_projective, times
    for policy in cfg["policies"]:
        control = archived["policies"][policy]
        rows = [geometry[policy]["leaves"][index]
                for index in cfg["geometry_leaf_indices"]]
        alpha, b = ref.coefficients(policy)
        masks = [row["mask"] for row in rows]
        points = [tuple(row["raw_point"]) for row in rows]
        if (control["leaf_masks"] != masks
                or len(set(masks)) != 6
                or masks != sorted(masks)
                or len({point[0] for point in points}) != 6
                or any(not on_curve(point, b) for point in points)
                or alpha != control["alpha"] or b != control["normalized_b"]):
            raise ValueError("witness and exact archived geometry disagree")
        for index, (row, point) in enumerate(zip(rows, points)):
            x, z, w = ref.leaf(row["mask"], alpha)
            if (x != point[0] or z != row["z"] or w != row["w"]
                    or control["leaves"][index] != {
                        "mask": row["mask"],
                        "raw_point_normalized": list(point), "z": z}):
                raise ValueError("checked leaf differs from archived base")
        fourfold = [times(point, 4, b) for point in points]
        order = int(workload["subgroup_order"])
        if (any(point is None or times(point, order, b) is not None
                for point in fourfold)
                or len(set(fourfold)) != 6
                or control["fourfold_subgroup_points"]
                != [list(point) for point in fourfold]):
            raise ValueError("fourfold subgroup projection differs")
        pairs = [add(points[index], points[index + 1], b)
                 for index in (0, 2, 4)]
        combined = add(pairs[0], pairs[1], b)
        target = add(combined, pairs[2], b)
        chain = pairs + [combined, target]
        if (any(point is None for point in chain)
                or list(target) != cfg["expected_targets"][policy]
                or control["target_point_normalized"] != list(target)
                or control["target_x"] != target[0]
                or control["intermediates"] != [
                    {"x": point[0], "finite": True} for point in chain[:4]]):
            raise ValueError("finite target chain differs")
        proj = [projective_x(point) for point in chain]
        links = [
            (projective_x(points[0]), projective_x(points[1]), proj[0]),
            (projective_x(points[2]), projective_x(points[3]), proj[1]),
            (projective_x(points[4]), projective_x(points[5]), proj[2]),
            (proj[0], proj[1], proj[3]),
            (proj[3], proj[2], proj[4]),
        ]
        if any(s3_projective(*link, b) != 0 for link in links):
            raise ValueError("independent projective S3 replay failed")
    return archived


def expected_unit_bytes(mode, control, input_vars, choice, cfg):
    values = {}

    def fix(name, width, word):
        for bit in range(width):
            variable = input_vars[f"{name}:{bit}"]
            if variable in values:
                raise ValueError("duplicate named input variable")
            values[variable] = (word >> bit) & 1

    for index, row in enumerate(control["leaves"]):
        fix(f"s{index}", 24, row["mask"])
        if mode != f"x{index}":
            fix(f"x{index}", ref.DEGREE,
                row["raw_point_normalized"][0])
        if mode != f"z{index}":
            fix(f"z{index}", ref.DEGREE, row["z"])
    for index, point in enumerate(control["intermediates"]):
        fix(f"t{index}", ref.DEGREE, point["x"])
        variable = input_vars[f"f:{index}"]
        if variable in values or not point["finite"]:
            raise ValueError("unexpected state flag")
        values[variable] = 1
    if len(choice) != 2:
        raise ValueError("target selector width changed")
    selected = int(mode == "negative")
    for bit, variable in enumerate(choice):
        if variable in values:
            raise ValueError("target selector overlaps witness input")
        values[variable] = (selected >> bit) & 1
    count = (cfg["single_coordinate_fixed_units"]
             if mode in ("x0", "z0", "x5", "z5")
             else cfg["fixed_positive_units"])
    if len(values) != count:
        raise ValueError("independent fixed-unit count changed")
    literals = sorted(variable if value else -variable
                      for variable, value in values.items())
    return "".join(f"{literal} 0\n" for literal in literals).encode()


def reconstruct(base, delta, output):
    lines = delta.splitlines()
    if any(not re.fullmatch(rb"-?[1-9][0-9]* 0", line)
           for line in lines):
        raise ValueError("malformed unit-clause delta")
    with base.open("rb") as source, output.open("xb") as dest:
        header = source.readline().split()
        if len(header) != 4 or header[:2] != [b"p", b"cnf"]:
            raise ValueError("invalid archived XCNF header")
        variables, constraints = map(int, header[2:])
        dest.write(f"p cnf {variables} {constraints + len(lines)}\n".encode())
        shutil.copyfileobj(source, dest, length=1 << 20)
        dest.write(delta)
    return variables, constraints + len(lines), len(lines)


def progress(output):
    rows = [line for line in output.splitlines() if line.startswith("c rst ")]
    conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", output,
                           re.MULTILINE)
    return {"restart_rows": len(rows),
            "last_restart_row": rows[-1] if rows else None,
            "final_conflicts": int(conflicts[-1]) if conflicts else None}


def audit_policy(policy, cfg, checked, scratch):
    control = checked["policies"][policy]
    archive, map_path, base_path = distinct.base_paths(policy)
    base_row = ref.read(base_path)
    inputs = ref.read(map_path)
    target = control["target_x"]
    if (base_row["schema"] != "ecc2k130-263-distinct-s3-base-v1"
            or base_row["status"] != "CONTROL_FORMULA_BUILT"
            or base_row["policy"] != policy
            or base_row["target_x_choices"]
            != [str(target)] + [str(target ^ 1)] * 3
            or base_row["formula_gzip_sha256"] != ref.sha(archive)
            or base_row["formula_gzip_bytes"] != archive.stat().st_size
            or base_row["input_vars_sha256"] != ref.sha(map_path)
            or base_row["input_vars_count"] != len(inputs)
            or base_row["config_sha256"] != ref.sha(distinct.HERE / "CONFIG.json")
            or base_row["witness_sha256"] != ref.sha(distinct.RUN / "witness.json")
            or base_row["builder_sha256"] != ref.sha(distinct.HERE / "distinct.py")
            or base_row["projective_builder_sha256"]
            != cfg["projective_builder_sha256"]
            or base_row["sat_builder_sha256"] != cfg["sat_builder_sha256"]):
        raise ValueError("base formula receipt or source differs")
    cells_path = distinct.RUN / f"{policy}_cells.json"
    cells = ref.read(cells_path)
    if (cells["schema"] != "ecc2k130-263-distinct-s3-cells-v1"
            or cells["status"] != "PASS_SIX_EXACT_INPUTS"
            or cells["policy"] != policy
            or cells["config_sha256"] != ref.sha(distinct.HERE / "CONFIG.json")
            or cells["producer_sha256"] != ref.sha(distinct.HERE / "distinct.py")
            or cells["witness_sha256"] != ref.sha(distinct.RUN / "witness.json")
            or cells["base_receipt_sha256"] != ref.sha(base_path)
            or cells["base_gzip_sha256"] != ref.sha(archive)
            or cells["input_vars_sha256"] != ref.sha(map_path)
            or set(cells["cells"]) != set(cfg["modes"])):
        raise ValueError("frozen cell receipt differs")
    rows = {}
    with tempfile.TemporaryDirectory(prefix="distinct-s3-audit-",
                                     dir=scratch) as temporary:
        base = Path(temporary) / "base.xcnf"
        with gzip.open(archive, "rb") as source, base.open("xb") as dest:
            shutil.copyfileobj(source, dest, length=1 << 20)
        if (ref.sha(base) != base_row["formula_raw_sha256"]
                or base.stat().st_size != base_row["formula_raw_bytes"]):
            raise ValueError("lossless base archive differs")
        for mode in cfg["modes"]:
            row = cells["cells"][mode]
            prefix = distinct.RUN / f"{policy}_{mode}"
            delta = prefix.with_suffix(".units.txt").read_bytes()
            expected = expected_unit_bytes(
                mode, control, inputs,
                base_row["target_selector_variables"], cfg)
            if (delta != expected
                    or row["unit_delta_sha256"] != distinct.sha_bytes(delta)
                    or row["target_choice"] != int(mode == "negative")
                    or row["released_coordinate_bits"] != (
                        cfg["released_coordinate_bits"]
                        if mode in ("x0", "z0", "x5", "z5") else 0)):
                raise ValueError("exact unit delta differs")
            formula = Path(temporary) / f"{mode}.xcnf"
            variables, constraints, count = reconstruct(base, delta, formula)
            if (ref.sha(formula) != row["formula_sha256"]
                    or formula.stat().st_size != row["formula_bytes"]
                    or variables != row["variables"]
                    or constraints != row["total_constraints"]
                    or count != row["unit_count"]):
                raise ValueError("full reconstructed SAT input differs")
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
            if (solver["schema"] != "ecc2k130-263-distinct-s3-solver-v1"
                    or solver["policy"] != policy or solver["mode"] != mode
                    or solver["formula_sha256"] != row["formula_sha256"]
                    or solver["cell_receipt_sha256"] != ref.sha(cells_path)
                    or solver["config_sha256"]
                    != ref.sha(distinct.HERE / "CONFIG.json")
                    or solver["runner_sha256"]
                    != ref.sha(distinct.HERE / "distinct.py")
                    or solver["solver_sha256"] != cfg["solver_sha256"]
                    or solver["stdout_raw_sha256"]
                    != distinct.sha_bytes(raw_output)
                    or solver["stdout_raw_bytes"] != len(raw_output)
                    or solver["stdout_archive_sha256"] != ref.sha(stdout_archive)
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
                raise ValueError("solver receipt or transcript differs")
            state = solver["status"]
            trace = progress(output)
            if state == "SAT_UNVERIFIED":
                if terminal != ["s SATISFIABLE"] or solver["exit_code"] != 10:
                    raise ValueError("SAT transcript is incomplete")
                assignment = model.parse_assignment(output, variables)
                checks = model.verify_xcnf(formula, assignment)
                replay = model.replay_signs(policy, inputs,
                    base_row["target_selector_variables"], control, assignment)
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
                        raise ValueError("bounded cell has no search progress")
                elif state == "OOM_GUARD":
                    if solver["guard"] != "RSS_CAP":
                        raise ValueError("RSS status lacks guard")
                elif state != "PRODUCER_FAILURE":
                    raise ValueError("unknown solver status")
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
    return {"base_formula_sha256": base_row["formula_raw_sha256"],
            "cells": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-dir", type=Path, default=Path("/private/tmp"))
    parser.add_argument("--out", type=Path, default=distinct.RUN / "audit.json")
    args = parser.parse_args()
    cfg = distinct.config()
    checked = checked_witness(cfg)
    policies = {policy: audit_policy(policy, cfg, checked, args.scratch_dir)
                for policy in cfg["policies"]}
    controls_pass = all(
        policies[policy]["cells"]["positive"]["status"]
        == "SAT_VERIFIED_GROUP"
        and policies[policy]["cells"]["negative"]["status"] == "UNSAT"
        for policy in cfg["policies"])
    result = {
        "schema": "ecc2k130-263-distinct-s3-audit-v1",
        "status": ("PASS_EXACT_INPUTS_AND_TRANSCRIPTS" if controls_pass
                   else "CONTROL_FAILURE"),
        "candidate_id": None,
        "config_sha256": ref.sha(distinct.HERE / "CONFIG.json"),
        "protocol_sha256": ref.sha(distinct.HERE / "PROTOCOL.md"),
        "witness_sha256": ref.sha(distinct.RUN / "witness.json"),
        "producer_sha256": ref.sha(distinct.HERE / "distinct.py"),
        "auditor_sha256": ref.sha(Path(__file__)),
        "policies": policies,
    }
    distinct.write_json(args.out, result)
    print(json.dumps({"status": result["status"],
                      "cells": {policy: {mode: row["status"]
                          for mode, row in item["cells"].items()}
                          for policy, item in policies.items()}},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
