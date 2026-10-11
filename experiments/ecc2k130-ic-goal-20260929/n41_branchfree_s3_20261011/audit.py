"""Bind the W9 branch-free and guarded public-query receipts."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
W9 = HERE.parent / "n41_w7_entropy_cubic_20261011/w9"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


identity = load(HERE / "identity_check.json")
assert identity["status"] == "PASS_BRANCHFREE_S3_FIELD_IDENTITY_CHECK"
assert identity["source_sha256"] == sha(HERE / "identity_check.py")
assert identity["fixture_sha256"] == sha(W9 / "fixture.json")
assert identity["fixture_link_count"] == 7 and identity["all_fixture_links_valid"]
assert identity["random_triples_checked"] == 1024
prior = load(W9 / "query/query_result.json")
prior_protocol = load(W9 / "query/protocol.json")
assert prior["status"] == "BOUNDED_UNKNOWN"


def audit_variant(directory, name):
    run = directory / "query"
    protocol = load(run / "protocol.json")
    control = load(run / "control_result.json")
    query = load(run / "query_result.json")
    assert protocol["candidate_id"] is None
    assert protocol["public_target_original"] == prior_protocol["public_target_original"]
    assert protocol["public_target_transported"] == prior_protocol["public_target_transported"]
    assert protocol["raw_target_preimage_z"] == prior_protocol["raw_target_preimage_z"]
    assert protocol["factor_base_B"] == 2072
    assert protocol["folded_columns_K"] == 251
    assert protocol["workers"] == 1
    assert protocol["solver_cap_seconds"] == 120
    assert protocol["rss_cap_bytes"] == 4 * 1024**3
    assert protocol["solver_flags"] == prior_protocol["solver_flags"]
    assert protocol["source_sha256"][f"{name}_circuit"] == sha(directory / "circuit.py")
    assert protocol["source_sha256"][f"{name}_runner"] == sha(directory / "run.py")
    assert control["status"] == "PASS_FULL_N41_TRANSPORTED_EIGHT_SLOT_ASSIGNMENT"
    assert control["assignment_check"]["clauses"] == control["formula"]["clauses"]
    assert control["assignment_check"]["native_xor_rows"] == control["formula"]["native_xor_rows"]
    assert control["protocol_sha256"] == sha(run / "protocol.json")
    assert query["status"] == "BOUNDED_UNKNOWN" and query["solver_started"]
    assert query["solver_timed_out"] and not query["solver_rss_exceeded"]
    assert query["peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    assert query["protocol_sha256"] == sha(run / "protocol.json")
    phase = query["phase_seconds"]
    assert phase["total"] >= phase["construction"] + phase["write_and_hash"] + phase["solver"]
    stdout = gzip.open(run / "solver.stdout.gz", "rb").read()
    stderr = gzip.open(run / "solver.stderr.gz", "rb").read()
    assert hashlib.sha256(stdout).hexdigest() == query["stdout_sha256"]
    assert hashlib.sha256(stderr).hexdigest() == query["stderr_sha256"]
    assert b"c rst" in stdout
    assert b"s SATISFIABLE" not in stdout and b"s UNSATISFIABLE" not in stdout
    return {"variant": name, "status": query["status"],
            "variables": query["formula"]["variables"],
            "and_gates": query["formula"]["and_gates"],
            "clauses": query["formula"]["clauses"],
            "native_xor_rows": query["formula"]["native_xor_rows"],
            "formula_bytes": query["formula"]["bytes"],
            "solver_seconds": phase["solver"],
            "peak_combined_rss_bytes": query["peak_combined_rss_bytes"],
            "active_restart_lines": sum(line.startswith(b"c rst") for line in stdout.splitlines()),
            "sha256": {"protocol": sha(run / "protocol.json"),
                       "control": sha(run / "control_result.json"),
                       "query": sha(run / "query_result.json")}}


first = audit_variant(HERE, "branchfree")
guarded = audit_variant(HERE / "guarded", "guarded")
full = load(HERE / "guarded/full_assignment.json")
assert full["status"] == "PASS_GUARDED_FOUR_PREIMAGE_ASSIGNMENT"
assert full["sha256"]["source"] == sha(HERE / "guarded/control_full.py")
assert full["sha256"]["circuit"] == sha(HERE / "guarded/circuit.py")
assert full["sha256"]["protocol"] == sha(HERE / "guarded/query/protocol.json")
assert full["records"][full["known_raw_preimage_index"]]["failed_clauses"] == 0
assert all(row["failed_native_xor_rows"] == 0 for row in full["records"])
assert prior["formula"]["and_gates"] - guarded["and_gates"] == 705
assert prior["formula"]["clauses"] - guarded["clauses"] == 1999
out = {"status": "PASS_N41_W9_BRANCHFREE_AND_GUARDED_AUDIT",
       "candidate_id": None,
       "prior_w9": {"variables": prior["formula"]["variables"],
                    "and_gates": prior["formula"]["and_gates"],
                    "clauses": prior["formula"]["clauses"],
                    "native_xor_rows": prior["formula"]["native_xor_rows"],
                    "formula_bytes": prior["formula"]["bytes"],
                    "query_sha256": sha(W9 / "query/query_result.json")},
       "variants": [first, guarded],
       "sha256": {"identity": sha(HERE / "identity_check.json"),
                  "guarded_full_assignment": sha(HERE / "guarded/full_assignment.json")}}
(HERE / "audit.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], [(v["variant"], v["status"]) for v in out["variants"]])
