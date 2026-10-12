#!/usr/bin/env python3
"""Freeze exact Q1484 inputs, source, runtime and archive identity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent
PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


DEPENDENCIES = (
    "ecc2k130/codegen/curves.py",
    "ecc2k130/codegen/field.py",
    "experiments/compact-s3-m4-20261003/enumerate_n83_weight5_full.py",
    "experiments/compact-s3-m4-20261003/enumerate_q1413_projected_x.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
    "experiments/compact-s3-m4-20261003/q1481_window_orbit_base/enumerate_base.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
)
REFERENCES = (
    "experiments/compact-s3-m4-20261003/protocol.json",
    "experiments/compact-s3-m4-20261003/q1413_projected_x_protocol.json",
    "experiments/compact-s3-m4-20261003/runs/n131_q1413_projected_x_w6.json",
    "experiments/compact-s3-m4-20261003/q1481_window_orbit_base/design_protocol.json",
    "experiments/compact-s3-m4-20261003/q1481_window_orbit_base/protocol.json",
)
SOURCES = ("enumerate_n131.py", "verify_archive.py", "self_test.py",
           "freeze_protocol.py")


def make_record() -> dict:
    design_path = HERE / "design_protocol.json"
    design = json.loads(design_path.read_text())
    parent = json.loads((PARENT / "protocol.json").read_text())[
        "degree_131_design"]
    q1481 = json.loads((PARENT /
                       "q1481_window_orbit_base/design_protocol.json").read_text())
    q1413 = json.loads((PARENT /
                       "runs/n131_q1413_projected_x_w6.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    preflight = json.loads((HERE / "preflight.json").read_text())
    assert runtime["status"] == "verified"
    assert preflight["status"] == "PASS"
    assert preflight["proposal_id"] == "Q1484"
    assert preflight["enumerator_source_sha256"] == sha(
        HERE / "enumerate_n131.py")
    assert preflight["archive_auditor_source_sha256"] == sha(
        HERE / "verify_archive.py")
    assert preflight["self_test_source_sha256"] == sha(
        HERE / "self_test.py")
    assert design["proposal_id"] == "Q1484"
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    assert design["curve_id"] == parent["curve"]["curve_id"] == (
        q1481["instances"]["131"]["curve_id"]) == q1413["curve_id"]
    assert design["nominal_window_dimension_d"] == (
        q1481["instances"]["131"]["nominal_window_dimension_d"]) == 27
    assert design["raw_x_orbits_formula"] == 1 << 26
    assert parent["curve"]["cofactor"] == q1413["cofactor"] == 4
    return {
        "kind": "q1484_frozen_n131_window_base_enumeration",
        "proposal_id": "Q1484", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "curve_id": design["curve_id"],
        "field": parent["field"], "curve": parent["curve"],
        "cofactor": parent["curve"]["cofactor"],
        "subgroup_order": parent["curve"]["subgroup_order"],
        "nominal_window_dimension_d": 27,
        "raw_x_orbits_formula": 1 << 26,
        "archive_encoding": design["archive_encoding"],
        "actual_usable_B": None, "folded_K": None,
        "enumerated_set_sha256": None,
        "complete_n131_log2_work": None,
        "limits": design["limits"],
        "design_sha256": sha(design_path),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "preflight_sha256": sha(HERE / "preflight.json"),
        "source_sha256": {name: sha(HERE / name) for name in SOURCES},
        "dependency_sha256": {path: sha(ROOT / path)
                              for path in DEPENDENCIES},
        "reference_sha256": {path: sha(ROOT / path)
                             for path in REFERENCES},
        "run_order": ["Q1484R1 exact N131 enumeration",
                      "independent archive and group-law audit"],
        "claim_scope": design["claim_scope"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = make_record()
    if args.check or PROTOCOL.exists():
        assert json.loads(PROTOCOL.read_text()) == expected
        print("Q1484 protocol freeze PASS", flush=True)
    else:
        PROTOCOL.write_text(json.dumps(expected, indent=2,
                                       sort_keys=True) + "\n")
        print("Q1484 protocol frozen", flush=True)


if __name__ == "__main__":
    main()
