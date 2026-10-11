"""Bind frozen source receipts and paired exact-output decisions."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def load(name):return json.loads((HERE/name).read_text())
def sha(name):return hashlib.sha256((HERE/name).read_bytes()).hexdigest()

for protocol_name in ("n131_wide_protocol.json","holdout_protocol.json",
                      "holdout64_protocol.json"):
    protocol=load(protocol_name)
    for name,digest in protocol["sha256"].items():
        assert sha(name)==digest,(protocol_name,name)
assert load("protocol.json")["sha256"]["run"]==sha("run.py")
assert load("n131_protocol.json")["sha256"]["project"]==sha("project_n131.py")
assert load("prefix_protocol.json")["sha256"]["source"]==sha("prefix_census.py")
n41=load("result.json")
n131=load("n131_wide_result.json")
holdout=load("holdout64_result.json")
prefix=load("prefix_result.json")
sage=load("sage_audit.json")
timeout=load("holdout_timeout.json")
assert n41["status"]=="COMPLETE_N41_JOINT_PARTIAL_LINEAR_PANEL"
assert n131["status"]=="COMPLETE_N131_WIDE_JOINT_LINEAR_PANEL"
assert holdout["status"]=="COMPLETE_N131_JOINT_LINEAR_64_HOLDOUT"
assert prefix["status"]=="COMPLETE_N131_PAIR_PREFIX_CENSUS"
assert sage["status"]=="PASS_INDEPENDENT_SAGE_JOINT_LINEAR_RANK"
assert timeout["status"]=="CENSORED_TIME" and not timeout["complete_panel"]
assert len(n41["rows"])==129 and len(n131["rows"])==25
assert len(holdout["rows"])==64
for width,expected in (("8",0),("10",16),("12",123)):
    assert n41["summary"][width]["controls_passing_joint"]==expected
for width,expected in (("32",6),("36",64)):
    assert holdout["summary"][width]["joint_passes"]==expected
    assert holdout["summary"][width]["both_local_passes"]==64
    assert prefix["counts"][width]=={"left_unique_prefixes":65868,
                                     "right_unique_prefixes":65868,"outputs":65868}
assert len(sage["checks"])==9
assert sage["checks"][-1]["consistent"] and not sage["checks"][-1]["exact_s3_zero"]
out={"status":"PASS_JOINT_PARTIAL_LINEAR_ARCHIVE_AUDIT",
     "candidate_id":None,
     "n41_controls":128,"n131_first_controls":24,"n131_holdout_controls":64,
     "holdout_128_status":timeout["status"],
     "sha256":{name:sha(name) for name in
               ("protocol.json","result.json","n131_protocol.json",
                "n131_wide_protocol.json","n131_wide_result.json",
                "holdout64_protocol.json","holdout64_result.json",
                "prefix_result.json","sage_audit.json")}}
(HERE/"audit.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print(out["status"])
