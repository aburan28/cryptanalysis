#!/usr/bin/env python3
"""Freeze width-18 Karatsuba PDP against the same public N83 target."""

import json
from pathlib import Path

from karatsuba import HERE, runner


ROOT = runner.ROOT
WIDTH = ROOT / "experiments/n83-geometric-width17-18-20261012"
PARENT = ROOT / "experiments/n83-geometric-m5-topology16-20261012"
PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
M5 = ROOT / "experiments/m5-s3-gate-20261004"
S3 = ROOT / "experiments/compact-s3-m4-20261003"
CODEGEN = ROOT / "ecc2k130/runner/codegen"


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    prior_path = PARENT / "protocol.json"
    prior_result_path = PARENT / "width16_ordinary.json"
    prior = json.loads(prior_path.read_text())
    assert prior["proposal_id"] == "Q2026101253"
    frontier_path = WIDTH / "frontier.json"
    replay_path = WIDTH / "independent_sage_replay.json"
    frontier = json.loads(frontier_path.read_text())
    replay = json.loads(replay_path.read_text())
    assert frontier["status"] == "complete_geometry_stage"
    assert replay["status"] == "PASS"
    assert [row["dimension"] for row in replay["results"]] == [17, 18]
    row = next(row for row in frontier["rows"] if row["dimension"] == 18)
    base_path = WIDTH / row["canonical_key_file"]
    assert runner.sha(base_path) == row["canonical_key_sha256"]
    cache_receipt_path = HERE / "materialization.json"
    cache_receipt = json.loads(cache_receipt_path.read_text())
    assert cache_receipt["status"] == "PASS"
    assert cache_receipt["K"] == row["folded_columns_K"]
    assert cache_receipt["B"] == row["actual_usable_points_B_before_folding"]
    cache_path = HERE / cache_receipt["canonical_x_file"]
    assert runner.sha(cache_path) == cache_receipt["canonical_x_sha256"]
    identity_path = PAIR / "runs/n83_knownlog_orbit_base_k48194.json"
    assert runner.sha(identity_path) == prior["curve_identity_sha256"]
    sources = [HERE / name for name in
               ("prepare.py", "base_run.py", "karatsuba.py", "ordinary.py",
                "control.py", "materialize.py")]
    sources += [M5 / "build_m5.py", M5 / "run_gate.py",
                S3 / "chain_s3.py", S3 / "chain_s3_multitarget.py",
                S3 / "cofactor_preimages.py", CODEGEN / "curves.py",
                CODEGEN / "field.py", PAIR / "orbit_key.py",
                ROOT / "experiments/n83-orbit-key-x-20261012/fast_x.py"]
    assert all(path.is_file() for path in sources)
    base_row = {
        "dimension": 18,
        "offset_onb_coordinates": 1 << 81,
        "K": row["folded_columns_K"],
        "B": row["actual_usable_points_B_before_folding"],
        "base_file": str(base_path.relative_to(ROOT)),
        "base_sha256": runner.sha(base_path),
        "canonical_x_cache_file": str(cache_path.relative_to(ROOT)),
        "canonical_x_cache_sha256": runner.sha(cache_path),
        "five_subset_first_moment": row["five_subset_first_moment"],
    }
    protocol = {
        **prior,
        "kind": "n83_shifted_width18_power_basis_karatsuba_five_summand_protocol",
        "proposal_id": "Q2026101254",
        "comparison_variable": (
            "expand the shifted affine factor base from width 16 to width 18 "
            "on the same curve and public target, retaining the three-product "
            "power-basis Karatsuba S3 link, fixed target slice and resource cap"),
        "method_comparison_parent": "Q2026101253 width-16 power-basis Karatsuba",
        "base_rows": [base_row],
        "leaf_domain": "first leaf is a width-18 affine seed; four other leaves independently select Frobenius powers; target is raw preimage choice zero",
        "run_order": [18],
        "parent_frontier_sha256": runner.sha(frontier_path),
        "parent_sage_replay_sha256": runner.sha(replay_path),
        "parent_karatsuba_protocol_sha256": runner.sha(prior_path),
        "parent_karatsuba_result_sha256": runner.sha(prior_result_path),
        "cache_materialization_sha256": runner.sha(cache_receipt_path),
        "source_sha256": {str(path.relative_to(ROOT)): runner.sha(path)
                          for path in sources},
    }
    runner.save(output, protocol)
    print(json.dumps({"status": "frozen", "proposal_id": protocol["proposal_id"],
                      "workload_id": protocol["workload_id"],
                      "B": base_row["B"], "K": base_row["K"]}), flush=True)


if __name__ == "__main__":
    main()
