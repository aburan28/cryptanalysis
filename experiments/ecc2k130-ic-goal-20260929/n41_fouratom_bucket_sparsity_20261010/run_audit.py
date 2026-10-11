"""Bounded parent for the independent integer-field replay."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE=Path(__file__).resolve().parent
freeze=json.loads((HERE/"audit_protocol.json").read_text())
assert freeze["source_sha256"]["run_audit.py"]==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
assert not (HERE/"audit_receipt.json").exists()
started=time.perf_counter()
peak=0
reason=None
with (HERE/"audit_stdout.txt").open("x") as stdout,(HERE/"audit_stderr.txt").open("x") as stderr:
    proc=subprocess.Popen(["python3",str(HERE/"audit.py")],
                          cwd=HERE,stdout=stdout,stderr=stderr)
    watched=psutil.Process(proc.pid)
    while proc.poll() is None:
        try:peak=max(peak,watched.memory_info().rss)
        except psutil.Error:pass
        if peak>freeze["memory_cap_bytes"]:reason="RSS_CAP"
        elif time.perf_counter()-started>freeze["cap_seconds"]:reason="WALL_CAP"
        if reason:
            proc.kill()
            break
        time.sleep(0.2)
    exit_code=proc.wait()
receipt={"status":"COMPLETE" if exit_code==0 else "FAILED",
         "exit_code":exit_code,"reason":reason,"parent_wall_s":time.perf_counter()-started,
         "sampled_peak_rss_bytes":peak,
         "protocol_sha256":hashlib.sha256((HERE/"audit_protocol.json").read_bytes()).hexdigest(),
         "result_exists":(HERE/"audit_result.json").exists()}
with (HERE/"audit_receipt.json").open("x") as stream:
    json.dump(receipt,stream,sort_keys=True,indent=2)
    stream.write("\n")
print(receipt,flush=True)
