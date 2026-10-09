#!/usr/bin/env python3
"""Reconcile the public-Q bridge-projected attempt with its frozen protocol."""

import hashlib
import json
import re
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
RUN = HERE / "public_q_stage_R1"
PROTOCOL = HERE / "solver_protocol.json"
FORMULA = HERE / "budget1/projected.xcnf"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")

GOOD_MATRIX = re.compile(r"\[matrix\] Good\s+matrix\s+\d+\s+(\d+) x\s*(\d+)")
UNUSED_MATRIX = re.compile(r"\[matrix\] UNused\s+matrix\s+(\d+) x\s*(\d+)")
TOO_MANY = re.compile(r"Too many rows in matrix: (\d+)")
FOUND = re.compile(r"\[occ-xor\] found\s+(\d+)")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    output = RUN / "independent_terminal_audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads(PROTOCOL.read_text())
    started = json.loads((RUN / "started.json").read_text())
    process = json.loads((RUN / "solver_process.json").read_text())
    result = json.loads((RUN / "result.json").read_text())
    stdout = RUN / "cryptominisat.stdout.txt"
    stderr = RUN / "cryptominisat.stderr.txt"
    checks = {
        "protocol_hash": started["protocol_sha256"] == sha(PROTOCOL) == result["source_sha256"]["protocol"],
        "formula_hash": sha(FORMULA) == protocol["source_sha256"]["formula"] == result["source_sha256"]["formula"],
        "solver_hash": sha(SOLVER) == protocol["source_sha256"]["solver"] == result["source_sha256"]["solver"],
        "runner_hash": sha(HERE / "run_public.py") == protocol["source_sha256"]["runner"] == result["source_sha256"]["runner"],
        "runtime_hash": sha(RUN / "sage_runtime_info.json") == started["runtime_info_sha256"] == result["source_sha256"]["runtime"],
        "stdout_hash": sha(stdout) == result["source_sha256"]["stdout"],
        "stderr_hash": sha(stderr) == result["source_sha256"]["stderr"],
        "one_target": started["target_count"] == result["target_count"] == 1 and
                      started["batch"] is False and result["batch"] is False,
        "identity": started["proposal_id"] == result["proposal_id"] == protocol["proposal_id"] and
                    started["curve_id"] == result["curve_id"] == protocol["curve_id"] and
                    started["workload_id"] == result["workload_id"] == protocol["workload_id"],
        "command": started["solver_command"] == process["command"] == [
            str(SOLVER), *protocol["solver_flags_common"], "--maxtime=578", str(FORMULA)],
        "within_rss_cap_or_oom": result["combined_peak_rss_bytes"] <= protocol["limit"]["combined_rss_bytes"] or
                                 result["status"] == "OOM",
    }
    try:
        live = psutil.Process(process["pid"])
    except psutil.NoSuchProcess:
        checks["solver_drained"] = True
    else:
        checks["solver_drained"] = not (
            abs(live.create_time() - process["create_time_epoch"]) < .05 and
            live.is_running() and live.status() != psutil.STATUS_ZOMBIE)
    if not all(checks.values()):
        raise AssertionError({"failed_checks": [key for key, passed in checks.items() if not passed]})
    statuses = []
    models = 0
    matrix_init = 0
    found = []
    dimensions = []
    oversized = []
    disabled = 0
    for line in stdout.open("rt", errors="replace"):
        if line.startswith("s "):
            statuses.append(line.strip())
        elif line.startswith("v "):
            models += 1
        matrix_init += "[find&init matx] performing matrix init" in line
        disabled += "TODO disable matrix, performing badly" in line
        if match := FOUND.search(line):
            found.append(int(match.group(1)))
        if match := GOOD_MATRIX.search(line) or UNUSED_MATRIX.search(line):
            dimensions.append((int(match.group(1)), int(match.group(2))))
        if match := TOO_MANY.search(line):
            oversized.append(int(match.group(1)))
    if statuses != result["solver_status_lines"] or models != result["solver_model_line_count"]:
        raise AssertionError("raw solver result differs from recorded status/model count")
    bridge_preserved = (matrix_init >= 2 and not found and not oversized and
                        dimensions and max(row for row, _ in dimensions) <= 10000 and
                        max(col for _, col in dimensions) <= 15000)
    if (result["status"] == "CENSORED_TIME" and
            ((result["stop_reason"] == "WALL_CAP" and not statuses) or
             (result["stop_reason"] == "SOLVER_TIME_LIMIT" and
              statuses == ["s INDETERMINATE"])) and models == 0 and
            578 <= result["solver_wall_seconds"] < 600):
        classification = "CENSORED_TIME"
    elif result["status"] == "SAT_MODEL_REQUIRES_INDEPENDENT_AUDIT" and statuses == ["s SATISFIABLE"] and models:
        classification = "SAT_MODEL_REQUIRES_INDEPENDENT_RELATION_AUDIT"
    elif result["status"] == "OOM" and result["stop_reason"] == "RSS_CAP":
        classification = "OOM"
    elif result["status"] == "UNSAT" and statuses == ["s UNSATISFIABLE"] and models == 0:
        classification = "UNSAT"
    else:
        classification = "INDETERMINATE"
    receipt = {
        "kind": "n131_d13_public_q_bridge_projected_independent_terminal_audit",
        "status": classification,
        "bridge_preserved_through_reported_matrix_initializations": bool(bridge_preserved),
        "matrix_init_count": matrix_init,
        "occurrence_xor_discovery_counts": found,
        "oversized_matrix_rows": sorted(set(oversized)),
        "max_reported_matrix_rows": max((row for row, _ in dimensions), default=None),
        "max_reported_matrix_columns": max((col for _, col in dimensions), default=None),
        "poor_performance_matrix_disable_count": disabled,
        "solver_status_lines": statuses, "solver_model_line_count": models,
        "solver_wall_seconds": result["solver_wall_seconds"],
        "solver_cpu_seconds_lower_bound": result["solver_cpu_seconds_lower_bound"],
        "combined_peak_rss_bytes": result["combined_peak_rss_bytes"],
        "checks": checks,
        "source_sha256": {"protocol": sha(PROTOCOL), "started": sha(RUN / "started.json"),
                          "process": sha(RUN / "solver_process.json"),
                          "result": sha(RUN / "result.json"),
                          "stdout": sha(stdout), "stderr": sha(stderr),
                          "auditor": sha(Path(__file__))},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": classification, "bridge_preserved": bool(bridge_preserved),
                      "solver_model_line_count": models}))


if __name__ == "__main__":
    main()
