#!/usr/bin/env python3
"""Independently audit frozen lookup formulas and terminal solver receipts."""

import hashlib
import json
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
LOOKUP = HERE.parent / "n131_d13_second_link_lookup_20261009"
FIRST = HERE.parent / "n131_d13_first_link_branches_20261009"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def process_drained(receipt):
    try:
        live = psutil.Process(receipt["pid"])
    except psutil.NoSuchProcess:
        return True
    return (abs(live.create_time() - receipt["create_time_epoch"]) >= .05 or
            not live.is_running() or live.status() == psutil.STATUS_ZOMBIE)


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    result_path = HERE / "result.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    encoding = json.loads((LOOKUP / "encoding_audit.json").read_text())
    prior = json.loads((FIRST / "protocol.json").read_text())
    if (result["status"] == "RUNNING" or
            result["source_sha256"]["protocol"] != sha(protocol_path) or
            result["source_sha256"]["runner"] != sha(HERE / "run.py") or
            result["proposal_id"] != protocol["proposal_id"] or
            result["curve_id"] != prior["curve_id"] or
            result["workload_id"] != prior["workload_id"] or
            result["target_count"] != 1 or
            protocol["source_sha256"]["encoding_audit"] != sha(LOOKUP / "encoding_audit.json") or
            protocol["source_sha256"]["solver"] != sha(SOLVER) or
            encoding["status"] != "PASS_EXACT_APPEND_ONLY_ENCODING"):
        raise ValueError("frozen identity or source mismatch")
    attempts = result["attempts"]
    if len(attempts) not in (1, 2):
        raise ValueError("unexpected branch count")
    checked = []
    for index, row in enumerate(attempts):
        formula = LOOKUP / f"branch{index}_lookup.xcnf"
        stdout = HERE / f"branch{index}.stdout.txt"
        stderr = HERE / f"branch{index}.stderr.txt"
        process_path = HERE / f"branch{index}.process.json"
        proc = json.loads(process_path.read_text())
        expected_command = [str(SOLVER), *protocol["solver_flags"],
                            f"--maxtime={protocol['per_branch_parent_wall_cap_seconds'] - 2}",
                            str(formula)]
        if (row["branch"] != index or proc["command"] != expected_command or
                row["command"] != expected_command or not process_drained(proc) or
                row["source_sha256"] != {"formula": sha(formula),
                                          "stdout": sha(stdout), "stderr": sha(stderr),
                                          "process": sha(process_path)} or
                sha(formula) != protocol["branches"][index]["formula_sha256"] or
                sha(formula) != encoding["branches"][index]["lookup_formula_sha256"] or
                row["wall_seconds"] > protocol["per_branch_parent_wall_cap_seconds"] + 15):
            raise ValueError(f"branch {index} process or input mismatch")
        statuses = []
        model_lines = 0
        with stdout.open("rb") as stream:
            for line in stream:
                if line.startswith(b"s "):
                    statuses.append(line.decode("ascii", "replace").strip())
                if line.startswith(b"v "):
                    model_lines += 1
        if statuses != row["solver_status_lines"] or model_lines != row["model_lines"]:
            raise ValueError(f"branch {index} solver output count changed")
        checked.append({"branch": index, "status": row["status"],
                        "wall_seconds": row["wall_seconds"],
                        "solver_status_lines": statuses, "model_lines": model_lines})
    if abs(result["solver_stage_wall_seconds"] - sum(x["wall_seconds"] for x in attempts)) > 1e-6:
        raise ValueError("solver stage accounting mismatch")
    if result["solver_stage_wall_seconds"] > protocol["combined_solver_stage_cap_seconds"] + 30:
        raise ValueError("combined solver interval exceeded")
    receipt = {"kind": "n131_d13_second_link_public_point_terminal_audit",
               "status": "PASS_ENCODING_AND_TERMINAL",
               "proposal_id": protocol["proposal_id"], "candidate_id": None,
               "run_id": None, "target_count": 1, "attempts": checked,
               "relation_replay_status": ("PENDING_INDEPENDENT_SAGE" if
                   result["status"] == "SAT_MODEL_PENDING_INDEPENDENT_REPLAY" else
                   "NO_MODEL_TO_REPLAY"),
               "source_sha256": {"protocol": sha(protocol_path),
                                 "result": sha(result_path),
                                 "encoding_audit": sha(LOOKUP / "encoding_audit.json"),
                                 "audit_script": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "relation_replay_status": receipt["relation_replay_status"]}))


if __name__ == "__main__":
    main()
