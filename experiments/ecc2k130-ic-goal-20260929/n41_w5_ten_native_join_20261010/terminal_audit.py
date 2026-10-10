#!/usr/bin/env python3
"""Bind frozen native source and input to both independent witness checks."""
import hashlib
import json
from pathlib import Path

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=json.loads((here/"protocol.json").read_text())
e=json.loads((here/"export_receipt.json").read_text())
s=json.loads((here/"run/started.json").read_text())
r=json.loads((here/"run/result.json").read_text())
hit=json.loads((here/"run/hits.jsonl").read_text().splitlines()[0])
sage=json.loads((here/"sage_hit_audit.json").read_text())
formula=json.loads((here/"formula_hit_audit.json").read_text())
assert p["status"]=="FROZEN_BEFORE_EXPORT_AND_JOIN"
assert e["status"]=="PASS_EXACT_NATIVE_INPUT_EXPORT"
assert s["status"]=="STARTED" and s["source_commit"]=="1765f4162"
assert s["protocol_sha256"]==sha(here/"protocol.json")
assert s["input_sha256"]==e["input_sha256"]==sha(here/"input.txt")
assert s["binary_sha256"]==p["native_sha256"]["binary"]==sha(here/"join")
assert p["native_sha256"]["join_source"]==sha(here/"join.cpp")
assert p["native_sha256"]["helper"]==sha(
    here.parent/"n131_w18_four_pairs/native_join/frozen_source/helper.cpp")
assert r["status"]=="FOUND_PENDING_SAGE_REPLAY" and r["found"]
assert r["left_distinct_four_sums"]==p["left_four_distinct_entries_expected"]
assert 0<r["right_distinct_probes"]<=p["max_right_distinct_probes"]
assert r["wall_ns"]<p["wall_cap_seconds"]*10**9
assert r["peak_rss_bytes"]<p["peak_rss_cap_bytes"]
assert r["group_hits"]==r["column_rejects"]+1
assert (here/"run/stderr.txt").stat().st_size==0
assert "FOUND_PENDING_SAGE_REPLAY" in (here/"run/stdout.txt").read_text()
assert sage["status"]=="PASS_INDEPENDENT_SAGE_PUBLIC_GROUP_REPLAY"
assert formula["status"]=="PASS_ARCHIVED_PUBLIC_XCNF_COMPLETE_ASSIGNMENT"
assert sage["masks"]==formula["masks"]==hit["masks"]
assert sage["signs"]==formula["signs"]==hit["signs"]
assert sage["raw_sum"]==formula["producer_relation"]["raw_sum"]==hit["raw_sum"]
result={"status":"PASS_FROZEN_NATIVE_RUN_AND_INDEPENDENT_REPLAY",
        "native_status":r["status"],"source_commit":s["source_commit"],
        "right_distinct_probes":r["right_distinct_probes"],
        "group_hits":r["group_hits"],"column_rejects":r["column_rejects"],
        "native_wall_ns":r["wall_ns"],"native_peak_rss_bytes":r["peak_rss_bytes"],
        "raw_sum":hit["raw_sum"],"target_preimage_index":hit["target_preimage_index"],
        "source_sha256":{"protocol":sha(here/"protocol.json"),
                         "input":sha(here/"input.txt"),
                         "binary":sha(here/"join"),
                         "native_result":sha(here/"run/result.json"),
                         "native_hit":sha(here/"run/hits.jsonl"),
                         "sage_replay":sha(here/"sage_hit_audit.json"),
                         "formula_replay":sha(here/"formula_hit_audit.json"),
                         "script":sha(Path(__file__))}}
with (here/"terminal_audit.json").open("x") as f:
    json.dump(result,f,indent=2,sort_keys=True);f.write("\n")
print(json.dumps({"status":result["status"],"probes":result["right_distinct_probes"]}))
