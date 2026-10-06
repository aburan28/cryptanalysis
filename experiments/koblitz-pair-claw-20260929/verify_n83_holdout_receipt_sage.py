#!/usr/bin/env python3
"""Independently replay a fresh n=83 holdout receipt in checked Sage."""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import verify_n83_quotient_receipt_sage as verifier
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
SCREEN = HERE / "n83_full_spill_screen.json"
HOLDOUT = HERE / "n83_holdout_target_20261001.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(receipt_path, runtime_path):
    screen = json.loads(SCREEN.read_text())
    validate_reference(screen)
    holdout = json.loads(HOLDOUT.read_text())
    receipt = json.loads(receipt_path.read_text())
    assert holdout["curve_id"] == receipt["curve_id"] == screen["curve_id"]
    assert holdout["public_target"] == receipt["public_target"]
    assert holdout["workload_id"] == receipt["workload_id"]
    assert holdout["fixture_scalar_retained"] is False
    assert receipt["proposal_id"] == "Q1090"
    assert receipt["isogeny"] == "none"
    assert receipt["factor_base"]["enumerated_set_sha256"] == holdout[
        "factor_base_enumerated_set_sha256"]
    assert receipt["factor_base"]["actual_usable_points_B_before_folding"] == (
        holdout["actual_usable_points_B_before_folding"])
    adapted = dict(screen)
    adapted["public_target"] = holdout["public_target"]
    with tempfile.TemporaryDirectory() as temp:
        adapted_path = Path(temp) / "holdout_screen.json"
        adapted_path.write_text(json.dumps(adapted, indent=2) + "\n")
        verifier.SCREEN = adapted_path
        result = verifier.verify(receipt_path, runtime_path)
        result["holdout_screen_sha256"] = result.pop("Q1062_screen_sha256")
    result.update({
        "kind": "n83_holdout_independent_sage_replay",
        "workload_id": holdout["workload_id"],
        "holdout_target_sha256": sha(HOLDOUT),
        "factor_base_screen_sha256": sha(SCREEN),
        "upstream_verifier_source_sha256": sha(Path(verifier.__file__)),
        "source_sha256": sha(Path(__file__)),
    })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite verification receipt"
    result = verify(args.receipt, args.runtime_info)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"workload_id": result["workload_id"],
                      "verified_relations": result["verified_relation_count"],
                      "out": str(args.out)}))


if __name__ == "__main__":
    main()
