#!/usr/bin/env python3
"""Audit archived ECC2K-130 public XCNF and bounded solver terminal state."""
import gzip
import hashlib
import json
from pathlib import Path

here=Path(__file__).resolve().parent
folder=here/"n131_public"
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
protocol=json.loads((here/"n131_public_protocol.json").read_text())
control=json.loads((here/"n131_control_result.json").read_text())
result=json.loads((folder/"result.json").read_text())
process=json.loads((folder/"process.json").read_text())
assert protocol["status"]=="FROZEN_BEFORE_PUBLIC_QUERY"
assert control["status"]=="PASS_FULL_FORMULA_CONTROL"
assert result["target_count"]==1
assert result["public_target_q"]==protocol["public_target_q"]
assert result["factor_base_B"]==protocol["B"]==3673460
assert result["folded_columns_K"]==protocol["K"]==262151
assert result["solver_command"]==process["command"]
assert result["solver_command"][4]=="--random=20261009"
assert result["source_sha256"]=={
    "protocol":sha(here/"n131_public_protocol.json"),
    "formula_archive":sha(folder/"system.xcnf.gz"),
    "stdout":sha(folder/"solver.stdout.txt"),
    "stderr":sha(folder/"solver.stderr.txt"),
    "process":sha(folder/"process.json")}
formula=result["formula"]
assert formula["compressed_sha256"]==sha(folder/"system.xcnf.gz")
digest=hashlib.sha256()
size=0
with gzip.open(folder/"system.xcnf.gz","rb") as stream:
    header=stream.readline().decode().strip()
    first=header.encode()+b"\n"
    digest.update(first)
    size+=len(first)
    for block in iter(lambda:stream.read(1<<20),b""):
        digest.update(block)
        size+=len(block)
assert digest.hexdigest()==formula["sha256"] and size==formula["bytes"]
assert header==f"p cnf {formula['variables']} {formula['clauses']+formula['xor_rows']}"
assert result["sampled_peak_combined_rss_bytes"]<=protocol["rss_cap_bytes"]
assert result["phase_seconds"]["online_wall"]<=protocol["online_cap_seconds"]+1
assert result["sampled_solver_cpu_seconds"]>1
stdout=(folder/"solver.stdout.txt").read_text(errors="replace")
search_began="c rst " in stdout or "c [search" in stdout
assert search_began
status=result["status"]
if status=="CENSORED_TIME":
    assert result["stop_reason"] in ("SOLVER_WALL_CAP","ONLINE_WALL_CAP")
    assert result["model_lines"]==0
elif status=="SAT_MODEL_PENDING_INDEPENDENT_SAGE":
    assert result["solver_status_lines"]==["s SATISFIABLE"]
    assert result["model_lines"]>0 and result["producer_xcnf_check"]
elif status=="UNSAT_FORMULA":
    pass
elif status not in ("OOM","PRODUCER_OR_SOLVER_FAILURE"):
    raise ValueError("unexpected public terminal status")
audit={"status":"PASS_PUBLIC_TERMINAL_AND_ARCHIVE_CUSTODY",
       "producer_status":status,"solver_search_began":search_began,
       "online_wall_seconds":result["phase_seconds"]["online_wall"],
       "peak_combined_rss_bytes":result["sampled_peak_combined_rss_bytes"],
       "formula_sha256":formula["sha256"],
       "source_sha256":{"protocol":sha(here/"n131_public_protocol.json"),
                        "result":sha(folder/"result.json"),
                        "formula_archive":sha(folder/"system.xcnf.gz"),
                        "script":sha(Path(__file__))}}
with (folder/"terminal_audit.json").open("x") as out:
    json.dump(audit,out,indent=2,sort_keys=True)
    out.write("\n")
print(json.dumps({"status":audit["status"],"producer_status":status}))
