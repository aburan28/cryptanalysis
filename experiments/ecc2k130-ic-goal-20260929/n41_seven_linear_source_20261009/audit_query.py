#!/usr/bin/env python3
"""Audit the exact frozen public-point solver terminal state."""
import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
protocol = json.loads((here / "protocol.json").read_text())
preflight = json.loads((here / "preflight/receipt.json").read_text())
result = json.loads((here / "public/result.json").read_text())
process = json.loads((here / "public/process.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_MEASUREMENT"
assert preflight["status"] == "PASS_FULL_FORMULA_AND_GROUP_CONTROL"
assert preflight["protocol_sha256"] == sha(here / "protocol.json")
assert preflight["formula"]["sha256"] == sha(here / "preflight/system.xcnf")
assert result["formula"]["sha256"] == preflight["formula"]["sha256"]
assert result["source_sha256"] == {
    "protocol": sha(here / "protocol.json"),
    "formula": sha(here / "public/system.xcnf"),
    "stdout": sha(here / "public/solver.stdout.txt"),
    "stderr": sha(here / "public/solver.stderr.txt"),
    "process": sha(here / "public/process.json"),
}
assert result["solver_command"] == process["command"]
assert result["solver_command"][4] == "--random=20261009"
assert result["target_count"] == 1
assert result["public_target_q"] == protocol["public_target_q"]
assert result["transported_target_qprime"] == protocol["transported_target_qprime"]
assert result["phase_seconds"]["online_wall"] <= protocol["online_cap_seconds"] + 1
status = result["status"]
if status == "CENSORED_TIME":
    assert result["stop_reason"] in ("SOLVER_WALL_CAP", "ONLINE_WALL_CAP")
    assert result["model_lines"] == 0
elif status == "SAT_MODEL_PENDING_INDEPENDENT_SAGE":
    assert result["model_lines"] > 0
    assert result["solver_status_lines"] == ["s SATISFIABLE"]
    assert result["producer_relation"]["valid"] is True
elif status == "UNSAT_FORMULA":
    status = "CONTRADICTS_SAVED_SAT_ASSIGNMENT"
elif status not in ("OOM", "PRODUCER_OR_SOLVER_FAILURE", "INVALID_MODEL"):
    raise ValueError("unexpected terminal classification")
audit = {"status": "PASS_TERMINAL_CUSTODY",
         "producer_status": result["status"],
         "interpretation": status,
         "online_wall_seconds": result["phase_seconds"]["online_wall"],
         "formula_equal_to_saved_satisfiable_control": True,
         "source_sha256": {"protocol": sha(here / "protocol.json"),
                           "preflight": sha(here / "preflight/receipt.json"),
                           "result": sha(here / "public/result.json"),
                           "script": sha(Path(__file__))}}
with (here / "terminal_audit.json").open("x") as out:
    json.dump(audit, out, indent=2, sort_keys=True)
    out.write("\n")
print(json.dumps({"status": audit["status"], "producer_status": audit["producer_status"]}))
