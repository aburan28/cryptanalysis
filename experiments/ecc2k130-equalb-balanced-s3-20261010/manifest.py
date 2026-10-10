#!/usr/bin/env python3
"""Verify and hash the balanced-S3 source, controls, and bounded raw evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_balanced as balanced
import archive_formulas  # noqa: E402; balanced adds the parent path


RUN = balanced.HERE / "runs/R1"
MANIFEST = RUN / "manifest.json"
PARENT = balanced.PARENT / "runs/R1"
LEAF = balanced.gate.PARENT / "runs/R1"
PARENT_INPUTS = (
    balanced.PARENT / "build_four_lift.py",
    balanced.PARENT / "archive_formulas.py",
    balanced.PARENT / "runs/R1/manifest.json",
    PARENT / "sage_lifts.json",
    PARENT / "mux_controls/receipt.json",
    PARENT / "normal4_m6_four_lift.json",
    PARENT / "w24_m6_four_lift.json",
    balanced.gate.PARENT / "build_formula.py",
    balanced.gate.PARENT / "field.py",
    balanced.gate.PARENT / "run_pilot.py",
    LEAF / "sage_verification.json",
    LEAF / "cnf_controls/receipt.json",
    balanced.gate.PUBLIC,
    balanced.ref.EQUAL / "CONFIG.json",
    balanced.ref.EQUAL / "runs/R1/base_prefixes.json",
    *(balanced.source.CODEGEN / name for name in ("build.py", "ir.py", "cnf.py")),
)


def read(path: Path):
    return json.loads(path.read_text())


def collect() -> dict:
    runtime = read(RUN / "runtime-info.json")
    sage = read(RUN / "sage_balanced.json")
    parent = read(PARENT / "manifest.json")
    parent_lifts = read(PARENT / "sage_lifts.json")
    parent_mux = read(PARENT / "mux_controls/receipt.json")
    leaf_sage = read(LEAF / "sage_verification.json")
    leaf_cnf = read(LEAF / "cnf_controls/receipt.json")
    if (runtime["status"] != "verified"
            or sage["status"]
            != "PASS_INDEPENDENT_BALANCED_POINT_AND_BOOLEAN_REPLAY"
            or parent["status"] != "PASS_SOURCE_AND_RUN_EVIDENCE"
            or parent_lifts["status"] != "PASS_INDEPENDENT_FOUR_RAW_LIFTS"
            or parent_mux["status"]
            != "PASS_FOUR_POSITIVE_FOUR_NEGATIVE_NATIVE_XOR_CONTROLS"
            or leaf_sage["status"] != "PASS_SAGE_POINT_AND_BOOLEAN_REPLAY"
            or leaf_cnf["status"] != "PASS_PINNED_POSITIVE_AND_NEGATIVE"
            or sage["runtime_info_sha256"]
            != balanced.ref.sha(RUN / "runtime-info.json")
            or sage["builder_sha256"]
            != balanced.ref.sha(balanced.HERE / "build_balanced.py")):
        raise ValueError("Sage, leaf, or four-lift prerequisite changed")
    for policy in balanced.POLICIES:
        control = sage["controls"][policy]
        if (not control["positive_boolean_replay"]
                or not control["negative_target_x_bit0_rejected"]
                or control["finite_intermediate_count"] != 4):
            raise ValueError("balanced point control failed: " + policy)
    expected = {
        "normal4_source": ("normal4", 536683, 599988, 300963, 657),
        "w24_source": ("w24", 336209, 340190, 221402, 749),
    }
    for policy, (name, variables, clauses, xors, last_restart) in (
            expected.items()):
        stem = name + "_m6_four_lift"
        built = read(RUN / (stem + ".json"))
        parent_built = read(PARENT / (stem + ".json"))
        archive = read(RUN / (stem + ".archive.json"))
        pilot_path = RUN / (stem + "_pilot.json")
        pilot = read(pilot_path)
        audit = read(RUN / (stem + "_audit.json"))
        formula_path = RUN / (stem + ".xcnf.gz")
        raw_sha, raw_bytes = archive_formulas.decompressed_sha(formula_path)
        stats = built["stats"]
        if (built["schema"] != "ecc2k130-equalb-balanced-s3-m6-xcnf-v1"
                or built["policy"] != policy
                or built["actual_usable_points_B"] != 11743888
                or built["target_x_choices"] != [
                    str(x) for x in balanced.gate.target_lifts()]
                or built["builder_sha256"] != balanced.ref.sha(
                    balanced.HERE / "build_balanced.py")
                or stats != {"vars": variables, "clauses": clauses,
                             "xors": xors}
                or {key: parent_built["stats"][key] - stats[key]
                    for key in stats} != {"vars": 1030, "clauses": 131,
                                          "xors": 899}
                or raw_sha != built["formula_sha256"]
                or raw_sha != archive["raw_formula_sha256"]
                or raw_bytes != archive["raw_formula_bytes"]
                or balanced.ref.sha(formula_path) != archive["archive_sha256"]
                or archive["formula_receipt_sha256"]
                != balanced.ref.sha(RUN / (stem + ".json"))
                or pilot["policy"] != policy
                or pilot["status"] != "BOUNDED_UNKNOWN"
                or pilot["guard"] != "WALL_CAP"
                or pilot["verified_relation"]
                or pilot["novel_rank"] is not None
                or pilot["formula_sha256"] != raw_sha
                or audit["status"] != "PASS_TRANSCRIPT_AND_SOURCE_BINDING"
                or audit["solver_status"] != pilot["status"]
                or audit["pilot_sha256"] != balanced.ref.sha(pilot_path)
                or audit["last_live_restart_count"] != last_restart
                or audit["live_restart_rows"] <= 0
                or audit["audit_source_sha256"] != balanced.ref.sha(
                    balanced.HERE / "audit_balanced.py")):
            raise ValueError("balanced formula or raw search changed: " + name)
    local = [path for path in balanced.HERE.rglob("*")
             if path.is_file() and path != MANIFEST
             and "__pycache__" not in path.parts]
    files = sorted(local + list(PARENT_INPUTS),
                   key=lambda path: str(path.relative_to(balanced.ROOT)))
    return {
        "schema": "ecc2k130-equalb-balanced-s3-evidence-manifest-v1",
        "status": "PASS_SOURCE_AND_BOUNDED_RUN_EVIDENCE",
        "candidate_id": None,
        "file_count": len(files),
        "files_sha256": {
            str(path.relative_to(balanced.ROOT)): balanced.ref.sha(path)
            for path in files
        },
        "normal4_solver_status": "BOUNDED_UNKNOWN",
        "w24_solver_status": "BOUNDED_UNKNOWN",
        "verified_relations": 0,
        "novel_rank": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    current = collect()
    if args.verify:
        if current != read(MANIFEST):
            raise ValueError("evidence manifest differs from current files")
    else:
        if MANIFEST.exists():
            parser.error("refusing to overwrite manifest")
        MANIFEST.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print("PASS_MANIFEST", current["file_count"])


if __name__ == "__main__":
    main()
