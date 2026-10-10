#!/usr/bin/env python3
"""Independently check retained public timeout and seven-block join receipts."""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

here = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
public = json.loads((here / "public/result.json").read_text())
protocol = json.loads((here / "protocol_v2.json").read_text())
assert public["status"] == "CENSORED_TIME"
assert public["stop_reason"] == "SOLVER_WALL_CAP"
assert public["model_lines"] == 0 and public["solver_status_lines"] == []
assert public["solver_exit_code"] == -15
assert public["phase_seconds"]["online_wall"] <= protocol["online_cap_seconds"]
assert public["source_sha256"] == {
    "protocol": sha(here / "protocol_v2.json"),
    "formula": sha(here / "public/system.xcnf"),
    "stdout": sha(here / "public/solver.stdout.txt"),
    "stderr": sha(here / "public/solver.stderr.txt"),
    "process": sha(here / "public/process.json"),
}
assert public["formula"]["sha256"] == sha(here / "public/system.xcnf")
assert public["solver_command"][4] == "--random=20261009"
assert public["verified_relations"] == public["useful_rank"] == 0
transfer = json.loads((here / "transfer_result.json").read_text())
geometry_path = here.parent / "n131_w19_near_pair_geometry/result.json"
geometry = json.loads(geometry_path.read_text())
q = 2 * geometry["rational_source_masks"]
order = int(geometry["one_diagonal_pair_support_heuristic_denominator"])
assert transfer["source_result_sha256"] == sha(geometry_path)
assert transfer["n41_protocol_v2_sha256"] == sha(here / "protocol_v2.json")
assert transfer["per_block_projected_point_count"] == q
assert transfer["unrestricted_left_triples"] == q**3
assert transfer["unrestricted_right_quadruples"] == q**4
assert transfer["lower_bound_bytes_for_one_8_byte_key_per_left_triple"] == 8*q**3
assert Fraction(transfer["uniform_group_expected_raw_tuples"]) == Fraction(q**7, order)
result = {"status": "PASS_PUBLIC_TERMINAL_AND_TRANSFER_ARITHMETIC",
          "public_status": public["status"],
          "public_online_seconds": public["phase_seconds"]["online_wall"],
          "n131_left_key_lower_bound_bytes": 8*q**3}
path = here / "terminal_audit.json"
if path.exists():
    raise FileExistsError(path)
path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result))
