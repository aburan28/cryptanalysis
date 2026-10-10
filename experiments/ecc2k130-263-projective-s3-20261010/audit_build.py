#!/usr/bin/env python3
"""Independently audit both guarded projective XCNF constructions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import build_projective as circuit


HERE = Path(__file__).resolve().parent
ref = circuit.ref


def count_xcnf(path):
    digest = hashlib.sha256()
    header = None
    ordinary = xors = size = 0
    with path.open("rb") as stream:
        for line in stream:
            digest.update(line)
            size += len(line)
            if line.startswith(b"p cnf "):
                if header is not None:
                    raise ValueError("duplicate XCNF header")
                header = tuple(int(value) for value in line.split()[2:4])
            elif line.startswith(b"x"):
                xors += 1
            elif line.strip() and not line.startswith(b"c"):
                ordinary += 1
    return digest.hexdigest(), size, header, ordinary, xors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite build audit")
    config = ref.read(HERE / "CONFIG.json")
    small = ref.read(HERE / "runs/R1/small_field.json")
    group = ref.read(HERE / "runs/R1/exceptional_group.json")
    boolean = ref.read(HERE / "runs/R1/exceptional_boolean.json")
    if (small["status"] != "PASS_EXHAUSTIVE_GROUP_LAW_EQUIVALENCE"
            or group["status"] != "PASS_TWO_N131_CANCELLATION_GROUP_CONTROLS"
            or boolean["status"]
            != "PASS_SOURCE_AND_DESCENDANT_EXCEPTIONAL_BOOLEAN_CONTROLS"
            or boolean["group_control_sha256"]
            != ref.sha(HERE / "runs/R1/exceptional_group.json")
            or boolean["builder_sha256"]
            != ref.sha(HERE / "build_projective.py")):
        raise ValueError("group-law or Boolean control chain failed")
    policies = {}
    for policy in circuit.POLICIES:
        xs = circuit.check_inputs(policy)
        stem = HERE / "runs/R1" / (policy + "_projective")
        formula = stem.with_suffix(".xcnf")
        receipt = ref.read(stem.with_suffix(".json"))
        guard = ref.read(stem.with_suffix(".build_guard.json"))
        raw_sha, size, header, ordinary, xors = count_xcnf(formula)
        stats = receipt["stats"]
        if (receipt["schema"] != "ecc2k130-263-projective-s3-xcnf-v1"
                or receipt["policy"] != policy
                or receipt["target_x_choices"] != [str(value) for value in xs]
                or receipt["builder_sha256"]
                != ref.sha(HERE / "build_projective.py")
                or receipt["parent_builder_sha256"]
                != config["parent_builder_sha256"]
                or receipt["parent_lifts_sha256"]
                != config["parent_lifts_sha256"]
                or receipt["config_sha256"] != ref.sha(HERE / "CONFIG.json")
                or receipt["small_field_sha256"]
                != ref.sha(HERE / "runs/R1/small_field.json")
                or receipt["exceptional_boolean_sha256"]
                != ref.sha(HERE / "runs/R1/exceptional_boolean.json")
                or receipt["actual_usable_points_B"]
                != config["actual_usable_points_B_each"]
                or receipt["projective_intermediates"] != 4
                or receipt["formula_sha256"] != raw_sha
                or header != (stats["vars"], stats["clauses"]+stats["xors"])
                or (ordinary, xors) != (stats["clauses"], stats["xors"])):
            raise ValueError("formula identity, header, or count failed: " + policy)
        if (guard["status"] != "PASS_FORMULA_BUILT_WITH_EXTERNAL_GUARD"
                or guard["policy"] != policy
                or guard["builder_sha256"] != receipt["builder_sha256"]
                or guard["formula_sha256"] != raw_sha
                or guard["formula_receipt_sha256"]
                != ref.sha(stem.with_suffix(".json"))
                or guard["runner_sha256"] != ref.sha(HERE / "run_build.py")
                or guard["stdout_sha256"]
                != ref.sha(stem.with_suffix(".build_stdout.txt"))
                or guard["stderr_sha256"]
                != ref.sha(stem.with_suffix(".build_stderr.txt"))
                or guard["external_wall_cap_seconds"]
                != config["formula_build_wall_limit_seconds_each"]
                or guard["external_rss_cap_bytes"]
                != config["formula_build_peak_rss_limit_bytes"]
                or guard["wall_seconds"] > guard["external_wall_cap_seconds"]
                or guard["peak_sampled_rss_bytes"]
                > guard["external_rss_cap_bytes"]
                or guard["exit_code"] != 0 or guard["guard"] is not None):
            raise ValueError("external build guard or transcript failed: " + policy)
        policies[policy] = {"formula_sha256": raw_sha,
                            "raw_formula_bytes": size,
                            "vars": header[0],
                            "clauses": ordinary,
                            "native_xors": xors,
                            "build_wall_seconds": guard["wall_seconds"],
                            "sampled_peak_rss_bytes":
                            guard["peak_sampled_rss_bytes"]}
    result = {
        "schema": "ecc2k130-263-projective-s3-build-audit-v1",
        "status": "PASS_TWO_GUARDED_PROJECTIVE_XCNFS",
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "primary_workload_id": config["primary_workload_id"],
        "small_field_sha256": ref.sha(HERE / "runs/R1/small_field.json"),
        "exceptional_boolean_sha256": ref.sha(
            HERE / "runs/R1/exceptional_boolean.json"),
        "policies": policies,
        "source_sha256": ref.sha(Path(__file__)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": result["status"],
                      "policies": policies}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
