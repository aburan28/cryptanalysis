"""Frozen wide-bit extension of the N131 joint linear projection."""

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
WIDTHS = (12, 16, 20, 24, 28, 32, 36, 40)
spec = importlib.util.spec_from_file_location("narrow", HERE / "project_n131.py")
narrow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(narrow)


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def freeze():
    panel = json.loads((HERE / "n131_panel.json").read_text())
    assert panel["status"] == "FROZEN_N131_W18_JOINT_LINEAR_PROJECTION"
    record = {"status": "FROZEN_N131_WIDE_JOINT_LINEAR_PROTOCOL",
              "candidate_id": None, "widths": list(WIDTHS),
              "limits": {"workers": 1, "seconds": 120, "rss_bytes": 4294967296},
              "sha256": {name: sha(name) for name in
                         ("project_n131_wide.py", "project_n131.py", "run.py",
                          "n131_panel.json", "n131_protocol.json", "n131_result.json")}}
    (HERE / "n131_wide_protocol.json").write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
    print(record["status"])


def evaluate():
    protocol = json.loads((HERE / "n131_wide_protocol.json").read_text())
    for name, digest in protocol["sha256"].items():
        assert sha(name) == digest, name
    panel = json.loads((HERE / "n131_panel.json").read_text())
    original = json.loads((HERE / "n131_result.json").read_text())
    s1, s2 = (narrow.joint.frob(narrow.SEED << 1, r) for r in (26, 39))
    target = panel["target_z"]
    start = time.monotonic_ns()
    rows = []
    for prior in original["rows"]:
        c, d = prior["coordinates"]
        left = {"c": c, "s": s1, "seed_mask": narrow.SEED, "rotation": 26}
        right = {"c": d, "s": s2, "seed_mask": narrow.SEED, "rotation": 39}
        decisions = {str(width): narrow.joint.joint_consistency(left, right, target, width)
                     for width in WIDTHS}
        if prior["label"] == "positive":
            assert all(q["joint"] for q in decisions.values())
        assert all(q["left_local"] and q["right_local"]
                   for q in decisions.values())
        rows.append({"label": prior["label"], "coordinates": [c,d],
                     "decisions": decisions})
        if time.monotonic_ns()-start > 120_000_000_000:
            raise TimeoutError("frozen 120-second cap")
    summary = {str(width): {
        "positive_passing": rows[0]["decisions"][str(width)]["joint"],
        "controls_passing_joint": sum(
            row["decisions"][str(width)]["joint"] for row in rows[1:]),
        "controls_passing_both_local": sum(
            row["decisions"][str(width)]["left_local"] and
            row["decisions"][str(width)]["right_local"] for row in rows[1:]),
        "rank_min": min(row["decisions"][str(width)]["rank"] for row in rows),
        "rank_max": max(row["decisions"][str(width)]["rank"] for row in rows),
        "variables": rows[0]["decisions"][str(width)]["variables"]}
               for width in WIDTHS}
    out = {"status": "COMPLETE_N131_WIDE_JOINT_LINEAR_PANEL",
           "candidate_id": None, "controls": len(rows)-1,
           "elapsed_ns": time.monotonic_ns()-start,
           "summary": summary, "rows": rows,
           "protocol_sha256": sha("n131_wide_protocol.json")}
    (HERE / "n131_wide_result.json").write_text(json.dumps(out, indent=2, sort_keys=True)+"\n")
    print(out["status"], out["elapsed_ns"]/1e9)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "evaluate"):
        raise SystemExit("usage: project_n131_wide.py freeze|evaluate")
    (freeze if sys.argv[1] == "freeze" else evaluate)()
