#!/usr/bin/env python3
"""Freeze the exact raw target-x coset for Q1432 final-link checks."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--mode", choices=("ordinary", "control"), default="ordinary")
    args = parser.parse_args()
    n = args.degree
    source_name = {
        (53, "ordinary"): "n53_q1410_ordinary.json",
        (53, "control"): "n53_q1410_witness_locked.json",
        (83, "ordinary"): "n83_q1408_ordinary.json",
        (83, "control"): "n83_q1408_planted_locked.json",
    }[(n, args.mode)]
    source = STAGE / "runs" / source_name
    record = json.loads(source.read_text())
    expected = {
        53: ("EC1N53Ckb1hf77aab617904", 24062,
             "05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5"),
        83: ("EC1N83Ckb1h876c2921cb64", 30977592,
             "56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8"),
    }[n]
    assert (record["curve_id"], record["factor_base_actual_B"],
            record["factor_base_enumerated_set_sha256"]) == expected
    assert record["isogeny"] == "none"
    assert record["mode"] == ("ordinary" if args.mode == "ordinary" else
                              "witness_locked" if n == 53 else "planted_locked")
    if args.mode == "ordinary":
        assert record["workload_id"] == ("74f2979b3e68" if n == 53 else
                                         "bab50a1e5f66")
    else:
        assert record["workload_id"] is None
    targets = record["raw_preimage_x_coordinates"]
    assert len(targets) == len(set(targets)) == (428 if n == 53 else 4)
    assert all(0 <= value < (1 << n) for value in targets)
    path = HERE / f"n{n}_{args.mode}.targets"
    with path.open("w") as output:
        output.write(f"{n} {len(targets)} {record['curve_id']} {record['workload_id'] or 'none'}\n")
        for value in targets:
            output.write("".join("1" if value & (1 << bit) else "0"
                                 for bit in range(n)) + "\n")
    manifest = {
        "proposal_id": "Q1432", "candidate_id": None, "run_id": None,
        "mode": args.mode,
        "curve_id": record["curve_id"], "workload_id": record["workload_id"],
        "isogeny": "none", "degree": n,
        "factor_base_actual_B": record["factor_base_actual_B"],
        "factor_base_folded_columns": record["factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": record[
            "factor_base_enumerated_set_sha256"],
        "target_count": len(targets),
        "target_file_sha256": sha(path),
        "source_receipt_sha256": sha(source),
    }
    (HERE / f"n{n}_{args.mode}.targets.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
