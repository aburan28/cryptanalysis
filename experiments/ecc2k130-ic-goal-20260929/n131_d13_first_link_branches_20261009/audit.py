#!/usr/bin/env python3
"""Independently check exact first-link branches and solver-stage receipts."""

import hashlib
import json
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n131_d13_two_leaf_cubes_20261009/cube0.xcnf"
ROOTS = GOAL / "n131_d13_two_leaf_cubes_20261009/first_link_candidates.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_formula(index, cube):
    formula = HERE / f"branch{index}.xcnf"
    source = SOURCE.read_bytes()
    actual = formula.read_bytes()
    base_header, base_body = source.split(b"\n", 1)
    new_header, new_body = actual.split(b"\n", 1)
    if base_header != b"p cnf 115289 292581" or new_header != b"p cnf 115289 292712":
        raise ValueError("XCNF header mismatch")
    units = [int(value) for value in cube["unit_literals"]]
    if len(units) != 131 or len({abs(v) for v in units}) != 131:
        raise ValueError("wrong pin count")
    if [abs(v) for v in units] != list(range(158, 289)):
        raise ValueError("pins are not precisely first-link coordinate")
    decoded = sum(1 << bit for bit, value in enumerate(units) if value > 0)
    if decoded != cube["partial0_phi_mask"]:
        raise ValueError("pin-to-root mismatch")
    appendix = b"".join(f"{v} 0\n".encode("ascii") for v in units)
    if new_body != base_body + appendix:
        raise ValueError("cube changed a source formula record")
    if sha(formula) != cube["formula_sha256"]:
        raise ValueError("cube hash mismatch")
    return sha(formula)


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    result_path = HERE / "result.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    if result["source_sha256"]["protocol"] != sha(protocol_path):
        raise ValueError("run/protocol mismatch")
    if (result["target_count"] != 1 or result["batch"] is not False or
            result["proposal_id"] != protocol["proposal_id"]):
        raise ValueError("one-target identity mismatch")
    roots = json.loads(ROOTS.read_text())
    if (roots["status"] != "PASS_TWO_COMPLETE_ROOTS_PER_CUBE" or
            protocol["source_sha256"]["roots"] != sha(ROOTS) or
            protocol["source_sha256"]["prior_cube0"] != sha(SOURCE) or
            roots["cubes"][0]["leaf_codes"] != protocol["cubes"][0]["leaf_codes"] or
            [cube["partial0_phi_mask"] for cube in protocol["cubes"]] !=
            roots["cubes"][0]["partial0_phi_masks"]):
        raise ValueError("exact first-link root receipt mismatch")
    formulas = []
    for index, cube in enumerate(protocol["cubes"]):
        if cube["leaf_codes"] != roots["cubes"][0]["leaf_codes"]:
            raise ValueError("branch leaf pair changed")
        formulas.append(check_formula(index, cube))
    checked = []
    for index, row in enumerate(result["attempts"]):
        if (row["branch"] != index or
                row["leaf_codes"] != protocol["cubes"][index]["leaf_codes"] or
                row["partial0_phi_mask"] != protocol["cubes"][index]["partial0_phi_mask"]):
            raise ValueError("attempt order changed")
        process_path = HERE / f"branch{index}.process.json"
        process = json.loads(process_path.read_text())
        try:
            live = psutil.Process(process["pid"])
        except psutil.NoSuchProcess:
            live = None
        if (live is not None and abs(live.create_time() - process["create_time_epoch"]) < .05
                and live.is_running() and live.status() != psutil.STATUS_ZOMBIE):
            raise ValueError("solver process is still live")
        for key, filename in (("formula", f"branch{index}.xcnf"),
                              ("stdout", f"branch{index}.stdout.txt"),
                              ("stderr", f"branch{index}.stderr.txt"),
                              ("process", f"branch{index}.process.json")):
            if row["source_sha256"][key] != sha(HERE / filename):
                raise ValueError(f"attempt {index} {key} hash mismatch")
        if row["wall_seconds"] > protocol["per_cube_wall_cap_seconds"] + 15:
            raise ValueError("unbounded solver interval")
        checked.append({"branch": index, "status": row["status"],
                        "wall_seconds": row["wall_seconds"],
                        "model_lines": row["model_lines"]})
    if result["status"] == "RUNNING":
        raise ValueError("run has no terminal status")
    receipt = {"kind": "n131_d13_exact_first_link_branch_independent_terminal_audit",
               "status": "PASS_ENCODING_AND_TERMINAL",
               "proposal_id": protocol["proposal_id"],
               "candidate_id": None, "run_id": None,
               "formula_sha256": formulas, "attempts": checked,
               "relation_replay_status": ("PENDING_INDEPENDENT_SAGE" if
                    result["status"] == "SAT_MODEL_PENDING_INDEPENDENT_AUDIT"
                    else "NO_MODEL_TO_REPLAY"),
               "source_sha256": {"protocol": sha(protocol_path),
                                 "result": sha(result_path),
                                 "audit_script": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "relation_replay_status": receipt["relation_replay_status"]}))


if __name__ == "__main__":
    main()
