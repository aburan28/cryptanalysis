#!/usr/bin/env python3
"""Exact cardinality and storage audit for a literal seven-block N131 join."""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parent
source = root / "n131_w19_near_pair_geometry/result.json"
screen = json.loads(source.read_text())
local = json.loads((here / "protocol_v2.json").read_text())
if screen["status"] != "PASS" or screen["field_degree"] != 131:
    raise ValueError("N131 geometry status changed")
if local["source_mask_count"] != 32 or local["diagonal_blocks"] != 7:
    raise ValueError("N41 control changed")
q = screen["per_slot_usable_points_B"]
if q != 2 * screen["rational_source_masks"]:
    raise ValueError("signed source count changed")
order = int(screen["one_diagonal_pair_support_heuristic_denominator"])
left = q**3
right = q**4
pair = q**2
record = {
    "kind": "n131_seven_diagonal_literal_join_transfer",
    "status": "ARITHMETIC_AND_STORAGE_BOUND_ONLY",
    "curve_id": screen["curve_id"],
    "source_result_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "n41_protocol_v2_sha256": hashlib.sha256((here / "protocol_v2.json").read_bytes()).hexdigest(),
    "per_block_projected_point_count": q,
    "seven_block_actual_factor_base_points_B": None,
    "seven_block_folded_columns_K": None,
    "unrestricted_left_triples": left,
    "unrestricted_right_quadruples": right,
    "unrestricted_pair_states_per_pair": pair,
    "lower_bound_bytes_for_one_8_byte_key_per_left_triple": 8 * left,
    "minimum_full_join_probe_count": right,
    "uniform_group_expected_raw_tuples": str(Fraction(q**7, order)),
    "uniform_group_expected_raw_tuples_decimal": format(float(Fraction(q**7, order)), ".8f"),
    "method_boundary": "literal 3+4 join before column, orbit, or intermediate-equation constraints; no N131 target-coupled query",
}
path = here / "transfer_result.json"
if path.exists():
    raise FileExistsError(path)
path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": record["status"], "left": left, "right": right}))
