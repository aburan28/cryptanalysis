#!/usr/bin/env python3
"""Verify bucket-norm receipts and independently replay the group witness."""

import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE / "n41_two_free_pair_occupancy_20261009"))
from arithmetic_snapshot import Curve, Field  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(expected, path):
    if expected != sha(path):
        raise AssertionError("digest mismatch: " + str(path))


def phases(row, keys):
    if sum(row[key] for key in keys) != row["online_wall_ns"]:
        raise AssertionError("exclusive phase costs do not sum to online wall")


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    v2_protocol = json.loads((HERE / "sage_protocol_v2.json").read_text())
    batch_protocol = json.loads((HERE / "batch_protocol.json").read_text())
    affine = json.loads((HERE / "affine_rank_result.json").read_text())
    v2 = json.loads((HERE / "result.json").read_text())
    batch = json.loads((HERE / "batch_result.json").read_text())
    failure = json.loads((HERE / "failure_v1.json").read_text())
    geometry_path = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
    prior_path = BASE / "n41_two_free_pair_s3_norm_20261008/native_controls.json"
    prior_arithmetic = BASE / "n131_w14_s3_prefix_rank_20261010/run.py"
    runtime = HERE / "sage_runtime_info.json"
    for key, path in [("affine_source", HERE / "affine_rank.py"),
                      ("arithmetic_source", prior_arithmetic),
                      ("geometry", geometry_path),
                      ("prior_native_controls", prior_path), ("runtime", runtime)]:
        check(protocol["sha256"][key], path)
    check(protocol["sha256"]["sage_source"], HERE / "run_sage_v1.py")
    check(failure["source_sha256"], HERE / "run_sage_v1.py")
    check(failure["protocol_sha256"], HERE / "protocol.json")
    check(failure["partial_output_sha256"], HERE / "partial_result_v1.txt")
    assert failure["status"] == "PRODUCER_FAILURE"
    check(affine["source_sha256"], HERE / "affine_rank.py")
    check(affine["protocol_sha256"], HERE / "protocol.json")
    assert affine["status"] == "COMPLETE_EXACT_AFFINE_SCAN"
    assert affine["bucket_pairs"] == 3969
    assert affine["cross_product_rank_histogram"] == {"41": 3969}
    assert not affine["nonfull_bucket_pairs"]
    assert all(x["bucket_trace_histogram"] == {"0": 63} for x in affine["domains"])

    assert v2_protocol["prior_protocol_sha256"] == sha(HERE / "protocol.json")
    check(v2_protocol["failure_v1_sha256"], HERE / "failure_v1.json")
    check(v2_protocol["sha256"]["sage_source"], HERE / "run_sage.py")
    check(v2["source_sha256"], HERE / "run_sage.py")
    check(v2["protocol_sha256"], HERE / "sage_protocol_v2.json")
    assert v2["status"] == "COMPLETE_DIAGNOSTIC"
    assert [x["status"] for x in v2["cases"]] == ["COMPLETE", "COMPLETE"]
    assert [x["bucket_pairs_checked"] for x in v2["cases"]] == [3969, 3969]
    assert [x["bucket_pairs_with_gcd"] for x in v2["cases"]] == [1, 0]
    assert [x["gcd_degree_total"] for x in v2["cases"]] == [1, 0]
    for row in v2["cases"]:
        phases(row, ["norm_build_ns", "gcd_ns", "witness_ns", "other_online_ns"])
        assert row["online_wall_ns"] <= 120 * 10**9
        assert row["peak_rss_bytes"] <= protocol["rss_cap_bytes"]

    for key, path in [("source", HERE / "run_batch_sage.py"),
                      ("base_source", HERE / "run_sage.py"),
                      ("base_result", HERE / "result.json"),
                      ("geometry", geometry_path), ("runtime", runtime)]:
        check(batch_protocol["sha256"][key], path)
    check(batch["source_sha256"], HERE / "run_batch_sage.py")
    check(batch["protocol_sha256"], HERE / "batch_protocol.json")
    assert batch["status"] == "COMPLETE_DIAGNOSTIC"
    assert batch["global_left_degree"] == 978
    assert [x["status"] for x in batch["cases"]] == ["COMPLETE", "COMPLETE"]
    assert [x["gcd_calls"] for x in batch["cases"]] == [63, 63]
    assert [x["bucket_pairs_with_gcd"] for x in batch["cases"]] == [1, 0]
    assert [x["matching_x_count"] for x in batch["cases"]] == [1, 0]
    for row in batch["cases"]:
        phases(row, ["norm_build_ns", "gcd_ns", "root_extraction_ns", "other_online_ns"])
        assert row["online_wall_ns"] <= 120 * 10**9
        assert row["peak_rss_bytes"] <= protocol["rss_cap_bytes"]
    witness = batch["cases"][0]["first_group_witness"]
    assert witness == v2["cases"][0]["first_group_witness"]
    assert witness is not None and batch["cases"][1]["first_group_witness"] is None

    geometry = json.loads(geometry_path.read_text())["n41"]
    f = Field(41, [0, 3])
    curve = Curve(f, 0)
    folded = []
    sums = []
    for rotation, indices, pair_key in [(20, witness["left_source_indices"],
                                         "left_pair_point"),
                                        (30, witness["right_source_indices"],
                                         "right_pair_point")]:
        rows = geometry["point_rows_by_unique_rotation"][str(rotation)]
        points = [tuple(rows[i][:2]) for i in indices]
        assert all(curve.on_curve(p) for p in points)
        assert all(curve.mul(int(geometry["subgroup_order"]), p) is None for p in points)
        folded.extend(rows[i][2] for i in indices)
        total = curve.add(points[0], points[1])
        assert list(total) == witness[pair_key]
        sums.append(total)
    assert len(set(folded)) == 4
    assert list(curve.add(*sums)) == protocol["positive_residual"]
    assert [witness["left_seed_sum"], witness["right_seed_sum"]] == [16, 5]

    pair_states_upper = 4 * math.comb(8220, 2)
    r = 680564733841876926932320129493409985129
    two_free_upper = pair_states_upper**2
    half_probe_lower = ((r - 1) + 2*two_free_upper - 1) // (2*two_free_upper)
    projection = {"scope": "uniform independent target and target-independent fixed first-three-pair prefixes",
                  "n131_w14_source_masks": 8220,
                  "n131_pair_group_states_upper": pair_states_upper,
                  "two_free_pair_group_assignments_upper": two_free_upper,
                  "fixed_prefix_probes_for_half_success_lower": half_probe_lower,
                  "fixed_prefix_probes_per_second_at_600s_lower":
                      {"numerator": half_probe_lower, "denominator": 600},
                  "n131_seed_sum_bucket_pairs": (2**14-1)**2}
    receipt = {"status": "PASS_SEED_SUM_S3_BUCKET_NORM",
               "source_sha256": sha(Path(__file__)),
               "protocol_sha256": sha(HERE / "protocol.json"),
               "affine_result_sha256": sha(HERE / "affine_rank_result.json"),
               "exact_result_sha256": sha(HERE / "result.json"),
               "batch_result_sha256": sha(HERE / "batch_result.json"),
               "independent_group_replay": True,
               "n131_fixed_prefix_projection": projection}
    with (HERE / "verification.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "fixed_prefix_probes_for_half_success_lower": half_probe_lower}))


if __name__ == "__main__":
    main()
