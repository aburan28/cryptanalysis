#!/usr/bin/env python3
"""Run frozen one-worker mixed-rotation proposed-output controls."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

here = Path(__file__).resolve().parent
old = here.parent / "n131_w14_coupled_fouratom_inverse_20261010"
support = here.parent / "n131_w14_ten_source_gate_20261009" / "support_w14.tsv"
protocol = json.loads((here / "protocol.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_MIXED_ROTATION_PANEL"
files = {
    "native.cpp": here / "native.cpp",
    "native": here / "native",
    "prepare.py": here / "prepare.py",
    "inputs.json": here / "inputs.json",
    "run.py": here / "run.py",
    "sage_audit.py": here / "sage_audit.py",
    "sage_runtime_info.json": here / "sage_runtime_info.json",
    "legacy_native.cpp": old / "native.cpp",
    "support_w14.tsv": support,
}
for n,case in protocol["run_order"]:
    path = here / f"n{n}_{case}.txt"
    files[path.name] = path
assert protocol["source_sha256"] == {
    name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()
}
rows=[]
for n,case in protocol["run_order"]:
    name=f"n{n}_{case}"
    output=here/f"{name}.json"
    command=[str(here/"native"),str(here/f"{name}.txt"),str(output),
             "-" if n==41 else str(support),
             str(protocol["cap_seconds_per_run"]),str(protocol["rss_cap_bytes"])]
    start=time.monotonic_ns()
    try:
        process=subprocess.run(command,capture_output=True,text=True,
                               timeout=protocol["cap_seconds_per_run"]+5)
        status="PROCESS_OK" if process.returncode==0 else "PROCESS_FAILURE"
        code=process.returncode;stdout=process.stdout;stderr=process.stderr
    except subprocess.TimeoutExpired as exc:
        status="PARENT_TIMEOUT";code=None
        stdout=exc.stdout.decode(errors="replace") if isinstance(exc.stdout,bytes) else (exc.stdout or "")
        stderr=exc.stderr.decode(errors="replace") if isinstance(exc.stderr,bytes) else (exc.stderr or "")
    parent_ns=time.monotonic_ns()-start
    (here/f"{name}.stdout.txt").write_text(stdout)
    (here/f"{name}.stderr.txt").write_text(stderr)
    native=json.loads(output.read_text()) if output.exists() else None
    rows.append({"field_degree":n,"case":case,"status":status,"returncode":code,
                 "parent_ns":parent_ns,"native":native,
                 "input_sha256":hashlib.sha256((here/f"{name}.txt").read_bytes()).hexdigest()})
    (here/"result.json").write_text(json.dumps({"rows":rows,
         "protocol_sha256":hashlib.sha256((here/"protocol.json").read_bytes()).hexdigest()},
         indent=2,sort_keys=True)+"\n")
    print(json.dumps({"name":name,"status":status,
                      "native_status":native["status"] if native else None,
                      "hits":len(native["hits"]) if native else None,
                      "setup_s":native["setup_ns"]/1e9 if native else None,
                      "query_s":native["query_ns"]/1e9 if native else None},sort_keys=True),flush=True)
