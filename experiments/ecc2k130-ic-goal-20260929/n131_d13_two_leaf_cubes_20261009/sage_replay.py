#!/usr/bin/env sage -python
"""Independently replay a SAT cube model on the exact public N131 curve."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_d13_public_bridge_projection_20261009"
sys.path.insert(0, str(SOURCE))
import audit_sat_relation as base

base.RUN = HERE
base.PROJECTION = SOURCE / "budget1"
base.BRIDGE_FORMULA = SOURCE / "bridge_cnf/bridge_cnf.xcnf"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    output = HERE / "sage_replay.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    terminal = json.loads((HERE / "audit.json").read_text())
    if (result["status"] != "SAT_MODEL_PENDING_INDEPENDENT_AUDIT" or
            terminal["status"] != "PASS_ENCODING_AND_TERMINAL" or
            terminal["relation_replay_status"] != "PENDING_INDEPENDENT_SAGE" or
            result["proposal_id"] != protocol["proposal_id"]):
        raise ValueError("no audited SAT model is available for Sage replay")
    attempts = [row for row in result["attempts"] if
                row["status"] == "SAT_MODEL_PENDING_INDEPENDENT_AUDIT"]
    if len(attempts) != 1:
        raise ValueError("expected exactly one SAT cube model")
    index = attempts[0]["cube"]
    stdout = HERE / f"cube{index}.stdout.txt"
    formula = HERE / f"cube{index}.xcnf"
    projected_check = base.xcnf.verify(formula, stdout)
    unpinned_check = base.xcnf.verify(base.PROJECTION / "projected.xcnf", stdout)
    assignment = base.xcnf.model_from_stdout(stdout, projected_check["variables"])
    projection = json.loads((base.PROJECTION / "result.json").read_text())
    mapping = json.loads((base.PROJECTION / "variable_map.json").read_text())
    full = base.lift(assignment, mapping, base.PROJECTION / "lift_rows.jsonl",
                     projection["original_variables"])
    lifted = HERE / f"lifted_model_cube{index}.stdout.txt"
    base.save_full_model(lifted, full)
    bridge_check = base.xcnf.verify(base.BRIDGE_FORMULA, lifted)
    original_check = base.xcnf.verify(base.ORIGINAL, lifted)
    literals = [variable if full[variable] else -variable
                for variable in range(1, len(full))]
    row_result, checked, rebuilt_sha = base.replay_relation(literals)
    if len(checked) != len(row_result["decoded_rows"]) or not checked:
        raise ValueError("independent Sage replay did not cover decoded rows")
    record = {
        "kind": "n131_d13_two_leaf_cube_public_q_independent_sage_relation_replay",
        "status": "PASS_VERIFIED_RELATION", "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None, "target_count": 1,
        "cube": index, "leaf_codes": attempts[0]["leaf_codes"],
        "projected_cube_model_check": projected_check,
        "unpinned_projected_model_check": unpinned_check,
        "bridge_model_check": bridge_check,
        "original_model_check": original_check,
        "decoded_rows": row_result["decoded_rows"],
        "independent_sage_row_checks": checked,
        "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                          "result": sha(HERE / "result.json"),
                          "terminal_audit": sha(HERE / "audit.json"),
                          "cube_formula": sha(formula), "solver_stdout": sha(stdout),
                          "lifted_model": sha(lifted),
                          "original_formula": sha(base.ORIGINAL),
                          "rebuilt_original_formula": rebuilt_sha,
                          "replay_script": sha(Path(__file__))},
    }
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": record["status"], "verified_rows": len(checked)}))


if __name__ == "__main__":
    main()
