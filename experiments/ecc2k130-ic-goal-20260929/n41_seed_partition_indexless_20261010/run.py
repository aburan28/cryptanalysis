"""Run one frozen target-conditioned seed-partitioned N41 public query."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
INPUT=BASE/"n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"
HELPER=BASE/"n131_w18_four_pairs/native_join/frozen_source/helper.cpp"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads((HERE/"protocol.json").read_text())
assert freeze["status"]=="FROZEN_BEFORE_N41_SEED_PARTITION_PUBLIC_QUERY"
sources={"native.cpp":HERE/"native.cpp","native":HERE/"native",
         "run.py":Path(__file__),"input":INPUT,"helper.cpp":HELPER,
         "sage_runtime_info":HERE/"sage_runtime_info.json"}
assert freeze["sha256"]=={name:sha(path) for name,path in sources.items()}
assert not any((HERE/name).exists() for name in
               ("hit.json","native_result.json","stdout.txt","stderr.txt","receipt.json"))
command=[str(HERE/"native"),str(INPUT),str(HERE/"hit.json"),
         str(HERE/"native_result.json"),str(freeze["native_online_cap_seconds"]),
         str(freeze["rss_cap_bytes"])]
started=time.monotonic_ns()
status=None
code=None
with (HERE/"stdout.txt").open("x") as stdout,(HERE/"stderr.txt").open("x") as stderr:
    try:
        child=subprocess.run(command,stdout=stdout,stderr=stderr,
                             timeout=freeze["parent_cap_seconds"],check=False)
        code=child.returncode
    except subprocess.TimeoutExpired:
        status="CENSORED_PARENT_CAP"
parent_ns=time.monotonic_ns()-started
native=json.loads((HERE/"native_result.json").read_text()) if (HERE/"native_result.json").exists() else None
if status is None:
    status=native["status"] if code==0 and native else "PRODUCER_FAILURE"
if native and native["peak_rss_bytes"]>freeze["rss_cap_bytes"]:
    status="CENSORED_MEMORY"
if native and native["online_ns"]>freeze["native_online_cap_seconds"]*10**9:
    status="CENSORED_ONLINE_TIME"
hit=json.loads((HERE/"hit.json").read_text()) if (HERE/"hit.json").exists() else None
if status=="FOUND_PENDING_SAGE_REPLAY":
    assert hit and hit["status"]=="NATIVE_RELATION_PENDING_SAGE"
    assert hit["seed_sums"][2]==hit["seed_sums"][3]
    assert hit["seed_sums"][4]==hit["seed_sums"][5]
    assert hit["seed_sums"][2]^hit["seed_sums"][4] in freeze["allowed_offsets"]
    assert hit["raw_sum"]==freeze["public_target"]
receipt={"status":status,"candidate_id":None,"command":command,
         "process_exit_code":code,"parent_wall_ns":parent_ns,
         "protocol_sha256":sha(HERE/"protocol.json"),
         "source_sha256":freeze["sha256"],"native":native,"hit":hit,
         "artifact_sha256":{name:sha(HERE/name) for name in
             ("hit.json","native_result.json","stdout.txt","stderr.txt")
             if (HERE/name).exists()}}
with (HERE/"receipt.json").open("x") as output:
    json.dump(receipt,output,sort_keys=True,indent=2);output.write("\n")
print(json.dumps({"status":status,"parent_wall_s":parent_ns/1e9,
    "found_seed":native["found_seed"] if native else None,
    "online_s":native["online_ns"]/1e9 if native else None},sort_keys=True))
