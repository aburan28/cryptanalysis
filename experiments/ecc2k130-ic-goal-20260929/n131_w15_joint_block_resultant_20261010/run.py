"""Freeze and run the one-worker Sage joint-block resultant panel."""

import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=HERE.parents[2]
SAGE=ROOT/"sage"
sources={"joint.py":HERE/"joint.py",
         "rotated_resultant":BASE/"n131_w15_rotated_fouratom_inverse_20261010/resultant.json",
         "n41_screen":BASE/"n41_n131_diagonal_atom_20261010/screen.json",
         "n41_hit":BASE/"n131_w15_cross_block_seed_offset_20261010/n41_hit.json",
         "n131_lift":BASE/"n131_w15_coupled_sixpair_20261010/control_group_lift.json",
         "sage_runtime_info":HERE/"sage_runtime_info.json"}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


assert (HERE/"sage_runtime_info.json").exists()
protocol={"status":"FROZEN_BEFORE_JOINT_BLOCK_RESULTANT_PANEL",
          "source_sha256":{name:sha(path) for name,path in sources.items()},
          "one_worker":True,"parent_cap_seconds":120,
          "rss_measurement":"child ru_maxrss after exit; no enforced RSS guard in this symbolic control",
          "cases":["N41 public point with known free-pair control and four raw target branches",
                   "N131 constructed witness with known free-pair control and four raw target branches"]}
with (HERE/"protocol_v2.json").open("x") as output:
    json.dump(protocol,output,sort_keys=True,indent=2);output.write("\n")
command=[str(SAGE),"-python",str(HERE/"joint.py")]
started=time.perf_counter_ns()
try:
    run=subprocess.run(command,capture_output=True,text=True,timeout=120)
    status="PROCESS_COMPLETE" if run.returncode==0 else "PROCESS_EXIT"
    stdout,stderr,exit_code=run.stdout,run.stderr,run.returncode
except subprocess.TimeoutExpired as error:
    status="PARENT_TIMEOUT"
    stdout=(error.stdout or b"").decode(errors="replace")
    stderr=(error.stderr or b"").decode(errors="replace")
    exit_code=None
receipt={"status":status,"exit_code":exit_code,"parent_wall_ns":time.perf_counter_ns()-started,
         "stdout":stdout,"stderr":stderr,"command":command,
         "peak_child_rss_bytes":resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
         "protocol_sha256":sha(HERE/"protocol_v2.json"),
         "result_sha256":sha(HERE/"result.json") if (HERE/"result.json").exists() else None}
with (HERE/"receipt_v2.json").open("x") as output:
    json.dump(receipt,output,sort_keys=True,indent=2);output.write("\n")
print(status,stdout.strip(),stderr.strip())
