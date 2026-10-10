#!/usr/bin/env python3
"""Audit frozen Q1420 native/source XCNFs and capped solver transcripts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re

import field as ref


def audit_formula(path, build, archive):
    if (archive["status"] != "PASS_LOSSLESS_ARCHIVE"
            or archive["raw_formula_sha256"] != build["formula_sha256"]
            or archive["build_receipt_sha256"]
            != ref.sha(path.with_suffix(".json"))
            or archive["gzip_sha256"] != ref.sha(
                path.with_suffix(path.suffix + ".gz"))):
        raise ValueError("formula archive identity failed")
    digest = hashlib.sha256()
    header = None
    regular = xor = 0
    byte_count = 0
    with gzip.open(path.with_suffix(path.suffix + ".gz"), "rb") as stream:
        for line in stream:
            digest.update(line)
            byte_count += len(line)
            if line.startswith(b"p cnf "):
                if header is not None:
                    raise ValueError("duplicate XCNF header")
                header = tuple(int(value) for value in line.split()[2:4])
            elif line.startswith(b"x"):
                xor += 1
            elif line.strip() and not line.startswith(b"c"):
                regular += 1
    stats = build["stats"]
    if (digest.hexdigest() != build["formula_sha256"]
            or byte_count != archive["raw_formula_bytes"]
            or header != (stats["vars"], stats["clauses"]+stats["xors"])
            or (regular, xor) != (stats["clauses"], stats["xors"])):
        raise ValueError("XCNF bytes, header, or clause counts failed")
    return {"raw_sha256": digest.hexdigest(), "bytes": byte_count,
            "vars": header[0], "clauses": regular, "native_xors": xor}


def audit_solver(path, pilot, build, config):
    stdout = path.with_suffix(".stdout.txt")
    stderr = path.with_suffix(".stderr.txt")
    output = stdout.read_text(errors="replace")
    matches = re.findall(r"^c conflicts\s+:\s+(\d+)", output, re.M)
    if (pilot["status"] != "BOUNDED_UNKNOWN"
            or pilot["formula_sha256"] != build["formula_sha256"]
            or pilot["formula_receipt_sha256"]
            != ref.sha(path.parent / (pilot["policy"] + "_m6.json"))
            or pilot["stdout_sha256"] != ref.sha(stdout)
            or pilot["stderr_sha256"] != ref.sha(stderr)
            or pilot["solver_sha256"]
            != "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"
            or pilot["runner_sha256"] != ref.sha(ref.HERE / "run_pilot.py")
            or pilot["primary_workload_id"] != config["primary_workload_id"]
            or pilot["threads"] != 1 or pilot["solver_maxtime_seconds"] != 120
            or pilot["external_wall_cap_seconds"] != 150
            or pilot["rss_cap_bytes"] != 4 * (1 << 30)
            or pilot["wall_seconds"] > 150
            or pilot["peak_observed_rss_bytes"] > 4 * (1 << 30)
            or pilot["exit_code"] != 15 or pilot["guard"] is not None
            or "s INDETERMINATE" not in output
            or "s SATISFIABLE" in output or "s UNSATISFIABLE" in output
            or not matches or int(matches[-1]) <= 0
            or pilot["verified_relation"] is not False
            or pilot["novel_rank"] is not None):
        raise ValueError("solver transcript, resource, or status audit failed")
    return {"status": pilot["status"], "exit_code": pilot["exit_code"],
            "terminal_conflicts": int(matches[-1]),
            "wall_seconds": pilot["wall_seconds"],
            "peak_observed_rss_bytes": pilot["peak_observed_rss_bytes"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite audit result")
    config = ref.read(ref.HERE / "CONFIG.json")
    verification = ref.read(ref.HERE / "runs/R1/verification.json")
    boolean = ref.read(ref.HERE / "runs/R1/boolean_controls.json")
    lifts = ref.read(ref.HERE / "runs/R1/lifts.json")
    mux_dir = ref.HERE / "runs/R1/mux_controls"
    mux = ref.read(mux_dir / "receipt.json")
    primary = ref.read(ref.INPUT / "primary_workload.json")
    if (ref.sha(ref.ROUTE) != config["route_manifest_sha256"]
            or ref.sha(ref.INPUT / "primary_workload.json")
            != config["primary_workload_sha256"]
            or ref.sha(ref.INPUT / "base_selection.json")
            != config["base_selection_sha256"]
            or primary["workload_id"] != config["primary_workload_id"]
            or verification["status"]
            != "PASS_TWO_CURVES_FOUR_LIFTS_AND_M6_CONTROLS"
            or verification["lifts_sha256"]
            != ref.sha(ref.HERE / "runs/R1/lifts.json")
            or boolean["status"]
            != "PASS_TWO_POSITIVE_AND_SIX_NEGATIVE_IR_CONTROLS"
            or boolean["circuit_source_sha256"]
            != ref.sha(ref.HERE / "build_formula.py")
            or mux["status"]
            != "PASS_EIGHT_POSITIVE_EIGHT_NEGATIVE_XOR_CONTROLS"
            or mux["lifts_sha256"]
            != ref.sha(ref.HERE / "runs/R1/lifts.json")
            or mux["source_sha256"] != ref.sha(ref.HERE / "check_mux.py")
            or mux["builder_sha256"]
            != ref.sha(ref.HERE / "build_formula.py")
            or lifts["transported_source_lift_set_matches_descendant"] is not True):
        raise ValueError("geometry or Boolean control chain failed")
    policies = {}
    for policy in ("source", "descendant_native"):
        stem = ref.HERE / "runs/R1" / (policy + "_m6")
        build = ref.read(stem.with_suffix(".json"))
        archive = ref.read(stem.with_suffix(".archive.json"))
        pilot_path = ref.HERE / "runs/R1" / (policy + "_m6_pilot.json")
        pilot = ref.read(pilot_path)
        if (build["policy"] != policy or pilot["policy"] != policy
                or build["builder_sha256"]
                != ref.sha(ref.HERE / "build_formula.py")
                or build["field_source_sha256"] != ref.sha(ref.HERE / "field.py")
                or build["lifts_sha256"]
                != ref.sha(ref.HERE / "runs/R1/lifts.json")
                or build["actual_usable_points_B"]
                != config["selected_usable_points_B_each"]
                or build["build_wall_seconds"]
                > config["formula_build_wall_limit_seconds_each"]
                or build["peak_rss_bytes"]
                > config["formula_build_peak_rss_limit_bytes"]
                or build["target_x_choices"] != [
                    str(row[0]) for row in lifts[policy]["raw_target_lifts"]]):
            raise ValueError("formula manifest policy or input binding failed")
        mux_cases = mux["policies"][policy]
        if (mux_cases["target_x_choices"] != build["target_x_choices"]
                or len(mux_cases["cases"]) != 8
                or {(case["choice"], case["changed_x_bit_zero"])
                    for case in mux_cases["cases"]}
                != {(j, changed) for j in range(4)
                    for changed in (False, True)}):
            raise ValueError("target mux control domain changed")
        for case in mux_cases["cases"]:
            choice = case["choice"]
            altered = case["changed_x_bit_zero"]
            name = "%s_j%d_%s" % (
                policy, choice, "xbit0_changed" if altered else "exact")
            if (choice not in range(4) or not isinstance(altered, bool)
                    or case["expected_x"] != str(
                        int(build["target_x_choices"][choice]) ^ int(altered))
                    or case["status"] != ("UNSAT" if altered else "SAT")
                    or case["formula_sha256"]
                    != ref.sha(mux_dir / (name + ".xcnf"))
                    or case["stdout_sha256"]
                    != ref.sha(mux_dir / (name + ".stdout.txt"))
                    or case["stderr_sha256"]
                    != ref.sha(mux_dir / (name + ".stderr.txt"))):
                raise ValueError("native-XOR mux case failed replay")
        policies[policy] = {
            "formula": audit_formula(stem.with_suffix(".xcnf"), build, archive),
            "pilot": audit_solver(pilot_path, pilot, build, config),
        }
    result = {
        "schema": "ecc2k130-263-native-w24-m6-audit-v1",
        "status": "PASS_EXACT_FORMULAS_AND_BOUNDED_SOLVER_TRANSCRIPTS",
        "proposal_id": config["proposal_id"],
        "candidate_id": None,
        "primary_workload_id": config["primary_workload_id"],
        "config_sha256": ref.sha(ref.HERE / "CONFIG.json"),
        "geometry_verification_sha256": ref.sha(
            ref.HERE / "runs/R1/verification.json"),
        "boolean_controls_sha256": ref.sha(
            ref.HERE / "runs/R1/boolean_controls.json"),
        "target_mux_controls_sha256": ref.sha(mux_dir / "receipt.json"),
        "policies": policies,
        "construction_external_guard_enforced": False,
        "natural_relation_yield": None,
        "verified_relation_rank": None,
        "online_wall_time": None,
        "rho_ratio": None,
        "auditor_sha256": ref.sha(Path(__file__)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": result["status"],
                      "policies": {name: row["pilot"] for name, row in
                                   policies.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
