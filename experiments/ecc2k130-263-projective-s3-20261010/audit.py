#!/usr/bin/env python3
"""Independently audit projective-S3 controls, formulas, and solver evidence."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re

import build_projective as circuit


HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs/R1"
ref = circuit.ref
SOLVER_SHA = "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"


def check_controls(config):
    small = ref.read(RUNS / "small_field.json")
    group = ref.read(RUNS / "exceptional_group.json")
    boolean = ref.read(RUNS / "exceptional_boolean.json")
    build_audit = ref.read(RUNS / "build_audit.json")
    config_sha = ref.sha(HERE / "CONFIG.json")
    if (small["status"] != "PASS_EXHAUSTIVE_GROUP_LAW_EQUIVALENCE"
            or small["config_sha256"] != config_sha
            or small["source_sha256"] != ref.sha(HERE / "verify_small.py")
            or small["sage_runtime_info_sha256"]
            != ref.sha(RUNS / "runtime-info.json")
            or {(r["degree"], r["b"]) for r in small["results"]}
            != {(n, b) for n in (5, 7) for b in ("one", "generator")}
            or sum(r["ordered_class_triples"] for r in small["results"])
            != 497084
            or any(r["accepted_with_infinity"] <= 0 or
                   r["accepted_with_x_zero"] <= 0 for r in small["results"])):
        raise ValueError("small-field control receipt failed")
    if (group["status"] != "PASS_TWO_N131_CANCELLATION_GROUP_CONTROLS"
            or group["config_sha256"] != config_sha
            or group["source_sha256"] != ref.sha(HERE / "exceptional_control.py")
            or group["binary_group_source_sha256"]
            != ref.sha(HERE / "binary_group.py")
            or group["sage_runtime_info_sha256"]
            != ref.sha(RUNS / "runtime-info.json")
            or boolean["status"]
            != "PASS_SOURCE_AND_DESCENDANT_EXCEPTIONAL_BOOLEAN_CONTROLS"
            or boolean["config_sha256"] != config_sha
            or boolean["source_sha256"] != ref.sha(HERE / "check_exceptional.py")
            or boolean["group_control_sha256"]
            != ref.sha(RUNS / "exceptional_group.json")
            or boolean["small_field_sha256"]
            != ref.sha(RUNS / "small_field.json")
            or boolean["builder_sha256"] != ref.sha(HERE / "build_projective.py")):
        raise ValueError("n131 group/Boolean control chain failed")
    for policy in circuit.POLICIES:
        g = group["policies"][policy]
        b = boolean["policies"][policy]
        if (not g["first_pair_is_infinity"]
                or not g["independent_group_law_matches_sage"]
                or not g["all_links_zero"]
                or g["intermediates"][0] != {"finite": False, "x": 1}
                or not b["first_pair_is_infinity"]
                or not b["positive_roots_zero"]
                or b["mutations"] != dict.fromkeys(
                    ("f", "t0", "z0", "target"), "rejected")):
            raise ValueError("exceptional witness or mutation control failed")
    if (build_audit["status"] != "PASS_TWO_GUARDED_PROJECTIVE_XCNFS"
            or build_audit["config_sha256"] != config_sha
            or build_audit["source_sha256"] != ref.sha(HERE / "audit_build.py")
            or build_audit["small_field_sha256"]
            != ref.sha(RUNS / "small_field.json")
            or build_audit["exceptional_boolean_sha256"]
            != ref.sha(RUNS / "exceptional_boolean.json")):
        raise ValueError("guarded-build audit chain failed")
    return build_audit


def audit_formula(policy, config, build_audit):
    stem = RUNS / (policy + "_projective")
    build = ref.read(stem.with_suffix(".json"))
    guard = ref.read(stem.with_suffix(".build_guard.json"))
    archive = ref.read(stem.with_suffix(".archive.json"))
    archive_path = stem.with_suffix(".xcnf.gz")
    if (build["schema"] != "ecc2k130-263-projective-s3-xcnf-v1"
            or build["policy"] != policy
            or build["builder_sha256"] != ref.sha(HERE / "build_projective.py")
            or build["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or build["small_field_sha256"]
            != ref.sha(RUNS / "small_field.json")
            or build["exceptional_boolean_sha256"]
            != ref.sha(RUNS / "exceptional_boolean.json")
            or build["actual_usable_points_B"]
            != config["actual_usable_points_B_each"]
            or build["summands"] != 6
            or build["projective_intermediates"] != 4
            or build["target_x_choices"] != [
                str(x) for x in circuit.check_inputs(policy)]):
        raise ValueError("formula input or source binding failed: " + policy)
    if (archive["schema"] != "ecc2k130-263-projective-s3-xcnf-archive-v1"
            or archive["status"] != "PASS_LOSSLESS_ARCHIVE"
            or archive["policy"] != policy
            or archive["source_sha256"] != ref.sha(HERE / "archive_formula.py")
            or archive["build_receipt_sha256"] != ref.sha(stem.with_suffix(".json"))
            or archive["gzip_sha256"] != ref.sha(archive_path)
            or archive["gzip_bytes"] != archive_path.stat().st_size
            or archive["raw_formula_sha256"] != build["formula_sha256"]):
        raise ValueError("archive identity failed: " + policy)
    digest = hashlib.sha256()
    header = None
    clauses = xors = byte_count = 0
    with gzip.open(archive_path, "rb") as stream:
        for line in stream:
            digest.update(line)
            byte_count += len(line)
            if line.startswith(b"p cnf "):
                if header is not None:
                    raise ValueError("duplicate XCNF header")
                header = tuple(map(int, line.split()[2:4]))
            elif line.startswith(b"x"):
                xors += 1
            elif line.strip() and not line.startswith(b"c"):
                clauses += 1
    stats = build["stats"]
    if (digest.hexdigest() != build["formula_sha256"]
            or byte_count != archive["raw_formula_bytes"]
            or header != (stats["vars"], stats["clauses"] + stats["xors"])
            or (clauses, xors) != (stats["clauses"], stats["xors"])):
        raise ValueError("archived XCNF bytes or header failed: " + policy)
    audit_row = build_audit["policies"][policy]
    if (audit_row["formula_sha256"] != digest.hexdigest()
            or audit_row["raw_formula_bytes"] != byte_count
            or (audit_row["vars"], audit_row["clauses"],
                audit_row["native_xors"]) != (header[0], clauses, xors)):
        raise ValueError("construction audit disagrees with archive: " + policy)
    if (guard["status"] != "PASS_FORMULA_BUILT_WITH_EXTERNAL_GUARD"
            or guard["policy"] != policy
            or guard["formula_sha256"] != digest.hexdigest()
            or guard["formula_receipt_sha256"]
            != ref.sha(stem.with_suffix(".json"))
            or guard["runner_sha256"] != ref.sha(HERE / "run_build.py")
            or guard["stdout_sha256"]
            != ref.sha(stem.with_suffix(".build_stdout.txt"))
            or guard["stderr_sha256"]
            != ref.sha(stem.with_suffix(".build_stderr.txt"))
            or guard["external_wall_cap_seconds"] != 300
            or guard["external_rss_cap_bytes"] != 4 * (1 << 30)
            or guard["wall_seconds"] > 300
            or guard["peak_sampled_rss_bytes"] > 4 * (1 << 30)
            or guard["exit_code"] != 0 or guard["guard"] is not None):
        raise ValueError("construction guard or transcript failed: " + policy)
    return build, {"raw_sha256": digest.hexdigest(), "bytes": byte_count,
                   "vars": header[0], "clauses": clauses,
                   "native_xors": xors, "gzip_sha256": ref.sha(archive_path),
                   "build_wall_seconds": guard["wall_seconds"],
                   "build_peak_rss_bytes": guard["peak_sampled_rss_bytes"]}


def audit_solver(policy, build, config):
    name = ("source_projective_pilot_retry1" if policy == "source" else
            "descendant_native_projective_pilot")
    path = RUNS / (name + ".json")
    pilot = ref.read(path)
    stdout = RUNS / (name + ".stdout.txt")
    stderr = RUNS / (name + ".stderr.txt")
    output = stdout.read_text(errors="replace")
    conflicts = re.findall(r"^c conflicts\s+:\s+(\d+)", output, re.M)
    if (pilot["schema"] != "ecc2k130-263-projective-s3-pilot-v1"
            or pilot["status"] != "BOUNDED_UNKNOWN"
            or pilot["policy"] != policy
            or pilot["primary_workload_id"] != config["primary_workload_id"]
            or pilot["ordinary_query_index"] != config["first_query_index"]
            or pilot["formula_sha256"] != build["formula_sha256"]
            or pilot["formula_receipt_sha256"]
            != ref.sha(RUNS / (policy + "_projective.json"))
            or pilot["build_audit_sha256"] != ref.sha(RUNS / "build_audit.json")
            or pilot["runner_sha256"] != ref.sha(HERE / "run_pilot.py")
            or pilot["solver_sha256"] != SOLVER_SHA
            or pilot["stdout_sha256"] != ref.sha(stdout)
            or pilot["stderr_sha256"] != ref.sha(stderr)
            or pilot["threads"] != 1
            or pilot["solver_maxtime_seconds"] != 120
            or pilot["external_wall_cap_seconds"] != 150
            or pilot["rss_cap_bytes"] != 4 * (1 << 30)
            or pilot["wall_seconds"] > 150
            or pilot["peak_observed_rss_bytes"] > 4 * (1 << 30)
            or pilot["guard"] is not None or pilot["exit_code"] != 15
            or pilot["command"][1:5]
            != ["--threads=1", "--maxtime=120", "--verb=1", "--printsol=1"]
            or "s INDETERMINATE" not in output
            or "s SATISFIABLE" in output or "s UNSATISFIABLE" in output
            or not conflicts or int(conflicts[-1]) <= 0
            or pilot["verified_relation"] is not False
            or pilot["novel_rank"] is not None):
        raise ValueError("solver status, source, or transcript failed: " + policy)
    return {"status": pilot["status"], "terminal_conflicts": int(conflicts[-1]),
            "exit_code": pilot["exit_code"], "wall_seconds": pilot["wall_seconds"],
            "peak_observed_rss_bytes": pilot["peak_observed_rss_bytes"],
            "stdout_sha256": pilot["stdout_sha256"]}


def audit_failures():
    first = ref.read(RUNS / "source_pilot_failed_preflight.json")
    second = ref.read(RUNS / "source_projective_pilot_failed_receipt.json")
    sandbox = ref.read(RUNS / "source_retry1_sandbox_preflight.json")
    if (first["status"] != "PRODUCER_FAILURE"
            or first["solver_started"] is not False
            or first["stage"] != "solver_limit_config_lookup"
            or second["status"] != "PRODUCER_FAILURE"
            or second["stage"] != "post_solver_receipt_write"
            or second["solver_started"] is not True
            or second["stdout_sha256"]
            != ref.sha(RUNS / second["raw_stdout"])
            or second["stderr_sha256"]
            != ref.sha(RUNS / second["raw_stderr"])
            or sandbox["status"] != "PRODUCER_FAILURE"
            or sandbox["solver_started"] is not False
            or sandbox["stage"] != "rss_sampler_preflight"
            or sandbox["formula_sha256"]
            != ref.read(RUNS / "source_projective.json")["formula_sha256"]
            or sandbox["runner_sha256"] != ref.sha(HERE / "run_pilot.py")):
        raise ValueError("failed producer/preflight chain failed")
    return {"config_preflight": first["status"],
            "post_solver_receipt": second["status"],
            "sandbox_rss_preflight": sandbox["status"],
            "post_solver_stdout_sha256": second["stdout_sha256"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite audit result")
    config = ref.read(HERE / "CONFIG.json")
    build_audit = check_controls(config)
    policies = {}
    for policy in circuit.POLICIES:
        build, formula = audit_formula(policy, config, build_audit)
        policies[policy] = {"formula": formula,
                            "pilot": audit_solver(policy, build, config)}
    result = {
        "schema": "ecc2k130-263-projective-s3-audit-v1",
        "status": "PASS_PROJECTIVE_FORMULAS_AND_BOUNDED_SOLVER_TRANSCRIPTS",
        "candidate_id": None,
        "proposal_id": config["proposal_id"],
        "primary_workload_id": config["primary_workload_id"],
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "small_field_sha256": ref.sha(RUNS / "small_field.json"),
        "exceptional_group_sha256": ref.sha(RUNS / "exceptional_group.json"),
        "exceptional_boolean_sha256": ref.sha(RUNS / "exceptional_boolean.json"),
        "build_audit_sha256": ref.sha(RUNS / "build_audit.json"),
        "policies": policies,
        "preserved_failures": audit_failures(),
        "natural_relation_yield": None,
        "verified_relation_rank": None,
        "online_wall_time": None,
        "rho_ratio": None,
        "auditor_sha256": ref.sha(Path(__file__)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "policies": {p: r["pilot"] for p, r in policies.items()}},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
