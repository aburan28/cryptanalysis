#!/usr/bin/env python3
"""Hash the exact source, formula, control and solver evidence of this gate."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import field as ref


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "runs/R1/manifest.json"
PREREGISTER_COMMIT = "a260e763e1efe7fbb4b6982c1a3f3c1f76e0baf3"


def files() -> dict:
    included = {}
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT:
            continue
        if "__pycache__" in path.parts or path.name == ".DS_Store":
            continue
        included[str(path.relative_to(HERE))] = {
            "sha256": ref.sha(path), "bytes": path.stat().st_size}
    return included


def archived_formula_sha(path: Path) -> str:
    """Check zero-time gzip and hash the original XCNF bytes."""
    archive = path.read_bytes()
    if archive[:8] != b"\x1f\x8b\x08\x00\x00\x00\x00\x00":
        raise ValueError("XCNF archive lacks a deterministic gzip header")
    raw = gzip.decompress(archive)
    return hashlib.sha256(raw).hexdigest()


def validated_status() -> dict:
    run = HERE / "runs/R1"
    sage = json.loads((run / "sage_verification.json").read_text())
    controls = json.loads((run / "cnf_controls/receipt.json").read_text())
    torsion = json.loads((run / "torsion_lifts.json").read_text())
    if (sage["status"] != "PASS_SAGE_POINT_AND_BOOLEAN_REPLAY"
            or controls["status"] != "PASS_PINNED_POSITIVE_AND_NEGATIVE"
            or torsion["status"] != "PASS_FOUR_EXACT_RAW_TARGET_LIFTS"):
        raise ValueError("construction or torsion evidence did not pass")
    for name in ("w24_leaf", "normal4_leaf"):
        formula = json.loads((run / (name + ".json")).read_text())
        if formula["formula_sha256"] != archived_formula_sha(
                run / (name + ".xcnf.gz")):
            raise ValueError("archived leaf formula changed")
    for row in controls["results"]:
        stem = row["policy"] + ("_negative" if row["changed_x_bit_0"]
                                else "_positive")
        if row["formula_sha256"] != archived_formula_sha(
                run / "cnf_controls" / (stem + ".xcnf.gz")):
            raise ValueError("archived pinned control changed")
    policies = {}
    for policy, stem in (("w24_source", "w24_m6_q0"),
                         ("normal4_source", "normal4_m6_q0")):
        formula = json.loads((run / (stem + ".json")).read_text())
        pilot = json.loads((run / (stem + "_pilot.json")).read_text())
        audit = json.loads((run / (stem + "_audit.json")).read_text())
        if (formula["formula_sha256"] != archived_formula_sha(
                run / (stem + ".xcnf.gz"))
                or pilot["formula_sha256"] != formula["formula_sha256"]
                or pilot["policy"] != policy or audit["policy"] != policy
                or pilot["status"] != audit["status"]
                or not audit["solver_search_began"]):
            raise ValueError("ordinary-query pilot binding failed")
        policies[policy] = pilot["status"]
    return policies


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    record = {
        "schema": "ecc2k130-equalb-m6-leaf-circuit-manifest-v1",
        "candidate_id": None,
        "source_curve_id": "EC1N131Ckb1h136f03e58c98",
        "preregister_commit": PREREGISTER_COMMIT,
        "actual_usable_points_B": 11743888,
        "ordinary_query_index": 0,
        "policy_statuses": validated_status(),
        "files": files(),
    }
    if args.verify:
        if json.loads(OUTPUT.read_text()) != record:
            raise ValueError("manifest content or file hashes changed")
        print("PASS_MANIFEST", len(record["files"]))
    else:
        if OUTPUT.exists():
            parser.error("refusing to overwrite manifest")
        OUTPUT.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        print("WROTE_MANIFEST", len(record["files"]))


if __name__ == "__main__":
    main()
