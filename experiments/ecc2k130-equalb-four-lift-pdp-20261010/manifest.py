#!/usr/bin/env python3
"""Bind source, controls, archived formulas, and bounded solver receipts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import archive_formulas
import build_four_lift as gate


RUN = gate.HERE / "runs/R1"
MANIFEST = RUN / "manifest.json"
PARENT = gate.PARENT / "runs/R1"
PARENT_INPUTS = (
    gate.PARENT / "build_formula.py",
    gate.PARENT / "field.py",
    gate.PARENT / "run_pilot.py",
    PARENT / "sage_verification.json",
    PARENT / "cnf_controls/receipt.json",
    PARENT / "torsion_lifts.json",
    PARENT / "w24_m6_q0_pilot.json",
    PARENT / "normal4_m6_q0_pilot.json",
    gate.PUBLIC,
    gate.ref.EQUAL / "CONFIG.json",
    gate.ref.EQUAL / "runs/R1/base_prefixes.json",
)


def read(path: Path):
    return json.loads(path.read_text())


def collect() -> dict:
    parent_sage = read(PARENT / "sage_verification.json")
    parent_cnf = read(PARENT / "cnf_controls/receipt.json")
    runtime = read(RUN / "runtime-info.json")
    sage = read(RUN / "sage_lifts.json")
    mux = read(RUN / "mux_controls/receipt.json")
    columns = read(RUN / "columns.json")
    if (parent_sage["status"] != "PASS_SAGE_POINT_AND_BOOLEAN_REPLAY"
            or parent_cnf["status"] != "PASS_PINNED_POSITIVE_AND_NEGATIVE"
            or runtime["status"] != "verified"
            or sage["status"] != "PASS_INDEPENDENT_FOUR_RAW_LIFTS"
            or mux["status"]
            != "PASS_FOUR_POSITIVE_FOUR_NEGATIVE_NATIVE_XOR_CONTROLS"
            or len(mux["cases"]) != 8
            or columns["status"]
            != "PASS_EXACT_PREFIX_RESTRICTION_OF_VERIFIED_ORBIT_MAP"
            or columns["source_w24_potential_columns"] != 5869878
            or columns["source_normal4_potential_columns"] != 44824):
        raise ValueError("prerequisite control or column receipt changed")
    for policy, name in (("w24_source", "w24"),
                         ("normal4_source", "normal4")):
        stem = name + "_m6_four_lift"
        built = read(RUN / (stem + ".json"))
        archive = read(RUN / (stem + ".archive.json"))
        pilot = read(RUN / (stem + "_pilot.json"))
        audit = read(RUN / (stem + "_audit.json"))
        formula_path = RUN / (stem + ".xcnf.gz")
        raw_sha, raw_bytes = archive_formulas.decompressed_sha(formula_path)
        if (built["policy"] != policy
                or built["actual_usable_points_B"] != 11743888
                or built["target_x_choices"] != [str(x) for x in gate.target_lifts()]
                or built["builder_sha256"] != gate.ref.sha(
                    gate.HERE / "build_four_lift.py")
                or raw_sha != built["formula_sha256"]
                or raw_sha != archive["raw_formula_sha256"]
                or raw_bytes != archive["raw_formula_bytes"]
                or gate.ref.sha(formula_path) != archive["archive_sha256"]
                or pilot["policy"] != policy
                or pilot["status"] != "BOUNDED_UNKNOWN"
                or pilot["verified_relation"]
                or pilot["novel_rank"] is not None
                or audit["status"] != "PASS_TRANSCRIPT_AND_SOURCE_BINDING"
                or audit["solver_status"] != pilot["status"]
                or audit["conflicts"] <= 0 or audit["restarts"] <= 0
                or audit["pilot_sha256"] != gate.ref.sha(
                    RUN / (stem + "_pilot.json"))):
            raise ValueError("formula, bounded run, or audit changed: " + name)
    local = [path for path in gate.HERE.rglob("*")
             if path.is_file() and path != MANIFEST
             and "__pycache__" not in path.parts]
    files = sorted(local + list(PARENT_INPUTS), key=lambda path:
                   str(path.relative_to(gate.ROOT)))
    return {
        "schema": "ecc2k130-equalb-four-lift-evidence-manifest-v1",
        "status": "PASS_SOURCE_AND_RUN_EVIDENCE",
        "candidate_id": None,
        "file_count": len(files),
        "files_sha256": {str(path.relative_to(gate.ROOT)): gate.ref.sha(path)
                         for path in files},
        "w24_solver_status": "BOUNDED_UNKNOWN",
        "normal4_solver_status": "BOUNDED_UNKNOWN",
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
