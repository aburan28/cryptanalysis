#!/usr/bin/env python3
"""Test exact sparse-x rationality clauses on the same n53 public target."""

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path

import run_multitarget_probe
from chain_s3_rational import build_rational_multitarget
from run_probe import HERE, sha


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args, _ = parser.parse_known_args()
    assert args.n == 53 and args.kind in ("planted", "ordinary")
    assert not args.out.exists()
    supports_path = HERE / "bases/n53_weight3_nonrational_supports.json.gz"
    with gzip.open(supports_path, "rt") as stream:
        supports = json.load(stream)
    packed = base64.b64decode(supports["nonrational_supports_base64"],
                              validate=True)
    assert hashlib.sha256(packed).hexdigest() == supports[
        "nonrational_supports_sha256"]
    invalid = [int.from_bytes(packed[index:index + 7], "little")
               for index in range(0, len(packed), 7)]
    assert len(invalid) == supports["nonrational_x_masks"] == 12826
    assert len(set(invalid)) == len(invalid)

    def build(n, weight, xs):
        assert n == 53 and weight == 3
        return build_rational_multitarget(n, weight, xs, invalid)

    run_multitarget_probe.build_multitarget = build
    run_multitarget_probe.main()
    receipt = json.loads(args.out.read_text())
    assert receipt["proposal_id"] == "Q1306"
    receipt["kind"] = "full_cofactor_preimage_rational_filtered_s3_stage_probe"
    receipt["baseline_proposal_id"] = receipt["proposal_id"]
    receipt["proposal_id"] = "Q1308"
    receipt["rational_filter_source_sha256"] = sha(
        HERE / "chain_s3_rational.py")
    receipt["rational_support_archive_sha256"] = sha(supports_path)
    receipt["rational_support_digest_sha256"] = supports[
        "nonrational_supports_sha256"]
    receipt["rational_support_invalid_count"] = len(invalid)
    receipt["wrapper_source_sha256"] = sha(Path(__file__))
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"n": 53, "kind": args.kind,
                      "status": receipt["attempts"][-1]["status"],
                      "verified_relation": receipt["verified_relation"] is not None,
                      "formula_clauses": receipt["formula_cnf_clauses"],
                      "conflicts": receipt["attempts"][0][
                          "solver_conflicts_reported"],
                      "target_pdp_wall_seconds":
                      receipt["target_pdp_wall_seconds"]}))


if __name__ == "__main__":
    main()
