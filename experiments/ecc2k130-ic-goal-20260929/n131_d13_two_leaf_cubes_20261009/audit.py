#!/usr/bin/env python3
"""Independently check the cube encoding and retained solver-stage receipts."""

import hashlib
import json
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n131_d13_public_bridge_projection_20261009/budget1/projected.xcnf"
RAW = (GOAL / "n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/"
       "official_q_phi_fiber_d13_m12_v1.xcnf")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_formula(index, cube):
    formula = HERE / f"cube{index}.xcnf"
    source = SOURCE.read_bytes()
    actual = formula.read_bytes()
    base_header, base_body = source.split(b"\n", 1)
    new_header, new_body = actual.split(b"\n", 1)
    if base_header != b"p cnf 115289 292555" or new_header != b"p cnf 115289 292581":
        raise ValueError("XCNF header mismatch")
    units = [int(value) for value in cube["unit_literals"]]
    if len(units) != 26 or len({abs(v) for v in units}) != 26:
        raise ValueError("wrong pin count")
    if {abs(v) for v in units} != set(range(2, 28)):
        raise ValueError("pins are not precisely two leaf selectors")
    for position, code in enumerate(cube["leaf_codes"]):
        decoded = sum(1 << bit for bit in range(13)
                      if units[position * 13 + bit] > 0)
        if decoded != code:
            raise ValueError("pin-to-code mismatch")
    appendix = b"".join(f"{v} 0\n".encode("ascii") for v in units)
    if new_body != base_body + appendix:
        raise ValueError("cube changed a source formula record")
    if sha(formula) != cube["formula_sha256"]:
        raise ValueError("cube hash mismatch")
    return sha(formula)


def valid_codes():
    forbidden = set()
    with RAW.open("rt", encoding="ascii") as stream:
        for line in stream:
            if line.startswith(("p", "c", "x")):
                continue
            fields = [int(v) for v in line.split()]
            if len(fields) == 14 and fields[-1] == 0 and {
                    abs(v) for v in fields[:-1]} == set(range(2, 15)):
                forbidden.add(sum(1 << (abs(v) - 2) for v in fields[:-1]
                                  if v < 0))
    if len(forbidden) != 4058:
        raise ValueError("valid-selector source mismatch")
    return set(range(8192)) - forbidden


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
    allowed = valid_codes()
    formulas = []
    for index, cube in enumerate(protocol["cubes"]):
        if any(code not in allowed for code in cube["leaf_codes"]):
            raise ValueError("invalid pinned leaf code")
        formulas.append(check_formula(index, cube))
    checked = []
    for index, row in enumerate(result["attempts"]):
        if row["cube"] != index or row["leaf_codes"] != protocol["cubes"][index]["leaf_codes"]:
            raise ValueError("attempt order changed")
        process_path = HERE / f"cube{index}.process.json"
        process = json.loads(process_path.read_text())
        try:
            live = psutil.Process(process["pid"])
        except psutil.NoSuchProcess:
            live = None
        if (live is not None and abs(live.create_time() - process["create_time_epoch"]) < .05
                and live.is_running() and live.status() != psutil.STATUS_ZOMBIE):
            raise ValueError("solver process is still live")
        for key, filename in (("formula", f"cube{index}.xcnf"),
                              ("stdout", f"cube{index}.stdout.txt"),
                              ("stderr", f"cube{index}.stderr.txt"),
                              ("process", f"cube{index}.process.json")):
            if row["source_sha256"][key] != sha(HERE / filename):
                raise ValueError(f"attempt {index} {key} hash mismatch")
        if row["wall_seconds"] > protocol["per_cube_wall_cap_seconds"] + 15:
            raise ValueError("unbounded solver interval")
        checked.append({"cube": index, "status": row["status"],
                        "wall_seconds": row["wall_seconds"],
                        "model_lines": row["model_lines"]})
    if result["status"] == "RUNNING":
        raise ValueError("run has no terminal status")
    receipt = {"kind": "n131_d13_two_leaf_cube_independent_terminal_audit",
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
