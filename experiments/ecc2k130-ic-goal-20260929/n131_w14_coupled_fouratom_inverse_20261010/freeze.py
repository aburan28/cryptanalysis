#!/usr/bin/env python3
"""Freeze the local four-atom oracle source and bounded control panel."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
W14 = GOAL / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
W6 = GOAL / "n41_n131_diagonal_atom_20261010/screen.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    inputs = json.loads((HERE / "inputs.json").read_text())
    terms = json.loads((HERE / "resultant_terms.json").read_text())
    assert runtime["status"] == "verified"
    assert inputs["status"] == "PASS_FROZEN_FOUR_ATOM_OUTPUT_CONTROLS"
    assert terms["status"] == "PASS_UNIVERSAL_SAME_SEED_FOUR_ATOM_RESULTANT"
    assert inputs["source_sha256"] == {
        "script": sha(HERE / "prepare.py"), "w6_screen": sha(W6),
        "w14_support": sha(W14), "resultant_terms": sha(HERE / "resultant_terms.json"),
        "runtime": sha(HERE / "sage_runtime_info.json")}
    sources = {"script": HERE / "oracle.py", "terms": HERE / "resultant_terms.json",
               "inputs": HERE / "inputs.json", "runtime": HERE / "sage_runtime_info.json"}
    record = {
        "status": "FROZEN_BEFORE_FOUR_ATOM_ORACLE_PANEL",
        "kind": "same_seed_four_diagonal_atom_output_inverse",
        "candidate_id": None, "target_count": 0,
        "curve_ids": [inputs["panels"]["41"]["curve_id"],
                      inputs["panels"]["131"]["curve_id"]],
        "input_law": "one constructed four-atom output and one independent trace-zero field control in each field; source masks and seed sum fixed before each query",
        "workers": 1, "cap_seconds_per_case": 120,
        "rss_cap_bytes": 4 * 1024**3,
        "run_order": ["n41_positive", "n41_trace_zero_control",
                      "n131_positive", "n131_trace_zero_control"],
        "promotion_gate": "both N41 cases must complete with exact positive product recovery and trace-zero algebraic rejection before N131 cases",
        "source_sha256": {key: sha(path) for key, path in sources.items()},
        "identity_sha256": {"freeze": sha(Path(__file__)),
                            "derive": sha(HERE / "derive.py"),
                            "prepare": sha(HERE / "prepare.py"),
                            "w6_screen": sha(W6), "w14_support": sha(W14)},
    }
    with (HERE / "protocol.json").open("x") as out:
        json.dump(record, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": record["status"], "cap_seconds_per_case": 120}))


if __name__ == "__main__":
    main()
