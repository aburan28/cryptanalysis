"""Bind a factor-base-count correction to the immutable N131 query receipt."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
RUN = GOAL / "n131_w15_basis_aware_fivepair_20261011"
SOURCE = GOAL / "n131_w15_coupled_sixpair_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((RUN / "protocol.json").read_text())
    query = json.loads((RUN / "query_result.json").read_text())
    audit = json.loads((RUN / "terminal_audit.json").read_text())
    source_protocol = json.loads((SOURCE / "protocol.json").read_text())
    support = json.loads((SOURCE / "support_receipt.json").read_text())
    group = json.loads((SOURCE / "sage_group_audit.json").read_text())
    assert protocol["factor_base_B"] == support["rational_masks"] == 16441
    assert source_protocol["actual_projected_factor_base_B"] == 197292
    assert support["actual_subgroup_factor_base_points_B"] == 197292
    assert group["actual_subgroup_factor_base_points_B"] == 197292
    assert protocol["folded_columns_K"] == support["folded_columns_K"] == 16381
    assert source_protocol["curve_id"] == protocol["curve_id"]
    assert audit["public_target_q"] == query["target"] == protocol["public_target_q"]
    assert query["protocol_sha256"] == sha(RUN / "protocol.json")
    record = {"status": "PASS_N131_W15_FACTOR_BASE_METADATA_CORRECTION",
              "affected_run_protocol_sha256": sha(RUN / "protocol.json"),
              "affected_run_query_sha256": sha(RUN / "query_result.json"),
              "curve_id": protocol["curve_id"],
              "incorrect_protocol_field": {"factor_base_B": 16441},
              "corrected_fields": {"actual_subgroup_usable_factor_base_B": 197292,
                                   "rational_masks_per_window": 16441,
                                   "folded_columns_K": 16381},
              "query_status": query["status"],
              "source_sha256": {"support_receipt.json": sha(SOURCE / "support_receipt.json"),
                                "sage_group_audit.json": sha(SOURCE / "sage_group_audit.json"),
                                "source_protocol.json": sha(SOURCE / "protocol.json")}}
    (HERE / "correction.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": record["status"],
                      "correct_B": record["corrected_fields"]["actual_subgroup_usable_factor_base_B"]}))


if __name__ == "__main__":
    main()
