#!/usr/bin/env sage -python
"""Replay one lookup SAT model against the original N131 formula and curve."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "n131_d13_public_bridge_projection_20261009"
LOOKUP = ROOT / "n131_d13_second_link_lookup_20261009"
FIRST = ROOT / "n131_d13_first_link_branches_20261009"
sys.path.insert(0, str(SOURCE))
import audit_sat_model_and_relation as base

base.RUN = HERE
base.PROJECTION = SOURCE / "budget1"
base.BRIDGE_FORMULA = SOURCE / "bridge_cnf/bridge_cnf.xcnf"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    output = HERE / "sage_replay.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    result_path = HERE / "result.json"
    terminal_path = HERE / "audit.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    terminal = json.loads(terminal_path.read_text())
    if (result["status"] != "SAT_MODEL_PENDING_INDEPENDENT_REPLAY" or
            terminal["status"] != "PASS_ENCODING_AND_TERMINAL" or
            terminal["relation_replay_status"] != "PENDING_INDEPENDENT_SAGE" or
            result["source_sha256"]["protocol"] != sha(protocol_path)):
        raise ValueError("no audited SAT lookup model is available")
    attempts = [row for row in result["attempts"] if
                row["status"] == "SAT_MODEL_PENDING_INDEPENDENT_REPLAY"]
    if len(attempts) != 1:
        raise ValueError("expected one SAT branch")
    index = attempts[0]["branch"]
    stdout = HERE / f"branch{index}.stdout.txt"
    formula = LOOKUP / f"branch{index}_lookup.xcnf"
    lookup_check = base.xcnf.verify(formula, stdout)
    lookup_model = base.xcnf.model_from_stdout(stdout, lookup_check["variables"])
    source_formula = FIRST / f"branch{index}.xcnf"
    source_variables, _ = base.xcnf.header(source_formula)
    source_model = HERE / f"source_model_branch{index}.stdout.txt"
    base.save_full_model(source_model, lookup_model[:source_variables + 1])
    source_check = base.xcnf.verify(source_formula, source_model)
    projected_check = base.xcnf.verify(base.PROJECTION / "projected.xcnf", source_model)
    assignment = base.xcnf.model_from_stdout(source_model, projected_check["variables"])
    projection = json.loads((base.PROJECTION / "result.json").read_text())
    mapping = json.loads((base.PROJECTION / "variable_map.json").read_text())
    full = base.lift(assignment, mapping, base.PROJECTION / "lift_rows.jsonl",
                     projection["original_variables"])
    lifted = HERE / f"lifted_model_branch{index}.stdout.txt"
    base.save_full_model(lifted, full)
    bridge_check = base.xcnf.verify(base.BRIDGE_FORMULA, lifted)
    original_check = base.xcnf.verify(base.ORIGINAL, lifted)
    literals = [variable if full[variable] else -variable
                for variable in range(1, len(full))]
    row_result, checked, rebuilt_sha = base.replay_relation(literals)
    if not checked or len(checked) != len(row_result["decoded_rows"]):
        raise ValueError("independent Sage row check incomplete")
    receipt = {
        "kind": "n131_d13_second_link_public_point_independent_sage_replay",
        "status": "PASS_VERIFIED_RELATION", "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None, "target_count": 1,
        "branch": index, "lookup_model_check": lookup_check,
        "source_branch_model_check": source_check,
        "projected_model_check": projected_check,
        "bridge_model_check": bridge_check,
        "original_model_check": original_check,
        "decoded_rows": row_result["decoded_rows"],
        "independent_sage_row_checks": checked,
        "source_sha256": {"protocol": sha(protocol_path), "result": sha(result_path),
                          "terminal_audit": sha(terminal_path),
                          "lookup_formula": sha(formula), "solver_stdout": sha(stdout),
                          "source_model": sha(source_model), "lifted_model": sha(lifted),
                          "original_formula": sha(base.ORIGINAL),
                          "rebuilt_original_formula": rebuilt_sha,
                          "replay_script": sha(Path(__file__))},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "verified_rows": len(checked)}))


if __name__ == "__main__":
    main()
