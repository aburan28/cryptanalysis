#!/usr/bin/env python3
"""Retain an independent full Q1041 base replay for the Q1324 comparison."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from q1324_inputs import Q1041, read_inputs
from run_probe import HERE, sha

sys.path.insert(0, str(Q1041))
from verify_n83_base import verify  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = HERE / "runs/n83_q1324_q1041_full_base_verification.json"
    runtime_path = HERE / "q1324_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    base_path, base, key_path, _, _, _, x_digest = read_inputs()
    checked = verify()
    assert checked["actual_B"] == base["factor_base"][
        "actual_usable_points_B_before_folding"] == 4000102
    assert checked["folded_columns"] == base["factor_base"][
        "signed_frobenius_columns"] == 24097
    assert checked["verified_projected_representatives"] == 24097
    receipt = {
        "kind": "q1324_independent_full_q1041_base_replay",
        "proposal_id": "Q1324",
        "candidate_id": None,
        "curve_id": checked["curve_id"],
        "isogeny": "none",
        "status": "PASS",
        "actual_usable_points_B_before_folding": checked["actual_B"],
        "signed_frobenius_columns": checked["folded_columns"],
        "verified_projected_representatives": checked[
            "verified_projected_representatives"],
        "factor_base_enumerated_set_sha256": base["factor_base"][
            "enumerated_set_sha256"],
        "derived_representative_x_sha256": x_digest,
        "base_receipt_sha256": sha(base_path),
        "point_key_file_sha256": sha(key_path),
        "q1041_verifier_source_sha256": sha(Q1041 / "verify_n83_base.py"),
        "q1324_input_source_sha256": sha(HERE / "q1324_inputs.py"),
        "runtime_info_sha256": sha(runtime_path),
        "source_sha256": sha(Path(__file__)),
    }
    content = json.dumps(receipt, indent=2) + "\n"
    if args.check:
        assert output.read_text() == content
    else:
        assert not output.exists()
        output.write_text(content)
    print(json.dumps({"status": receipt["status"],
                      "verified_representatives": checked[
                          "verified_projected_representatives"]}))


if __name__ == "__main__":
    main()
