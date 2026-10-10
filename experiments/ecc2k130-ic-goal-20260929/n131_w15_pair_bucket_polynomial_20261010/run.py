"""Run the frozen Sage polynomial construction with wall and RSS guards."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
RESTRICTED=BASE/"n131_w15_joint_block_resultant_20261010/restricted_result.json"
SUPPORT=BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads((HERE/"protocol.json").read_text())
assert freeze["status"]=="FROZEN_BEFORE_W15_PAIR_BUCKET_POLYNOMIAL"
sources={"produce.py":HERE/"produce.py","run.py":Path(__file__),
    "restricted_result.json":RESTRICTED,"support_w15.tsv":SUPPORT,
    "sage_runtime_info":HERE/"sage_runtime_info.json"}
assert freeze["sha256"]=={name:sha(path) for name,path in sources.items()}
assert not any((HERE/name).exists() for name in
    ("result.json","control_n41.json","stdout.txt","stderr.txt","receipt.json"))
command=["/Volumes/SSD990/cryptanalysis/sage","-python",str(HERE/"produce.py")]
started=time.monotonic_ns()
peak=0
termination=None
with (HERE/"stdout.txt").open("x") as stdout,(HERE/"stderr.txt").open("x") as stderr:
    process=subprocess.Popen(command,stdout=stdout,stderr=stderr)
    observed=psutil.Process(process.pid)
    while process.poll() is None:
        try:
            family=[observed]+observed.children(recursive=True)
            current=sum(p.memory_info().rss for p in family if p.is_running())
            peak=max(peak,current)
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            pass
        if peak>freeze["rss_cap_bytes"]:
            termination="CENSORED_MEMORY";process.kill();break
        if time.monotonic_ns()-started>freeze["parent_cap_seconds"]*10**9:
            termination="CENSORED_PARENT_CAP";process.kill();break
        time.sleep(0.05)
    code=process.wait()
parent_ns=time.monotonic_ns()-started
result=json.loads((HERE/"result.json").read_text()) if (HERE/"result.json").exists() else None
status=termination or (result["status"] if code==0 and result else "PRODUCER_FAILURE")
receipt={"status":status,"process_exit_code":code,"command":command,
    "parent_wall_ns":parent_ns,"peak_sampled_family_rss_bytes":peak,
    "protocol_sha256":sha(HERE/"protocol.json"),
    "source_sha256":freeze["sha256"],"candidate_id":None,
    "result_sha256":sha(HERE/"result.json") if result else None,
    "n41_control_sha256":sha(HERE/"control_n41.json")
        if (HERE/"control_n41.json").exists() else None,
    "stdout_sha256":sha(HERE/"stdout.txt"),
    "stderr_sha256":sha(HERE/"stderr.txt")}
with (HERE/"receipt.json").open("x") as output:
    json.dump(receipt,output,sort_keys=True,indent=2);output.write("\n")
print({"status":status,"parent_wall_s":parent_ns/1e9,
       "peak_sampled_family_rss_bytes":peak})
