#!/usr/bin/env python3
"""Verify and bind the selector gate's source, inputs, controls, and runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import archive_formulas as archive
import build_selector as circuit


RUN = circuit.HERE / "runs/R1"
MANIFEST = RUN / "manifest.json"
PARENTS = (
    circuit.BALANCED / "runs/R1/manifest.json",
    circuit.BALANCED / "runs/R1/normal4_m6_four_lift.json",
    circuit.BALANCED / "build_balanced.py",
    circuit.gate.PARENT / "runs/R1/manifest.json",
    circuit.gate.PARENT / "runs/R1/sage_verification.json",
    circuit.gate.PARENT / "build_formula.py",
    circuit.gate.PARENT / "field.py",
    circuit.gate.LIFTS,
    circuit.gate.PUBLIC,
    circuit.ref.EQUAL / "CONFIG.json",
    circuit.ref.EQUAL / "runs/R1/base_prefixes.json",
    circuit.ref.NORMAL / "CONFIG.json",
    circuit.ref.PARENT,
    *(circuit.source.CODEGEN / name for name in ("build.py", "ir.py", "cnf.py")),
)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def collect() -> dict:
    runtime = read(RUN / "runtime-info.json")
    sage = read(RUN / "sage_selector.json")
    controls = read(RUN / "cnf_controls/receipt.json")
    archives = read(RUN / "archives.json")
    prior = read(circuit.BALANCED / "runs/R1/normal4_m6_four_lift.json")
    prior_manifest = read(circuit.BALANCED / "runs/R1/manifest.json")
    failure = read(RUN / "counter_probe_attempt0.json")
    if (runtime["status"] != "verified"
            or sage["status"]
            != "PASS_128_POINTS_SUPPORT_BIJECTION_AND_BALANCED_TREE"
            or sage["point_controls"] != 128
            or sage["runtime_info_sha256"]
            != circuit.ref.sha(RUN / "runtime-info.json")
            or sage["high_position_control"]["mask"]
            != str((1 << 0) | (1 << 1) | (1 << 2) | (1 << 130))
            or controls["status"]
            != "PASS_PINNED_ELEVEN_NATIVE_XOR_CONTROLS"
            or len(controls["results"]) != 11
            or controls["sage_selector_sha256"]
            != circuit.ref.sha(RUN / "sage_selector.json")
            or archives["status"] != "PASS_DETERMINISTIC_ARCHIVE_REPLAY"
            or archives["archive_count"] != 15
            or archives["archiver_sha256"]
            != circuit.ref.sha(circuit.HERE / "archive_formulas.py")
            or prior_manifest["status"]
            != "PASS_SOURCE_AND_BOUNDED_RUN_EVIDENCE"
            or prior["stats"] != {"vars": 536683, "clauses": 599988,
                                  "xors": 300963}
            or failure["status"] != "PRODUCER_FAILURE"
            or failure["solver_search_started"]
            or failure["stdout_sha256"] != circuit.ref.sha(
                RUN / "counter_probe_attempt0.stdout.txt")
            or failure["stderr_sha256"] != circuit.ref.sha(
                RUN / "counter_probe_attempt0.stderr.txt")):
        raise ValueError("selector prerequisites or preflight failure changed")
    expected = {
        "counter_leaf": (38364, 33066, 26905),
        "support_index_leaf": (38390, 33749, 26953),
        "counter_m6_four_lift": (443029, 418074, 300963),
        "support_index_m6_four_lift": (443185, 422172, 301251),
    }
    archived = {row["path"]: row for row in archives["archives"]}
    for name, (variables, clauses, xors) in expected.items():
        built = read(RUN / (name + ".json"))
        compressed = RUN / (name + ".xcnf.gz")
        stored = archived[str(compressed.relative_to(circuit.ROOT))]
        replay_sha, replay_bytes = archive.decompressed_sha(compressed)
        if (built["schema"] != "ecc2k130-normal4-selector-xcnf-v1"
                or built["status"] != "FORMULA_BUILT"
                or built["builder_sha256"]
                != circuit.ref.sha(circuit.HERE / "build_selector.py")
                or built["stats"] != {"vars": variables,
                                      "clauses": clauses, "xors": xors}
                or built["formula_sha256"] != replay_sha
                or stored["raw_formula_sha256"] != replay_sha
                or stored["raw_formula_bytes"] != replay_bytes
                or stored["archive_sha256"] != circuit.ref.sha(compressed)):
            raise ValueError("selector formula or archive changed: " + name)
    for policy in circuit.POLICIES:
        pilot_path = RUN / (policy + "_pilot.json")
        pilot = read(pilot_path)
        audit = read(RUN / (policy + "_audit.json"))
        built = read(RUN / (policy + "_m6_four_lift.json"))
        if (pilot["policy"] != policy
                or pilot["status"] != "BOUNDED_UNKNOWN"
                or pilot["guard"] != "WALL_CAP"
                or pilot["producer_error"] is not None
                or pilot["live_restart_rows"] <= 0
                or pilot["formula_sha256"] != built["formula_sha256"]
                or pilot["verified_relation"]
                or pilot["novel_rank"] is not None
                or audit["status"]
                != "PASS_TRANSCRIPT_AND_FORMULA_BINDING"
                or audit["solver_status"] != pilot["status"]
                or audit["pilot_sha256"] != circuit.ref.sha(pilot_path)
                or audit["live_restart_rows"] != pilot["live_restart_rows"]):
            raise ValueError("ordinary pilot or independent audit changed")
    local = [path for path in circuit.HERE.rglob("*")
             if path.is_file() and path != MANIFEST
             and "__pycache__" not in path.parts]
    files = sorted(local + list(PARENTS),
                   key=lambda path: str(path.relative_to(circuit.ROOT)))
    return {
        "schema": "ecc2k130-normal4-selector-evidence-manifest-v1",
        "status": "PASS_SOURCE_INPUT_AND_CENSORED_RUN_EVIDENCE",
        "candidate_id": None,
        "file_count": len(files),
        "files_sha256": {str(path.relative_to(circuit.ROOT)): circuit.ref.sha(path)
                         for path in files},
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
