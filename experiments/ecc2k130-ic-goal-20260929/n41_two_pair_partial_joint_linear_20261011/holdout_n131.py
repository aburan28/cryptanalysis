"""Independent 128-pair challenge-width holdout at the observed rank transition."""

import hashlib
import importlib.util
import json
import random
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
SEED = 202610111952
COUNT = 128
WIDTHS = (32, 36)
spec = importlib.util.spec_from_file_location("narrow", HERE / "project_n131.py")
narrow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(narrow)


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def freeze():
    table = narrow.table_rows()
    assert len(table) == 65868
    rng = random.Random(SEED)
    ids = [[rng.randrange(len(table)), rng.randrange(len(table))]
           for _ in range(COUNT)]
    panel = {"status": "FROZEN_N131_JOINT_LINEAR_HOLDOUT",
             "candidate_id": None, "sample_seed": SEED, "ids": ids,
             "widths": list(WIDTHS),
             "input_law": "128 independent exact fixed-seed output pairs with replacement"}
    (HERE / "holdout_panel.json").write_text(json.dumps(panel, indent=2, sort_keys=True)+"\n")
    protocol = {"status": "FROZEN_N131_JOINT_LINEAR_HOLDOUT_PROTOCOL",
                "candidate_id": None,
                "limits": {"workers": 1, "seconds": 120, "rss_bytes": 4294967296},
                "sha256": {name: sha(name) for name in
                           ("holdout_n131.py", "project_n131.py", "run.py",
                            "holdout_panel.json", "n131_panel.json",
                            "n131_wide_result.json")}}
    (HERE / "holdout_protocol.json").write_text(json.dumps(protocol, indent=2, sort_keys=True)+"\n")
    print(panel["status"], len(ids))


def evaluate():
    protocol = json.loads((HERE / "holdout_protocol.json").read_text())
    for name, digest in protocol["sha256"].items():
        assert sha(name) == digest, name
    panel = json.loads((HERE / "holdout_panel.json").read_text())
    parent = json.loads((HERE / "n131_panel.json").read_text())
    table = narrow.table_rows()
    target = parent["target_z"]
    s1, s2 = (narrow.joint.frob(narrow.SEED << 1, r) for r in (26, 39))
    results = []
    start = time.monotonic_ns()
    for i, (a,b) in enumerate(panel["ids"]):
        c = table[a][0]
        d = narrow.joint.frob(table[b][0], 13)
        left = {"c": c, "s": s1, "seed_mask": narrow.SEED, "rotation": 26}
        right = {"c": d, "s": s2, "seed_mask": narrow.SEED, "rotation": 39}
        decisions = {str(k): narrow.joint.joint_consistency(left,right,target,k)
                     for k in WIDTHS}
        assert all(q["left_local"] and q["right_local"]
                   for q in decisions.values())
        results.append({"label": f"holdout_{i}", "ids": [a,b],
                        "coordinates": [c,d], "decisions": decisions})
        if time.monotonic_ns()-start > 120_000_000_000:
            raise TimeoutError("frozen 120-second cap")
    summary = {str(k): {"joint_passes": sum(x["decisions"][str(k)]["joint"]
                                           for x in results),
                        "both_local_passes": COUNT,
                        "rank_min": min(x["decisions"][str(k)]["rank"]
                                        for x in results),
                        "rank_max": max(x["decisions"][str(k)]["rank"]
                                        for x in results)} for k in WIDTHS}
    out = {"status": "COMPLETE_N131_JOINT_LINEAR_HOLDOUT",
           "candidate_id": None, "elapsed_ns": time.monotonic_ns()-start,
           "summary": summary, "rows": results,
           "protocol_sha256": sha("holdout_protocol.json")}
    (HERE / "holdout_result.json").write_text(json.dumps(out, indent=2, sort_keys=True)+"\n")
    print(out["status"], out["elapsed_ns"]/1e9, summary)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "evaluate"):
        raise SystemExit("usage: holdout_n131.py freeze|evaluate")
    (freeze if sys.argv[1] == "freeze" else evaluate)()
