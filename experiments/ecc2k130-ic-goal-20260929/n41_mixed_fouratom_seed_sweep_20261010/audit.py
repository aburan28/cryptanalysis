#!/usr/bin/env python3
"""Bind the corrected sweep and classify the two predecessor gates."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "mixed_fouratom_seed_sat_20261010"
SCREEN = ROOT / "n41_n131_diagonal_atom_20261010/screen.json"
MIXED = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


result = json.loads((HERE / "result.json").read_text())
protocol = json.loads((HERE / "protocol.json").read_text())
screen = json.loads(SCREEN.read_text())
panel = json.loads(MIXED.read_text())["panels"]["41"]
old_result = json.loads((OLD / "result.json").read_text())
old_seed_result = json.loads((OLD / "seed_result.json").read_text())
old_protocol = json.loads((OLD / "protocol.json").read_text())

assert result["protocol_sha256"] == sha(HERE / "protocol.json")
assert result["status"] == "PASS_EXACT_N41_RAW_ATOM_SEED_SWEEP"
assert result["cases"]["positive"]["algebraic_hit_seeds"] == [1]
assert result["cases"]["trace_zero_control"]["algebraic_hit_seeds"] == []
assert result["cases"]["positive"]["product_matches"] == 1
assert result["cases"]["trace_zero_control"]["product_matches"] == 0
assert any(hit["raw_sum"] == panel["raw_sum"] and
           hit["projected_sum"] == panel["projected_sum"]
           for hit in result["cases"]["positive"]["group_hits"])
assert result["source_sha256"] == protocol["source_sha256"]

# The earlier comparator summed subgroup atoms, whereas the S3 inverse
# and its constructed witness concern raw diagonal atoms.
subgroup_x = next(row["point"][0] for row in screen["slots"][0]
                  if row["mask"] == 2)
raw_x = next(row["raw_pair_point"][0] for row in screen["raw_audit"]
             if row["mask"] == 2)
old_lines = (ROOT / "n41_upper_xor_projection_20261010/w6_input.txt").read_text().splitlines()
old_x = next(int(line.split()[0]) for line in old_lines[2:66]
             if int(line.split()[2]) == 2)
assert old_x == subgroup_x != raw_x
assert old_seed_result["status"] == "PASS_EXACT_N41_MIXED_ALLSEED_PANEL"

sat_rows = []
for row in old_result["rows"]:
    case = row["case"]
    stdout = OLD / f"n41_{case}.solver.stdout.txt"
    stderr = OLD / f"n41_{case}.solver.stderr.txt"
    assert sha(stdout) == row["solver_stdout_sha256"]
    assert sha(stderr) == row["solver_stderr_sha256"]
    assert "s INDETERMINATE" in stdout.read_text().splitlines()
    assert row["returncode"] == 15 and row["model_literal_count"] == 0
    assert row["formula_sha256"] == sha(OLD / f"n41_{case}.xcnf")
    sat_rows.append({"case": case, "status": "CENSORED_TIME",
                     "solver_status": "INDETERMINATE",
                     "formula_sha256": row["formula_sha256"],
                     "solver_stdout_sha256": sha(stdout),
                     "parent_wall_ns": row["parent_wall_ns"],
                     "peak_solver_rss_bytes": row["peak_solver_rss_bytes"]})
assert old_protocol["cases"]["positive"]["complete_constructed_assignment"] == {
    "cnf_clauses": 6283, "xor_rows": 1638}

audit = {"status": "PASS_CORRECTED_RAW_ATOM_SWEEP_AUDIT",
         "candidate_id": None, "run_id": None,
         "source_sha256": {"audit.py": sha(Path(__file__)),
                           "protocol.json": sha(HERE / "protocol.json"),
                           "result.json": sha(HERE / "result.json"),
                           "screen.json": sha(SCREEN),
                           "mixed_inputs.json": sha(MIXED),
                           "predecessor_protocol.json": sha(OLD / "protocol.json"),
                           "predecessor_result.json": sha(OLD / "result.json"),
                           "predecessor_seed_protocol.json": sha(OLD / "seed_protocol.json"),
                           "predecessor_seed_result.json": sha(OLD / "seed_result.json")},
         "corrected": {"positive_seed": 1,
                       "positive_group_hits": len(result["cases"]["positive"]["group_hits"]),
                       "control_group_hits": len(result["cases"]["trace_zero_control"]["group_hits"]),
                       "raw_mask2_x": raw_x,
                       "subgroup_mask2_x": subgroup_x},
         "predecessor_seed_sweep": {"status": "PRODUCER_FAILURE_WRONG_POINT_DOMAIN",
                                    "old_input_mask2_x": old_x},
         "predecessor_sat": sat_rows}
(HERE / "terminal_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": audit["status"],
                  "sat_statuses": [v["status"] for v in sat_rows]}, sort_keys=True))
