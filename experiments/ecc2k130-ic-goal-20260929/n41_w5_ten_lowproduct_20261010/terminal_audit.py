#!/usr/bin/env python3
"""Bind the bounded public SAT run to its frozen source and witness audit."""
import json
from pathlib import Path

from solver_gate import AUDIT, FORMULA, HERE, PROTOCOL, sources, sha

protocol = json.loads(PROTOCOL.read_text())
audit = json.loads(AUDIT.read_text())
folder = HERE / "solver_run"
process = json.loads((folder / "process.json").read_text())
result = json.loads((folder / "result.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_UNPINNED_SAT_QUERY"
assert protocol["source_sha256"] == {name: sha(path)
                                       for name, path in sources().items()}
assert audit["status"] == "PASS_PUBLIC_RELATION_XCNF_ASSIGNMENT"
assert audit["formula"]["sha256"] == sha(FORMULA)
assert process["protocol_sha256"] == result["source_sha256"]["protocol"] == sha(PROTOCOL)
assert process["command"][-1] == str(FORMULA)
assert result["status"] == "CENSORED_TIME"
assert result["stop_reason"] == "WALL_CAP"
assert 0 < result["wall_seconds"] <= protocol["wall_cap_seconds"] + 1
assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
assert result["solver_status_lines"] == [] and result["model_lines"] == 0
assert result["source_sha256"]["stdout"] == sha(folder / "stdout.txt")
assert result["source_sha256"]["stderr"] == sha(folder / "stderr.txt")
assert result["source_sha256"]["process"] == sha(folder / "process.json")
assert (folder / "stderr.txt").stat().st_size == 0
stdout = (folder / "stdout.txt").read_text()
assert "c rst" in stdout and "K" in stdout
receipt = {"status": "PASS_FROZEN_FRAMED_FORMULA_AND_BOUNDED_SEARCH",
           "query_status": result["status"],
           "public_target_q": protocol["public_target_q"],
           "formula_sha256": sha(FORMULA),
           "source_commit": "a205e0c4",
           "wall_seconds": result["wall_seconds"],
           "sampled_peak_combined_rss_bytes": result["sampled_peak_combined_rss_bytes"],
           "source_sha256": {"protocol": sha(PROTOCOL),
                             "result": sha(folder / "result.json"),
                             "script": sha(__file__)}}
with (HERE / "terminal_audit.json").open("x") as out:
    json.dump(receipt, out, indent=2, sort_keys=True)
    out.write("\n")
print(json.dumps({"status": receipt["status"],
                  "query_status": result["status"]}))
