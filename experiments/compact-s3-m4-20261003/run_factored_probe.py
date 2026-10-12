#!/usr/bin/env python3
"""Run the three-product S3 variant on the baseline's exact frozen workload."""

import argparse
import json
from pathlib import Path

import run_probe
from chain_s3_factored import build_factored


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args, _ = parser.parse_known_args()
    assert args.n in (53, 83)
    assert args.kind in ("planted", "ordinary")
    assert not args.out.exists()
    baseline_path = run_probe.HERE / "runs" / (
        f"n{args.n}_{args.kind}_frozen.json")
    baseline = json.loads(baseline_path.read_text())
    run_probe.build = build_factored
    run_probe.main()
    receipt = json.loads(args.out.read_text())
    assert receipt["curve_id"] == baseline["curve_id"]
    assert receipt["protocol_sha256"] == baseline["protocol_sha256"]
    assert receipt["factor_base_enumerated_set_sha256"] == baseline[
        "factor_base_enumerated_set_sha256"]
    assert receipt["seed"] == baseline["seed"]
    assert receipt["raw_target"] == baseline["raw_target"]
    assert receipt["public_subgroup_target"] == baseline[
        "public_subgroup_target"]
    assert receipt["solver_command_budget_seconds"] == baseline[
        "solver_command_budget_seconds"]
    assert receipt["solver_command_budget_conflicts_per_attempt"] == (
        baseline["solver_command_budget_conflicts_per_attempt"])
    receipt["kind"] = "factored_three_product_s3_chain_stage_probe"
    receipt["baseline_proposal_id"] = receipt["proposal_id"]
    receipt["proposal_id"] = {53: "Q1304", 83: "Q1305"}[args.n]
    receipt["matched_baseline_receipt_sha256"] = run_probe.sha(baseline_path)
    receipt["core_formula_source_sha256"] = receipt.pop("solver_source_sha256")
    receipt["solver_source_sha256"] = run_probe.sha(
        run_probe.HERE / "chain_s3_factored.py")
    receipt["wrapper_source_sha256"] = run_probe.sha(Path(__file__))
    receipt["encoding_identity"] = (
        "ab=product(a,b); s=a+b; cross=product(s,c); "
        "abc=product(ab,c); square(ab+cross)+abc+1=0")
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"proposal_id": receipt["proposal_id"],
                      "n": args.n, "kind": args.kind,
                      "status": receipt["attempts"][-1]["status"],
                      "verified_relation": bool(receipt["verified_relation"]),
                      "variables": receipt["formula_variables"],
                      "and_gates": receipt["formula_and_gates"],
                      "pdp_wall_seconds": receipt["target_pdp_wall_seconds"]}))


if __name__ == "__main__":
    main()
