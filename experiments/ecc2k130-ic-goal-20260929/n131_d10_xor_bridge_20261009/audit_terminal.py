#!/usr/bin/env python3
"""Independently reconcile the N131 d10 CNF-bridge SAT-stage attempt."""

import hashlib
import json
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
RUN = HERE / "ordinary_precompute_R1"
PROTOCOL = HERE / "protocol.json"
FORMULA = HERE / "bridge_cnf/bridge_cnf.xcnf"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RUNNER = HERE / "run_bridge_query.py"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    output = RUN / "independent_terminal_audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads(PROTOCOL.read_text())
    result_path = RUN / "result.json"
    result = json.loads(result_path.read_text())
    started = json.loads((RUN / "started.json").read_text())
    process = json.loads((RUN / "solver_process.json").read_text())
    stdout = RUN / "cryptominisat.stdout.txt"
    stderr = RUN / "cryptominisat.stderr.txt"
    sources = result["source_sha256"]
    for key, path in (("protocol", PROTOCOL), ("formula", FORMULA),
                      ("runtime", RUN / "sage_runtime_info.json"),
                      ("stdout", stdout), ("stderr", stderr),
                      ("runner", RUNNER), ("solver", SOLVER)):
        if sources[key] != sha(path):
            raise ValueError("result hash differs for " + key)
    if (started["protocol_sha256"] != sha(PROTOCOL) or
            started["runtime_info_sha256"] != sha(RUN / "sage_runtime_info.json") or
            started["proposal_id"] != protocol["proposal_id"] or
            result["proposal_id"] != protocol["proposal_id"] or
            result["curve_id"] != protocol["curve_id"] or
            result["workload_id"] != protocol["workload_id"] or
            started["solver_command"] != process["command"] or
            process["command"] != [str(SOLVER),
                                   *protocol["run_policy"]["solver_flags"],
                                   str(FORMULA)] or
            result["target_count"] != 1 or result["batch"] is not False):
        raise ValueError("run identity or command differs from protocol")
    try:
        live = psutil.Process(process["pid"])
        if (abs(live.create_time() - process["create_time_epoch"]) < .05 and
                live.is_running() and live.status() != psutil.STATUS_ZOMBIE):
            raise RuntimeError("original solver process is still live")
    except psutil.NoSuchProcess:
        pass
    statuses = []
    models = 0
    for line in stdout.open("rb"):
        if line.startswith(b"s "):
            statuses.append(line.decode("ascii", errors="replace").strip())
        elif line.startswith(b"v "):
            models += 1
    if (statuses != result["solver_status_lines"] or
            models != result["solver_model_line_count"] or
            result["combined_peak_rss_bytes"] > protocol["rss_limit_bytes"] and
            result["status"] != "OOM"):
        raise ValueError("raw status/model/resource result differs")
    if (result["status"] == "CENSORED_TIME" and
            result["stop_reason"] == "WALL_CAP" and
            result["solver_exit_code"] == -15 and
            580 <= result["solver_wall_seconds"] < 591 and
            not statuses and models == 0):
        classification = "CENSORED_TIME"
    elif (result["status"] == "SAT_MODEL_REQUIRES_INDEPENDENT_AUDIT" and
          statuses == ["s SATISFIABLE"] and models):
        classification = "SAT_MODEL_REQUIRES_INDEPENDENT_AUDIT"
    elif (result["status"] == "OOM" and result["stop_reason"] == "RSS_CAP"):
        classification = "OOM"
    elif (result["status"] == "UNSAT" and
          statuses == ["s UNSATISFIABLE"] and models == 0):
        classification = "UNSAT"
    else:
        classification = "INDETERMINATE"
    receipt = {
        "kind": "n131_d10_cnf_xor_bridge_independent_terminal_audit",
        "status": classification,
        "proposal_id": protocol["proposal_id"],
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "target_count": 1,
        "solver_wall_seconds": result["solver_wall_seconds"],
        "combined_peak_rss_bytes": result["combined_peak_rss_bytes"],
        "solver_status_lines": statuses,
        "solver_model_line_count": models,
        "original_solver_process_drained": True,
        "source_sha256": {
            "protocol": sha(PROTOCOL), "formula": sha(FORMULA),
            "started": sha(RUN / "started.json"),
            "process": sha(RUN / "solver_process.json"),
            "result": sha(result_path), "stdout": sha(stdout),
            "stderr": sha(stderr), "runtime": sha(RUN / "sage_runtime_info.json"),
            "solver": sha(SOLVER), "runner": sha(RUNNER),
            "auditor": sha(Path(__file__)),
        },
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": classification,
                      "solver_model_line_count": models}))


if __name__ == "__main__":
    main()
