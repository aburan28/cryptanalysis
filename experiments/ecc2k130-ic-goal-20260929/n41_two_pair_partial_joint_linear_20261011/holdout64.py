"""Frozen 64-row prefix of the original independent holdout draw."""

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
COUNT = 64
WIDTHS = (32, 36)
spec = importlib.util.spec_from_file_location("project", HERE / "project_n131.py")
project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project)


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def freeze():
    parent = json.loads((HERE / "holdout_panel.json").read_text())
    assert parent["status"] == "FROZEN_N131_JOINT_LINEAR_HOLDOUT"
    panel = {"status": "FROZEN_N131_JOINT_LINEAR_64_PREFIX",
             "candidate_id": None, "ids": parent["ids"][:COUNT],
             "source_panel_sha256": sha("holdout_panel.json"),
             "selection": "first 64 indices of the prior frozen 128-row sample",
             "widths": list(WIDTHS)}
    (HERE / "holdout64_panel.json").write_text(json.dumps(panel,indent=2,sort_keys=True)+"\n")
    protocol = {"status": "FROZEN_N131_JOINT_LINEAR_64_PROTOCOL",
                "candidate_id": None,
                "limits": {"workers": 1, "seconds": 120, "rss_bytes": 4294967296},
                "sha256": {name: sha(name) for name in
                           ("holdout64.py", "project_n131.py", "run.py",
                            "holdout64_panel.json", "holdout_panel.json",
                            "holdout_timeout.json", "n131_panel.json")}}
    (HERE / "holdout64_protocol.json").write_text(json.dumps(protocol,indent=2,sort_keys=True)+"\n")
    print(panel["status"], COUNT)


def evaluate():
    protocol = json.loads((HERE / "holdout64_protocol.json").read_text())
    for name,digest in protocol["sha256"].items():
        assert sha(name) == digest, name
    panel = json.loads((HERE / "holdout64_panel.json").read_text())
    prior = json.loads((HERE / "n131_panel.json").read_text())
    rows = project.table_rows()
    target = prior["target_z"]
    s1,s2 = (project.joint.frob(project.SEED << 1, r) for r in (26,39))
    results = []
    start = time.monotonic_ns()
    for i,(a,b) in enumerate(panel["ids"]):
        c,d = rows[a][0],project.joint.frob(rows[b][0],13)
        left = {"c":c,"s":s1,"seed_mask":project.SEED,"rotation":26}
        right = {"c":d,"s":s2,"seed_mask":project.SEED,"rotation":39}
        decisions = {str(k): project.joint.joint_consistency(left,right,target,k)
                     for k in WIDTHS}
        assert all(v["left_local"] and v["right_local"] for v in decisions.values())
        results.append({"label":f"holdout_{i}","ids":[a,b],
                        "coordinates":[c,d],"decisions":decisions})
        if time.monotonic_ns()-start > 120_000_000_000:
            raise TimeoutError("frozen 120-second cap")
    summary = {str(k): {"joint_passes":sum(row["decisions"][str(k)]["joint"]
                                          for row in results),
                        "both_local_passes":COUNT,
                        "rank_min":min(row["decisions"][str(k)]["rank"]
                                       for row in results),
                        "rank_max":max(row["decisions"][str(k)]["rank"]
                                       for row in results)} for k in WIDTHS}
    out = {"status":"COMPLETE_N131_JOINT_LINEAR_64_HOLDOUT",
           "candidate_id":None,"elapsed_ns":time.monotonic_ns()-start,
           "summary":summary,"rows":results,
           "protocol_sha256":sha("holdout64_protocol.json")}
    (HERE / "holdout64_result.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(out["status"],out["elapsed_ns"]/1e9,summary)


if __name__ == "__main__":
    if len(sys.argv)!=2 or sys.argv[1] not in ("freeze","evaluate"):
        raise SystemExit("usage: holdout64.py freeze|evaluate")
    (freeze if sys.argv[1]=="freeze" else evaluate)()
