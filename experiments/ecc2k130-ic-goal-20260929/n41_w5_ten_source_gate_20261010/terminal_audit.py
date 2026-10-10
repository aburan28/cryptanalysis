#!/usr/bin/env python3
"""Independently check public-query input custody and terminal solver state."""
import hashlib
import json
from pathlib import Path

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=json.loads((here/"protocol_v2.json").read_text())
g=json.loads((here/"geometry_result.json").read_text())
a=json.loads((here/"sage_geometry_audit.json").read_text())
c=json.loads((here/"preflight_v2/receipt.json").read_text())
r=json.loads((here/"public/result.json").read_text())
process=json.loads((here/"public/process.json").read_text())
stdout=(here/"public/solver.stdout.txt").read_text(errors="replace")
assert p["status"]=="FROZEN_BEFORE_FORMULA"
assert a["status"]=="PASS_EXACT_SAGE_GEOMETRY_AND_GROUP_BASE"
assert c["status"]=="PASS_FULL_FORMULA_AND_GROUP_CONTROL"
assert p["public_target_q"]==g["public_target_q"]==r["public_target_q"]
assert p["actual_factor_base_points_B"]==g["actual_subgroup_factor_base_points_B"]
assert p["effective_folded_columns_K"]==g["folded_columns_K"]
assert p["source_sha256"]["run"]==sha(here/"run.py")
assert p["source_sha256"]["circuit"]==sha(here/"circuit.py")
assert r["source_sha256"]["protocol"]==sha(here/"protocol_v2.json")
for name,file in (("formula","system.xcnf"),("stdout","solver.stdout.txt"),
                  ("stderr","solver.stderr.txt"),("process","process.json")):
    assert r["source_sha256"][name]==sha(here/"public"/file)
assert r["formula"]["sha256"]==sha(here/"public/system.xcnf")
assert r["formula"]["bytes"]==(here/"public/system.xcnf").stat().st_size
assert process["command"]==r["solver_command"]
assert process["command"][1:1+len(p["solver_flags"])]==p["solver_flags"]
assert r["target_count"]==1 and r["candidate_id"] is None
assert r["status"]=="CENSORED_TIME" and r["stop_reason"]=="SOLVER_WALL_CAP"
assert r["solver_exit_code"]==-15 and r["solver_status_lines"]==[]
assert r["model_lines"]==0 and r["producer_relation"] is None
assert r["phase_seconds"]["online_wall"]<p["online_cap_seconds"]
assert r["sampled_peak_combined_rss_bytes"]<p["rss_cap_bytes"]
restarts=sum(line.startswith("c rst ") for line in stdout.splitlines())
assert restarts>100 and "s SATISFIABLE" not in stdout and "s UNSATISFIABLE" not in stdout
result={"status":"PASS_TERMINAL_CAP_AND_SOURCE_CUSTODY",
        "producer_status":r["status"],
        "solver_search_began":True,"restart_log_lines":restarts,
        "online_wall_seconds":r["phase_seconds"]["online_wall"],
        "sampled_peak_combined_rss_bytes":r["sampled_peak_combined_rss_bytes"],
        "formula_sha256":r["formula"]["sha256"],
        "source_sha256":{"protocol":sha(here/"protocol_v2.json"),
                         "result":sha(here/"public/result.json"),
                         "stdout":sha(here/"public/solver.stdout.txt"),
                         "audit_script":sha(Path(__file__))}}
with (here/"public/terminal_audit.json").open("x") as f:
    json.dump(result,f,indent=2,sort_keys=True);f.write("\n")
print(json.dumps({"status":result["status"],"restarts":restarts}))
