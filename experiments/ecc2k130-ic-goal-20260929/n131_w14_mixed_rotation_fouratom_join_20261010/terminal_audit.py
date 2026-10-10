#!/usr/bin/env python3
"""Check source/input binding, caps, raw statuses, and Sage replay."""

import hashlib
import json
from pathlib import Path

here=Path(__file__).resolve().parent
old=here.parent/"n131_w14_coupled_fouratom_inverse_20261010"
support=here.parent/"n131_w14_ten_source_gate_20261009"/"support_w14.tsv"
protocol=json.loads((here/"protocol.json").read_text())
result=json.loads((here/"result.json").read_text())
sage=json.loads((here/"sage_audit.json").read_text())
files={
    "native.cpp":here/"native.cpp", "native":here/"native",
    "prepare.py":here/"prepare.py", "inputs.json":here/"inputs.json",
    "run.py":here/"run.py", "sage_audit.py":here/"sage_audit.py",
    "sage_runtime_info.json":here/"sage_runtime_info.json",
    "legacy_native.cpp":old/"native.cpp", "support_w14.tsv":support,
}
for n,case in protocol["run_order"]:
    name=f"n{n}_{case}.txt"
    files[name]=here/name
assert protocol["source_sha256"]=={
    name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()
}
assert result["protocol_sha256"]==hashlib.sha256((here/"protocol.json").read_bytes()).hexdigest()
assert sage["status"]=="PASS_INDEPENDENT_MIXED_ROTATION_REPLAY"
assert sage["source_sha256"]["result"]==hashlib.sha256((here/"result.json").read_bytes()).hexdigest()
assert len(result["rows"])==len(protocol["run_order"])==4
for row,(n,case) in zip(result["rows"],protocol["run_order"]):
    assert (row["field_degree"],row["case"])==(n,case)
    assert row["status"]=="PROCESS_OK" and row["returncode"]==0
    assert row["input_sha256"]==protocol["source_sha256"][f"n{n}_{case}.txt"]
    native=row["native"]
    assert native["status"]=="COMPLETE_ALGEBRAIC_SCAN"
    assert native["setup_ns"]<protocol["cap_seconds_per_run"]*10**9
    assert native["query_ns"]<protocol["cap_seconds_per_run"]*10**9
    assert native["peak_rss_bytes"]<protocol["rss_cap_bytes"]
    assert native["left_outputs_checked"]==native["distinct_pair_outputs"][0]
    raw=json.loads((here/f"n{n}_{case}.json").read_text())
    assert raw==native
    assert not (here/f"n{n}_{case}.stderr.txt").read_text()
    assert "COMPLETE_ALGEBRAIC_SCAN" in (here/f"n{n}_{case}.stdout.txt").read_text()
    assert len(native["hits"])==(1 if case=="positive" else 0)
    if n==131:
        assert native["source_product_count"]==2062
        assert native["distinct_pair_outputs"]==[4124,4124]
    else:
        assert native["source_product_count"]==32
        assert native["distinct_pair_outputs"]==[33,33]
audit={"status":"PASS_TERMINAL_MIXED_ROTATION_AUDIT",
       "rows":4,"n131_positive_group_replay":True,
       "protocol_sha256":hashlib.sha256((here/"protocol.json").read_bytes()).hexdigest(),
       "result_sha256":hashlib.sha256((here/"result.json").read_bytes()).hexdigest(),
       "sage_audit_sha256":hashlib.sha256((here/"sage_audit.json").read_bytes()).hexdigest(),
       "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(here/"terminal_audit.json").write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n")
print(json.dumps(audit,sort_keys=True))
