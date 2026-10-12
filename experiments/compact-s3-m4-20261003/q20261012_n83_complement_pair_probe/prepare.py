#!/usr/bin/env python3
"""Freeze ordinary N83 complements from exact Q1497 first-pair outputs."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parent.parent
sys.path.insert(0, str(PARENT / "q20261011_operation_account"))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
from counted_onb import CountedOnb
from curves import Curve


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    out = HERE / "frozen_inputs.json"
    assert not out.exists()
    onb, curve = CountedOnb(83), None
    curve = Curve(onb)
    base = PARENT / "bases/n83_weight5_full_orbits.json"
    inputs = {}
    for label in ("selected", "holdout"):
        first_dir = ("q20261012_n83_restart_hyperparams" if label == "selected"
                     else "q20261012_n83_distinct_restart_holdout")
        first = PARENT / first_dir / "runs" / f"{label}_phase50/receipt.json"
        target = (PARENT / ("q20261011_wdsat_phase_restart" if label == "selected"
                            else "q20261011_n83_selector_holdout") / "target.json")
        row, fixture = read(first), read(target)
        assert row["exact_usable_first_pair"] and row["workload_id"] == fixture["workload_id"]
        bits = row["first_pair_bits"]
        leaves = []
        for j in range(2):
            coords = int(bits[j * 83:(j + 1) * 83][::-1], 2)
            p = curve.pointFromX(onb.fromCoords(coords))
            assert p is not None
            p = curve.mul(p, 4)
            assert p is not None and curve.onCurve(p)
            leaves.append(p)
        t = tuple(fixture["public_target"])
        assert curve.onCurve(t)
        complements = []
        for s0 in (1, -1):
            for s1 in (1, -1):
                p0 = leaves[0] if s0 == 1 else curve.neg(leaves[0])
                p1 = leaves[1] if s1 == 1 else curve.neg(leaves[1])
                r = curve.add(t, curve.neg(curve.add(p0, p1)))
                assert r is not None and curve.onCurve(r)
                assert curve.add(curve.add(p0, p1), r) == t
                complements.append({"signs": [s0, s1],
                                    "x_onb_hex": format(onb.toCoords(r[0]), "x"),
                                    "y_onb_hex": format(onb.toCoords(r[1]), "x")})
        inputs[label] = {"workload_id": row["workload_id"],
                         "first_pair_receipt_sha256": digest(first),
                         "target_receipt_sha256": digest(target),
                         "first_pair_combined_calls": row["first_pair_combined_calls"],
                         "complements": complements}
    data = {"proposal_id": "Q1501", "candidate_id": None, "run_id": None,
            "curve_id": "EC1N83Ckb1h876c2921cb64",
            "factor_base_actual_B": 30977592,
            "factor_base_folded_columns_K": 186612,
            "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
            "prepare_source_sha256": digest(Path(__file__)),
            "native_source_sha256": digest(HERE / "native_probe.cpp"),
            "base_point_file_sha256": digest(PARENT / "bases/n83_weight5_full_point_orbits.bin"),
            "inputs": inputs,
            "scan_limit_per_complement": 1000000,
            "batch_sizes": [512, 2048],
            "host_isolation": "none; throughput exploratory",
            "complete_n83_decomposition_work_log2": None,
            "complete_n131_solve_work_log2": None}
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(digest(out))


if __name__ == "__main__":
    main()
