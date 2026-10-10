"""Bounded parent for the N131 one-sided Artin-Schreier join."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE=Path(__file__).resolve().parent
SAGE=Path("/Volumes/SSD990/cryptanalysis/sage")
protocol=json.loads((HERE/"protocol_as.json").read_text())
assert protocol["source_sha256"]["run_as.py"]==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
assert not (HERE/"as_receipt.json").exists()
started=time.perf_counter()
peak=0
reason=None
with (HERE/"as_stdout.txt").open("x") as stdout,(HERE/"as_stderr.txt").open("x") as stderr:
    proc=subprocess.Popen([str(SAGE),"-python",str(HERE/"n131_as_join.py")],
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
        time.sleep(0.5)
    exit_code=proc.wait()
receipt={"status":"COMPLETE" if exit_code==0 else "FAILED",
         "exit_code":exit_code,"reason":reason,"parent_wall_s":time.perf_counter()-started,
         "sampled_peak_rss_bytes":peak,
         "protocol_sha256":hashlib.sha256((HERE/"protocol_as.json").read_bytes()).hexdigest(),
         "result_exists":(HERE/"as_result.json").exists()}
with (HERE/"as_receipt.json").open("x") as stream:
    json.dump(receipt,stream,sort_keys=True,indent=2)
    stream.write("\n")
print(receipt,flush=True)
