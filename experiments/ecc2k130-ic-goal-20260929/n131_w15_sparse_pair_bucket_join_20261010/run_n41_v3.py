"""Bounded parent for quotient-ring N41 join."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE=Path(__file__).resolve().parent
SAGE=Path("/Volumes/SSD990/cryptanalysis/sage")
protocol=json.loads((HERE/"protocol_v3.json").read_text())
assert protocol["source_sha256"]["run_n41_v3.py"]==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
assert not (HERE/"n41_receipt_v3.json").exists()
started=time.perf_counter()
peak=0
reason=None
with (HERE/"n41_stdout_v3.txt").open("x") as stdout,(HERE/"n41_stderr_v3.txt").open("x") as stderr:
    proc=subprocess.Popen([str(SAGE),"-python",str(HERE/"n41_quotient_v3.py")],
                          cwd=SAGE.parent,stdout=stdout,stderr=stderr)
    watched=psutil.Process(proc.pid)
    while proc.poll() is None:
        try:peak=max(peak,watched.memory_info().rss)
        except psutil.Error:pass
        if peak>protocol["memory_cap_bytes"]:reason="RSS_CAP"
        elif time.perf_counter()-started>protocol["cap_seconds"]:reason="WALL_CAP"
        if reason:
            proc.kill()
            break
        time.sleep(0.2)
    exit_code=proc.wait()
receipt={"status":"COMPLETE" if exit_code==0 else "FAILED",
         "exit_code":exit_code,"reason":reason,"parent_wall_s":time.perf_counter()-started,
         "sampled_peak_rss_bytes":peak,
         "protocol_sha256":hashlib.sha256((HERE/"protocol_v3.json").read_bytes()).hexdigest(),
         "result_exists":(HERE/"n41_result_v3.json").exists()}
with (HERE/"n41_receipt_v3.json").open("x") as stream:
    json.dump(receipt,stream,sort_keys=True,indent=2)
    stream.write("\n")
print(receipt,flush=True)
