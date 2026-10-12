#!/usr/bin/env python3
"""Freeze N83 W<=6 balanced-S3 control and ordinary CNFs on Q1408 points."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(STAGE))
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from run_q1325_full_weight5_probe import pin_bits  # noqa: E402
from q20261010_insearch_root.prepare import lower  # noqa: E402
from chain_s3 import field  # noqa: E402

OUT = HERE / "inputs.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(mode: str, protocol: dict) -> dict:
    label = "ordinary" if mode == "ordinary" else "planted_locked"
    record_path = STAGE / "runs" / f"n83_q1408_{label}.json"
    record = json.loads(record_path.read_text())
    assert record["curve_id"] == protocol["curve_id"]
    assert record["isogeny"] == "none"
    if mode == "ordinary":
        assert record["workload_id"] == protocol["ordinary_workload_id"]
    target = STAGE / "q20261010_final_link" / f"n83_{mode}.targets"
    target_manifest = json.loads(target.with_suffix(".targets.json").read_text())
    assert target_manifest["curve_id"] == protocol["curve_id"]
    assert target_manifest["workload_id"] == record["workload_id"]
    formula, leaves, mids, _, selector = build_balanced(
        83, 6, record["raw_preimage_x_coordinates"])
    if mode == "control":
        fixture = record["fixture"]
        assert fixture is not None
        for bits, value in zip(leaves, fixture["raw_leaf_x"]):
            pin_bits(formula, bits, value)
        onb = field.Onb(83)
        for bits, point in zip(mids, fixture["raw_pair_sum_points"]):
            pin_bits(formula, bits, onb.toCoords(int(point[0])))
        raw_sum = fixture["raw_sum"]
        selected = record["raw_preimage_x_coordinates"].index(
            onb.toCoords(int(raw_sum[0])))
        pin_bits(formula, selector, selected)
    prefix = Path(f"/private/tmp/q1449_n83_{mode}")
    xcnf = prefix.with_suffix(".xcnf")
    cnf = prefix.with_suffix(".cnf")
    mapping = prefix.with_suffix(".map")
    assert not xcnf.exists() and not cnf.exists() and not mapping.exists()
    formula.write(xcnf)
    clauses = list(lower(formula))
    vars_used = max((abs(lit) for row in clauses for lit in row), default=0)
    with cnf.open("w") as output:
        output.write(f"p cnf {vars_used} {len(clauses)}\n")
        for row in clauses:
            output.write(" ".join(map(str, row)) + " 0\n")
    with mapping.open("w") as output:
        output.write("83\n")
        for bits in (*leaves, *mids):
            output.write(" ".join(map(str, bits)) + "\n")
    return {
        "mode": mode,
        "curve_id": record["curve_id"],
        "workload_id": record["workload_id"],
        "isogeny": "none",
        "source_q1408_record_sha256": sha(record_path),
        "public_target": record["public_target"],
        "raw_target_preimage_x_coordinates": record["raw_preimage_x_coordinates"],
        "target_file": str(target),
        "target_file_sha256": sha(target),
        "target_manifest_sha256": sha(target.with_suffix(".targets.json")),
        "cnf_file": str(cnf), "cnf_sha256": sha(cnf),
        "cnf_variables": vars_used, "cnf_clauses": len(clauses),
        "xcnf_file": str(xcnf), "xcnf_sha256": sha(xcnf),
        "xcnf_variables": formula.variables,
        "xcnf_clauses": len(formula.clauses),
        "xcnf_xor_rows": len(formula.xors),
        "map_file": str(mapping), "map_sha256": sha(mapping),
        "leaf_weight_bound": 6,
        "fixture_raw_leaf_x": record["fixture"]["raw_leaf_x"]
        if mode == "control" else None,
    }


def main() -> None:
    assert not OUT.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["proposal_id"] == "Q1449"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    rows = [one("control", protocol), one("ordinary", protocol)]
    record = {
        "proposal_id": "Q1449",
        "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "ordinary_workload_id": protocol["ordinary_workload_id"],
        "isogeny": "none",
        "factor_base_actual_B": None,
        "factor_base_folded_columns_K": None,
        "factor_base_enumerated_set_sha256": None,
        "formula_rows": rows,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "prepare_source_sha256": sha(Path(__file__)),
        "builder_source_sha256": sha(STAGE / "chain_s3_balanced_multitarget.py"),
        "lowering_source_sha256": sha(STAGE / "q20261010_insearch_root/prepare.py"),
        "pin_source_sha256": sha(STAGE / "run_q1325_full_weight5_probe.py"),
        "field_source_sha256": sha(Path(field.__file__)),
    }
    OUT.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN",
                      "ordinary_cnf_sha256": rows[1]["cnf_sha256"],
                      "ordinary_cnf_clauses": rows[1]["cnf_clauses"]}))


if __name__ == "__main__":
    main()
