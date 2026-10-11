"""Recreate the positive model fixture and run the independent group lift."""

import json
from pathlib import Path

import replay

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main():
    known = json.loads((ROOT / "rotated_fouratom_public_lift_correction_20261010" /
                        "lift_result.json").read_text())
    audit = json.loads((ROOT / "n41_quartic_joint_public_20261010" /
                        "audit_result.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    assert control["status"] == "PASS_FULL_N41_PUBLIC_WITNESS_ASSIGNMENT"
    model = {"target": audit["target"], "masks": known["masks"],
             "block_reciprocals": [row["z_h_reciprocal_x"]
                                   for row in known["four_atom_blocks"]],
             "branch_w": [row["existential_branch_witness"] for row in audit["blocks"]],
             "intermediate_reciprocal": control["joined_reciprocal"],
             "raw_lift_index": known["raw_preimage_index"],
             "formula_sha256": "positive_assignment_control"}
    (HERE / "control_decoded.json").write_text(json.dumps(model, sort_keys=True, indent=2) + "\n")
    replay.MODEL = HERE / "control_decoded.json"
    replay.main()
    (HERE / "replay_result.json").replace(HERE / "control_replay_result.json")


if __name__ == "__main__":
    main()
