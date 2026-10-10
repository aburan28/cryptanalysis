#!/usr/bin/env python3
"""Bind N131 framed construction, Sage control, and bounded public search."""
import gzip
import hashlib
import json
from pathlib import Path

import query

HERE = Path(__file__).resolve().parent
sha = query.run.sha


def uncompressed_sha(path):
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


protocol = json.loads((HERE / "query_protocol.json").read_text())
construction = json.loads((HERE / "profile.json").read_text())
sage = json.loads((HERE / "sage_audit.json").read_text())
folder = HERE / "public_query"
process = json.loads((folder / "process.json").read_text())
result = json.loads((folder / "result.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_PUBLISHED_POINT_QUERY"
assert protocol["source_sha256"] == {name: sha(path)
                                       for name, path in query.sources().items()}
assert construction["status"] == "PASS_FULL_FORMULA_CONSTRUCTED_GROUP_WITNESS"
assert construction["formula"]["sha256"] == uncompressed_sha(HERE / "constructed_full.xcnf.gz")
assert construction["full_xcnf_assignment_check"] == {
    "cnf_clauses": construction["formula"]["clauses"],
    "xor_rows": construction["formula"]["xor_rows"]}
assert sage["status"] == "PASS_INDEPENDENT_SAGE_N131_GROUP_AND_FRAME_REPLAY"
assert result["public_target_q_polynomial"] == protocol["public_target_q_polynomial"]
assert result["formula"]["sha256"] == uncompressed_sha(folder / "system.xcnf.gz")
assert result["status"] == "CENSORED_TIME"
assert result["stop_reason"] == "SOLVER_WALL_CAP"
assert result["solver_status_lines"] == [] and result["model_lines"] == 0
assert result["phase_seconds"]["online_wall"] <= protocol["online_wall_cap_seconds"]
assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
assert process["protocol_sha256"] == result["source_sha256"]["protocol"] == sha(query.PROTOCOL)
for label, path in (("stdout", folder / "solver.stdout.txt"),
                    ("stderr", folder / "solver.stderr.txt"),
                    ("process", folder / "process.json")):
    assert result["source_sha256"][label] == sha(path)
assert (folder / "solver.stderr.txt").stat().st_size == 0
stdout = (folder / "solver.stdout.txt").read_text()
assert "c rst" in stdout and "K" in stdout
record = {"status": "PASS_FROZEN_N131_FRAME_CONTROL_AND_PUBLIC_QUERY_AUDIT",
          "query_status": result["status"],
          "source_commit": "3cee6225",
          "curve_id": protocol["curve_id"],
          "public_target_q_polynomial": protocol["public_target_q_polynomial"],
          "constructed_formula_sha256": construction["formula"]["sha256"],
          "public_formula_sha256": result["formula"]["sha256"],
          "online_wall_seconds": result["phase_seconds"]["online_wall"],
          "sampled_peak_combined_rss_bytes": result["sampled_peak_combined_rss_bytes"],
          "source_sha256": {"script": sha(__file__),
                            "protocol": sha(query.PROTOCOL),
                            "construction": sha(HERE / "profile.json"),
                            "sage": sha(HERE / "sage_audit.json"),
                            "result": sha(folder / "result.json")}}
receipt = HERE / "terminal_audit.json"
if receipt.exists():
    assert json.loads(receipt.read_text()) == record
else:
    with receipt.open("x") as out:
        json.dump(record, out, indent=2, sort_keys=True)
        out.write("\n")
print(json.dumps({"status": record["status"],
                  "query_status": record["query_status"]}))
