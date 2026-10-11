"""Check frozen inputs and compare complete exact and reciprocal S3 censuses."""

import collections
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text())


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


protocol = read("protocol.json")
s3_protocol = read("protocol_s3.json")
panel = read("panel.json")
exact = read("receipt.json")
s3 = read("s3_receipt.json")
sage = read("sage_replay.json")
assert protocol["status"] == "FROZEN_FULL_N41_FIRSTHALF_EXACT_CENSUS"
assert s3_protocol["status"] == "FROZEN_RECIPROCAL_S3_FULL_PANEL"
assert sage["status"] == "PASS_SAGE_FULL_FIRSTHALF_INPUT_AND_POSITIVE_REPLAY"
assert panel["selected_count"] == sage["controls"] == 1711

for key, name in {"source": "exact_full.cpp", "binary": "exact_full_native",
                  "exact_input": "exact_input.txt", "panel": "panel.json",
                  "targets": "targets.txt", "producer": "make_full_sage.py",
                  "runtime": "sage_runtime_info.json"}.items():
    assert protocol["sha256"][key] == sha(name), key
for name, expected in s3_protocol["sha256"].items():
    assert expected == sha(name), name
for name, expected in sage["sha256"].items():
    assert expected == sha(name), name

qa, qb = exact["queries"], s3["queries"]
assert len(qa) == len(qb) == 1712
assert exact["exact_pair_witnesses"] == s3["exact_pair_witnesses"] == [1956, 1956]
assert exact["distinct_exact_pair_points"] == s3["distinct_exact_pair_points"] == [1956, 1956]
assert [q["label"] for q in qa] == ["positive"] + [f"control_{i}" for i in range(1711)]
for a, b in zip(qa, qb):
    for key in ("label", "status", "target", "pair_probes", "group_hits",
                "column_compatible_hits"):
        assert a[key] == b[key], (a["label"], key)
    assert a["pair_probes"] == 1956
assert qa[0]["status"] == "EXACT_FOUR_ATOM_HIT"
assert qa[0]["group_hits"] == qa[0]["column_compatible_hits"] == 1
assert qa[0]["source_witnesses"] == qb[0]["source_witnesses"]
assert all(q["status"] == "COMPLETE_EXACT_NO_SUM" and q["group_hits"] == 0
           for q in qa[1:])
assert sum(q["root_candidates"] for q in qb) == 4

out = {"status": "PASS_FULL_N41_FIRSTHALF_CENSUS_AUDIT",
       "candidate_id": None,
       "input_law": panel["selection"],
       "control_count": len(qa)-1,
       "status_counts": dict(collections.Counter(q["status"] for q in qa)),
       "s3_root_candidates": sum(q["root_candidates"] for q in qb),
       "exact_group_hits": sum(q["group_hits"] for q in qa),
       "exact_online_ns_sum": sum(q["online_ns"] for q in qa),
       "s3_online_ns_sum": sum(q["online_ns"] for q in qb),
       "exact_setup_ns": exact["reusable_setup_ns"],
       "s3_setup_ns": s3["reusable_setup_ns"],
       "exact_peak_rss_bytes": exact["peak_rss_bytes"],
       "s3_peak_rss_bytes": s3["peak_rss_bytes"],
       "sha256": {name: sha(name) for name in
                  ("protocol.json", "protocol_s3.json", "receipt.json",
                   "s3_receipt.json", "sage_replay.json")}}
(HERE / "audit.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], out["control_count"], out["status_counts"])
