#!/usr/bin/env python3
"""Freeze the affine wavefront pair evaluation policy before fresh inputs."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BLOCK_SIZE = 128


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    width_path = ROOT / "joint-pair-width-design.json"
    inputs_path = ROOT / "joint-pair-width-inputs/inputs.json"
    panel_path = ROOT / "joint-pair-width-native-panel.json"
    width = json.loads(width_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    panel = json.loads(panel_path.read_text())
    if width.get("status") != "frozen_training_design" or \
            inputs.get("design_sha256") != sha256(width_path) or \
            panel.get("inputs_sha256") != sha256(inputs_path) or \
            panel.get("status") != "pass" or len(panel.get("rows", [])) != 40:
        raise ValueError("pair-width training custody or verification changed")
    rows = {(row["case_id"], row["mode"]): row for row in panel["rows"]}
    if len(rows) != 40 or any(not row.get("gate_pass") for row in rows.values()):
        raise ValueError("expected 40 distinct verified training arms")
    records = []
    for row in width["records"]:
        curve = row["curve"]
        cases = [case for case in inputs["cases"] if case["curve"]["name"] == curve]
        if len(cases) != 4 or any(case["count"] != 4096 for case in cases):
            raise ValueError("expected four 4096-scalar cases per curve")
        triple = [rows[(case["id"], "joint-pair-top-triple-pos")]["fields"] for case in cases]
        double = [rows[(case["id"], "joint-pair-top-double-pos")]["fields"] for case in cases]
        adds = sum(int(result["adds"]) for result in triple)
        if adds != sum(int(result["adds"]) for result in double):
            raise ValueError("training pair additions differ across point widths")
        pair_positions = 2 if curve == "glv-j0-32" else 4
        records.append({
            "curve": curve,
            "pair_positions": pair_positions,
            "training_scalars": 4 * 4096,
            "training_adds": adds,
            "training_rotations_double": sum(int(result["rotations"]) for result in double),
            "training_unit_adds_triple": sum(int(result["unit_adds"]) for result in triple),
            "training_serial_output_inversions": sum(
                int(result["output_inversions"]) for result in triple),
            "wave_output_inversions_upper_bound_per_case":
                (pair_positions - 1) * (4096 // BLOCK_SIZE),
        })
    design = {
        "schema": 1,
        "status": "frozen_training_design",
        "scope": "variable-time fixed-base public-scalar batches on two exact j=0 curves",
        "method": "evaluate equal pair positions across 128 independent scalars with affine batch addition; copy the first nonzero terms and share one inversion among lanes needing each later addition",
        "block_size": BLOCK_SIZE,
        "candidate_modes": ["joint-pair-top-triple-wave128", "joint-pair-top-double-wave128"],
        "reference_modes": ["joint-pair-top-triple-pos", "joint-pair-top-double-pos"],
        "table_rule": "reuse the proven bounded pair orbit set and existing 24-byte or 16-byte point records",
        "measurement_gate": "new disjoint correctness panel first; CPU wall ratio only with a host-level isolation receipt",
        "prior_art_scope": "batched field inversion and affine wavefront addition are known; this experiment evaluates their integration with the bounded Eisenstein pair atlas, without claiming academic priority",
        "width_design_sha256": sha256(width_path),
        "training_inputs_sha256": sha256(inputs_path),
        "training_panel_sha256": sha256(panel_path),
        "source_sha256": sha256(Path(__file__)),
        "records": records,
    }
    output = ROOT / "joint-pair-wave-design.json"
    content = (json.dumps(design, sort_keys=True, indent=2) + "\n").encode()
    if output.exists() and output.read_bytes() != content:
        raise ValueError("frozen wavefront design changed")
    output.write_bytes(content)
    print(json.dumps({"design_sha256": sha256(output), "records": records}, sort_keys=True))


if __name__ == "__main__":
    main()
