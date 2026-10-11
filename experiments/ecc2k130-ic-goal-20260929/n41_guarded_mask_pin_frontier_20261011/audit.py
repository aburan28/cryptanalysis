"""Bind guarded W9 mask-pin diagnostic and matched-cap positive control."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARDED = HERE.parent / "n41_branchfree_s3_20261011/guarded"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


protocol = load(HERE / "protocol.json")
result = load(HERE / "result.json")
long_protocol = load(HERE / "long_pin8_protocol.json")
long_result = load(HERE / "long_pin8_result.json")
base_protocol = load(GUARDED / "query/protocol.json")
base_control = load(GUARDED / "full_assignment.json")
base_query = load(GUARDED / "query/query_result.json")
assert protocol["status"] == "FROZEN_GUARDED_N41_W9_MASK_PIN_FRONTIER"
assert result["status"] == "COMPLETE_GUARDED_MASK_PIN_FRONTIER"
assert long_protocol["status"] == "FROZEN_GUARDED_N41_W9_LONG_PIN8_CONTROL"
assert base_control["status"] == "PASS_GUARDED_FOUR_PREIMAGE_ASSIGNMENT"
assert base_query["status"] == "BOUNDED_UNKNOWN"
assert protocol["public_target_original"] == base_protocol["public_target_original"]
assert protocol["raw_target_preimage_z"] == base_protocol["raw_target_preimage_z"]
assert long_protocol["public_target_original"] == protocol["public_target_original"]
assert long_protocol["known_masks"] == protocol["known_masks"]
assert result["protocol_sha256"] == sha(HERE / "protocol.json")
assert result["source_sha256"] == sha(HERE / "run.py")
assert protocol["source_sha256"]["runner"] == sha(HERE / "run.py")
assert protocol["source_sha256"]["guarded_circuit"] == sha(GUARDED / "circuit.py")
assert protocol["source_sha256"]["guarded_public_protocol"] == sha(GUARDED / "query/protocol.json")
assert protocol["source_sha256"]["guarded_full_control"] == sha(GUARDED / "full_assignment.json")
assert long_protocol["source_sha256"]["long_runner"] == sha(HERE / "run_long.py")
assert long_protocol["source_sha256"]["short_protocol"] == sha(HERE / "protocol.json")
assert long_result["protocol_sha256"] == sha(HERE / "long_pin8_protocol.json")
assert long_result["source_sha256"] == sha(HERE / "run_long.py")
assert protocol["pin_counts"] == [8, 6, 4, 2, 1]
assert len(result["rows"]) == 5
assert result["construction_seconds"] < protocol["construction_cap_seconds"]
assert result["total_wall_seconds"] >= result["construction_seconds"] + sum(
    row["solver_seconds"] + row["write_seconds"] for row in result["rows"])


def check_log(prefix, row):
    stdout = gzip.open(HERE / f"{prefix}.stdout.gz", "rb").read()
    stderr = gzip.open(HERE / f"{prefix}.stderr.gz", "rb").read()
    assert hashlib.sha256(stdout).hexdigest() == row["stdout_sha256"]
    assert hashlib.sha256(stderr).hexdigest() == row["stderr_sha256"]
    assert row["active_restart_lines"] == sum(line.startswith(b"c rst")
                                               for line in stdout.splitlines())
    assert row["active_restart_lines"] > 0
    assert b"s SATISFIABLE" not in stdout and b"s UNSATISFIABLE" not in stdout


for pin_count, row in zip(protocol["pin_counts"], result["rows"]):
    assert row["pin_count"] == pin_count
    assert row["pinned_bits"] == 9 * pin_count
    assert row["formula_clauses"] == base_query["formula"]["clauses"] + 9 * pin_count
    assert row["status"] == "BOUNDED_UNKNOWN" and row["solver_started"]
    assert row["solver_timed_out"] and not row["solver_rss_exceeded"]
    assert row["peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    check_log(f"pin{pin_count}", row)
assert long_result["status"] == "BOUNDED_UNKNOWN" and long_result["solver_started"]
assert long_result["solver_timed_out"] and not long_result["solver_rss_exceeded"]
assert long_result["formula_clauses"] == base_query["formula"]["clauses"] + 72
assert long_result["peak_combined_rss_bytes"] < long_protocol["rss_cap_bytes"]
assert long_result["solver_seconds"] > 120
check_log("long_pin8", long_result)
out = {"status": "PASS_N41_GUARDED_MASK_PIN_FRONTIER_AUDIT",
       "candidate_id": None,
       "short_cases": [{"pin_count": row["pin_count"],
                        "status": row["status"],
                        "solver_seconds": row["solver_seconds"],
                        "active_restart_lines": row["active_restart_lines"]}
                       for row in result["rows"]],
       "long_pin8": {"status": long_result["status"],
                     "solver_seconds": long_result["solver_seconds"],
                     "active_restart_lines": long_result["active_restart_lines"]},
       "sha256": {"protocol": sha(HERE / "protocol.json"),
                  "result": sha(HERE / "result.json"),
                  "long_protocol": sha(HERE / "long_pin8_protocol.json"),
                  "long_result": sha(HERE / "long_pin8_result.json")}}
(HERE / "audit.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], [row["status"] for row in result["rows"]],
      long_result["status"])
