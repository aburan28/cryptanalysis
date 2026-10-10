#!/usr/bin/env python3
"""Replay exact SAT inputs, all model clauses/XORs, and signed group sums."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tempfile

import build_control as circuit
import verify_model as model


HERE = Path(__file__).resolve().parent
PARENT = circuit.PARENT
ref = circuit.ref


def archive_bytes(raw_path, expected_sha, receipt_path, source_sha):
    archive_path = raw_path.with_suffix(raw_path.suffix + ".gz")
    receipt = ref.read(receipt_path)
    if (receipt["status"] != "PASS_LOSSLESS_ARCHIVE"
            or receipt["raw_sha256"] != expected_sha
            or receipt["gzip_sha256"] != ref.sha(archive_path)
            or receipt["gzip_bytes"] != archive_path.stat().st_size
            or receipt["source_sha256"] != source_sha):
        raise ValueError("lossless archive receipt changed: " + str(raw_path))
    with gzip.open(archive_path, "rb") as stream:
        raw = stream.read()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha or len(raw) != receipt["raw_bytes"]:
        raise ValueError("decompressed bytes differ: " + str(raw_path))
    return raw, receipt


def check_parent(config):
    for name, key in (
        ("CONFIG.json", "parent_config_sha256"),
        ("build_projective.py", "parent_builder_sha256"),
        ("audit.py", "parent_auditor_sha256"),
        ("runs/R1/audit.json", "parent_audit_receipt_sha256"),
        ("runs/R1/exceptional_group.json",
         "parent_exceptional_group_sha256"),
    ):
        if ref.sha(PARENT / name) != config[key]:
            raise ValueError("parent source/input changed: " + name)
    parent_audit = ref.read(PARENT / "runs/R1/audit.json")
    if parent_audit["status"] != "PASS_PROJECTIVE_FORMULAS_AND_BOUNDED_SOLVER_TRANSCRIPTS":
        raise ValueError("parent projective audit has not passed")
    return ref.read(PARENT / "runs/R1/exceptional_group.json")


def compose_cell(base_bytes, units, output):
    header, separator, body = base_bytes.partition(b"\n")
    fields = header.split()
    if not separator or len(fields) != 4 or fields[:2] != [b"p", b"cnf"]:
        raise ValueError("control base has invalid XCNF header")
    count = sum(bool(line.strip()) for line in units.splitlines())
    vars_, clauses = map(int, fields[2:])
    with output.open("xb") as stream:
        stream.write(f"p cnf {vars_} {clauses + count}\n".encode())
        stream.write(body)
        stream.write(units)
    return vars_, clauses + count, count


def check_build(policy, run_dir, config):
    stem = run_dir / (policy + "_control_base")
    build_path = stem.with_suffix(".json")
    guard_path = stem.with_suffix(".build_guard.json")
    map_path = stem.with_suffix(".inputs.json")
    build = ref.read(build_path)
    guard = ref.read(guard_path)
    if (build["status"] != "CONTROL_FORMULA_BUILT"
            or build["policy"] != policy
            or build["builder_sha256"] != ref.sha(HERE / "build_control.py")
            or build["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or build["parent_builder_sha256"]
            != config["parent_builder_sha256"]
            or build["input_vars_sha256"] != ref.sha(map_path)
            or build["parent_formula_sha256"]
            != build["reproduced_parent_formula_sha256"]
            or guard["status"]
            != "PASS_CONTROL_FORMULA_BUILT_WITH_EXTERNAL_GUARD"
            or guard["policy"] != policy
            or guard["builder_sha256"] != ref.sha(HERE / "build_control.py")
            or guard["runner_sha256"] != ref.sha(HERE / "run_build.py")
            or guard["formula_sha256"] != build["formula_sha256"]
            or guard["formula_receipt_sha256"] != ref.sha(build_path)
            or guard["input_vars_sha256"] != ref.sha(map_path)
            or guard["stdout_sha256"]
            != ref.sha(stem.with_suffix(".build_stdout.txt"))
            or guard["stderr_sha256"]
            != ref.sha(stem.with_suffix(".build_stderr.txt"))
            or guard["external_wall_cap_seconds"] != 300
            or guard["external_rss_cap_bytes"] != 4 * (1 << 30)
            or guard["wall_seconds"] > 300
            or guard["peak_sampled_rss_bytes"] > 4 * (1 << 30)
            or guard["exit_code"] != 0 or guard["guard"] is not None):
        raise ValueError("control base build or guard failed: " + policy)
    base_bytes, archive_receipt = archive_bytes(
        stem.with_suffix(".xcnf"), build["formula_sha256"],
        stem.with_suffix(".archive.json"),
        ref.sha(HERE / "archive_evidence.py"))
    if archive_receipt["input_receipt_sha256"] != ref.sha(build_path):
        raise ValueError("base archive is not bound to build receipt")
    header = base_bytes.partition(b"\n")[0].split()
    if (int(header[2]) != build["stats"]["vars"]
            or int(header[3])
            != build["stats"]["clauses"] + build["stats"]["xors"]):
        raise ValueError("control base header differs from build receipt")
    return build, base_bytes, ref.read(map_path), {
        "raw_sha256": build["formula_sha256"],
        "raw_bytes": len(base_bytes),
        "gzip_sha256": archive_receipt["gzip_sha256"],
        "build_wall_seconds": guard["wall_seconds"],
        "build_peak_rss_bytes": guard["peak_sampled_rss_bytes"],
    }


def check_cell(policy, mode, run_dir, config, witness, build, base, inputs, cells):
    prefix = run_dir / (policy + "_" + mode)
    delta = prefix.with_suffix(".units.txt")
    cell = cells["cells"][mode]
    receipt_path = prefix.with_suffix(".solver.json")
    solver = ref.read(receipt_path)
    units = delta.read_bytes()
    if (ref.sha(delta) != cell["unit_delta_sha256"]
            or cell["selected_target_choice"] != int(mode == "negative")
            or (cell["unit_count"] != (146 if mode == "free" else 2246))):
        raise ValueError("unit-delta identity or fixed domain changed")
    with tempfile.TemporaryDirectory(prefix="s3-control-audit-") as temp:
        formula = Path(temp) / "reconstructed.xcnf"
        vars_, total, unit_count = compose_cell(base, units, formula)
        if (ref.sha(formula) != cell["xcnf_sha256"]
                or formula.stat().st_size != cell["xcnf_bytes"]
                or vars_ != cell["vars"]
                or total != cell["total_constraints"]
                or unit_count != cell["unit_count"]):
            raise ValueError("reconstructed SAT input differs: " + mode)
        stdout_path = prefix.with_suffix(".stdout.txt")
        output_bytes, stdout_archive = archive_bytes(
            stdout_path, solver["stdout_sha256"],
            prefix.with_suffix(".stdout.archive.json"),
            ref.sha(HERE / "archive_evidence.py"))
        output = output_bytes.decode("utf-8", errors="replace")
        lines = [line.strip() for line in output.splitlines()
                 if line.startswith("s ")]
        maxtime = 120 if mode == "free" else 45
        wall_cap = 150 if mode == "free" else 60
        if (solver["schema"] != "ecc2k130-263-projective-s3-sat-solver-v1"
                or solver["policy"] != policy or solver["mode"] != mode
                or solver["formula_sha256"] != cell["xcnf_sha256"]
                or solver["cell_receipt_sha256"]
                != ref.sha(run_dir / (policy + "_cells.json"))
                or solver["runner_sha256"] != ref.sha(HERE / "run_cell.py")
                or solver["solver_sha256"] != config["solver_sha256"]
                or solver["config_sha256"] != ref.sha(HERE / "CONFIG.json")
                or solver["stderr_sha256"]
                != ref.sha(prefix.with_suffix(".stderr.txt"))
                or stdout_archive["input_receipt_sha256"]
                != ref.sha(receipt_path)
                or solver["terminal_status_lines"] != lines
                or solver["stdout_bytes"] != len(output_bytes)
                or solver["threads"] != 1
                or solver["solver_maxtime_seconds"] != maxtime
                or solver["external_wall_cap_seconds"] != wall_cap
                or solver["rss_cap_bytes"] != 4 * (1 << 30)
                or solver["wall_seconds"] > wall_cap + 2
                or solver["peak_observed_rss_bytes"] > 4 * (1 << 30)
                or solver["command"][1:5] != [
                    "--threads=1", f"--maxtime={maxtime}",
                    "--verb=1", "--printsol=1"]):
            raise ValueError("solver receipt or transcript differs: " + mode)
        status = solver["status"]
        if status == "SAT_UNVERIFIED":
            if lines != ["s SATISFIABLE"] or solver["exit_code"] != 10:
                raise ValueError("SAT receipt has no matching terminal result")
            values = model.parse_assignment(output, vars_)
            clauses = model.verify_xcnf(formula, values)
            group_replay = model.replay_signs(
                policy, inputs, build["target_selector_variables"],
                witness, values)
            status = "SAT_VERIFIED_GROUP"
        else:
            clauses = group_replay = None
            if status == "UNSAT":
                if lines != ["s UNSATISFIABLE"] or solver["exit_code"] != 20:
                    raise ValueError("UNSAT receipt has no matching terminal result")
            elif status == "BOUNDED_UNKNOWN":
                if (solver["guard"] != "WALL_CAP"
                        and (lines != ["s INDETERMINATE"]
                             or solver["exit_code"] != 15)):
                    raise ValueError("bounded receipt has no matching cap")
            elif status not in ("OOM_GUARD", "PRODUCER_FAILURE"):
                raise ValueError("unknown solver status")
        return {
            "status": status,
            "solver_status": solver["status"],
            "exit_code": solver["exit_code"],
            "guard": solver["guard"],
            "wall_seconds": solver["wall_seconds"],
            "peak_observed_rss_bytes": solver["peak_observed_rss_bytes"],
            "exact_input_sha256": cell["xcnf_sha256"],
            "unit_count": unit_count,
            "stdout_sha256": solver["stdout_sha256"],
            "all_constraints_checked": clauses,
            "exact_group_replay": group_replay,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite audit result")
    config = ref.read(HERE / "CONFIG.json")
    group_receipt = check_parent(config)
    policies = {}
    for policy in config["policies"]:
        build, base, inputs, base_row = check_build(policy, args.run_dir, config)
        cells_path = args.run_dir / (policy + "_cells.json")
        cells = ref.read(cells_path)
        if (cells["status"] != "PASS_THREE_EXACT_SAT_INPUTS"
                or cells["policy"] != policy
                or cells["producer_sha256"] != ref.sha(HERE / "make_cells.py")
                or cells["base_xcnf_sha256"] != build["formula_sha256"]
                or cells["input_vars_sha256"]
                != ref.sha(args.run_dir / (policy + "_control_base.inputs.json"))
                or cells["config_sha256"] != ref.sha(HERE / "CONFIG.json")):
            raise ValueError("cell manifest or producer differs: " + policy)
        results = {}
        for mode in ("positive", "negative", "free"):
            results[mode] = check_cell(
                policy, mode, args.run_dir, config,
                group_receipt["policies"][policy], build, base, inputs, cells)
        policies[policy] = {"base": base_row, "cells": results}
    gate_pass = all(
        row["cells"]["positive"]["status"] == "SAT_VERIFIED_GROUP"
        and row["cells"]["negative"]["status"] == "UNSAT"
        for row in policies.values())
    result = {
        "schema": "ecc2k130-263-projective-s3-sat-audit-v1",
        "status": ("PASS_FIXED_EXCEPTIONAL_SAT_AND_GROUP_REPLAY"
                   if gate_pass else "INCOMPLETE_FIXED_EXCEPTIONAL_SAT_GATE"),
        "candidate_id": None,
        "proposal_id": config["proposal_id"],
        "parent_commit": config["parent_commit"],
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "group_witness_sha256": ref.sha(
            PARENT / "runs/R1/exceptional_group.json"),
        "policies": policies,
        "natural_relation_yield": None,
        "novel_rank": None,
        "online_ic_time": None,
        "rho_ratio": None,
        "auditor_sha256": ref.sha(Path(__file__)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "cells": {p: {m: c["status"] for m, c in row["cells"].items()}
                                for p, row in policies.items()}},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
