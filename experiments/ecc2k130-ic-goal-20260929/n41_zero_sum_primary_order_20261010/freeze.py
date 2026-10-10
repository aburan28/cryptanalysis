#!/usr/bin/env python3
"""Freeze the primary-order paired solver gate before timing."""

import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_n131_zero_sum_forward_20261009"
JOINT = HERE.parent / "n41_n131_zero_sum_joint_20261009"
CMS = Path("/opt/homebrew/bin/cryptominisat5")

FILES = {
    "freezer": HERE / "freeze.py",
    "builder": HERE / "build.py",
    "runner": HERE / "run.py",
    "auditor": HERE / "sage_audit.py",
    "runtime": HERE / "sage_runtime_info.json",
    "build_receipt": HERE / "build.json",
    "known_model": HERE / "known_model_bits.txt",
    "original_control_formula": SOURCE / "control.xcnf",
    "original_public_formula": SOURCE / "public.xcnf",
    "ordered_control_formula": HERE / "ordered_control.xcnf",
    "ordered_public_formula": HERE / "ordered_public.xcnf",
    "source_protocol": SOURCE / "protocol.json",
    "source_control_build": SOURCE / "control_build.json",
    "source_public_build": SOURCE / "public_build.json",
    "source_chart_model": SOURCE / "chart/model_bits.txt",
    "source_chart_audit": SOURCE / "chart/recovered_audit.json",
    "model_checker": JOINT / "run.py",
    "solver_binary": CMS,
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    build = json.loads((HERE / "build.json").read_text())
    assert build["status"] == "BUILT_EXACT_REINDEX"
    for key in ("source_control_formula", "source_public_formula",
                "source_protocol", "ordered_control_formula",
                "ordered_public_formula", "known_model_bits"):
        alias = ("original_" + key[len("source_"):]
                 if key.startswith("source_") and key.endswith("_formula")
                 else "known_model" if key == "known_model_bits" else key)
        if alias in FILES:
            assert build["sha256"][key] == sha(FILES[alias]), key
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    source_protocol = json.loads((SOURCE / "protocol.json").read_text())
    assert source_protocol["status"] == "FROZEN_FORWARD"
    audit = json.loads((SOURCE / "chart/recovered_audit.json").read_text())
    assert audit["status"] == "VERIFIED_RAW_ROW"
    receipt = {
        "status": "FROZEN_PRIMARY_ORDER",
        "proposal_id": build["proposal_id"], "candidate_id": None,
        "curve_id": source_protocol["curve_id"],
        "target_count": 1, "target": source_protocol["target"],
        "method": "exact variable renaming with eight root bits, 56 mask bits, then four target flags before auxiliaries; CMS VMTF with renumber disabled",
        "paired_run_order": ["ordered_control", "original_control"],
        "public_gate": "ordered_control SAT_MODEL and independent Sage VERIFIED_RAW_ROW",
        "limits": {"ordered_control_seconds": 60,
                   "original_control_seconds": 60,
                   "ordered_public_seconds": 120,
                   "rss_bytes": 4_294_967_296,
                   "workers": 1},
        "files": {key: os.path.relpath(path, HERE)
                  for key, path in FILES.items()},
        "sha256": {key: sha(path) for key, path in FILES.items()},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "files": len(FILES), "sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
