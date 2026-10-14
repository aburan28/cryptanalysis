#!/usr/bin/env python3
"""Read-only receipt audit for the exact N83 width-14 rectangle base."""

import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/n83-geometric-two-shift12-20261012"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    protocol = read("protocol.json")
    result = read("rectangle.json")
    replay = read("independent_sage_replay.json")
    manifest = read("basis_manifest.json")
    screen_path = PARENT / "screen.json"
    prior_path = ROOT / "experiments/n83-geometric-width14-20261012/frontier.json"
    bridge_path = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"
    assert protocol["screen_sha256"] == result["screen_sha256"] == sha(screen_path)
    assert protocol["prior_frontier_sha256"] == result["prior_frontier_sha256"] == sha(prior_path)
    for key, path in (
        ("screen_source_sha256", PARENT / "screen.py"),
        ("curve_source_sha256", ROOT / "ecc2k130/codegen/curves.py"),
        ("field_source_sha256", ROOT / "ecc2k130/codegen/field.py"),
        ("orbit_source_sha256", ROOT / "experiments/koblitz-pair-claw-20260929/orbit_key.py"),
        ("bridge_sha256", bridge_path),
    ):
        assert protocol[key] == sha(path), key
    assert result["protocol_sha256"] == replay["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["producer_source_sha256"] == sha(HERE / "rectangle.py")
    assert replay["result_sha256"] == manifest["rectangle_receipt_sha256"] == sha(HERE / "rectangle.json")
    assert replay["verifier_source_sha256"] == sha(HERE / "verify_sage.py")
    assert result["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert read("sage_runtime_info.json")["status"] == "verified"
    assert replay["status"] == "PASS" and result["status"] == "complete_geometry"
    assert result["rectangle_count"] == replay["rectangle_count"] == 3 * math.comb(71, 4)
    assert replay["top_two_lift_bounds"] == [8532, 8509]
    assert result["winner_rational_lift_bound"] == 8532
    assert result["other_rectangle_column_upper_bound"] == 8509
    assert result["winner_edges"] == [[37, 73], [37, 82], [68, 73], [68, 82]]
    assert len(result["components"]) == 4
    assert result["components"] == replay["component_geometry"]
    assert sum(row["valid_lifts"] for row in result["components"]) == 8532
    assert all(row["identity_projections"] == row["duplicate_orbit_seeds"] == 0
               for row in result["components"])
    assert result["duplicate_orbit_seeds_in_union"] == 0
    K = result["folded_columns_K"]
    B = result["actual_usable_points_B_before_folding"]
    assert K == replay["folded_columns_K"] == manifest["effective_columns_K"] == 8532
    assert B == replay["actual_usable_points_B_before_folding"] == manifest["actual_subgroup_points_B"] == 166 * K == 1416312
    assert K > result["other_rectangle_column_upper_bound"]
    prior = json.loads(prior_path.read_text())["rows"][0]
    assert prior["folded_columns_K"] == result["prior_shifted_width14_K"] == 8261
    assert prior["actual_usable_points_B_before_folding"] == result["prior_shifted_width14_B"] == 1371326
    assert prior["five_subset_first_moment"] == result["prior_five_subset_first_moment"]
    with localcontext() as context:
        context.prec = 50
        exact_first_moment = str(Decimal(math.comb(B, 5)) / Decimal(protocol["subgroup_order"]))
    assert result["five_subset_first_moment"] == exact_first_moment
    key_path = HERE / result["key_file"]
    blob = key_path.read_bytes()
    assert len(blob) == 21 * K
    keys = [int.from_bytes(blob[i:i+21], "little") for i in range(0, len(blob), 21)]
    assert keys == sorted(set(keys))
    assert sha(key_path) == result["key_sha256"] == replay["full_key_sha256"] == manifest["factor_base_key_sha256"]
    assert manifest["factor_base_key_file"] == result["key_file"]
    assert manifest["curve_id"] == protocol["curve_id"] == result["curve_id"]
    offset = manifest["affine_offset_onb_coordinates"]
    basis = manifest["basis_onb_coordinates"]
    assert len(basis) == 14 and basis[:12] == [1 << i for i in range(12)]
    cosets = {offset, offset ^ basis[12], offset ^ basis[13],
              offset ^ basis[12] ^ basis[13]}
    assert cosets == set(manifest["coset_offsets_onb_coordinates"])
    assert cosets == {(1 << a) ^ (1 << b) for a, b in result["winner_edges"]}
    lean = (HERE / "RectangleBound.lean").read_text()
    assert all(token not in lean for token in ("sorry", "admit", "sorryAx", "axiom "))
    build = (HERE / "lean-build.txt").read_text()
    for theorem in ("other_rectangle_below_winner", "winner_exceeds_prior_width14",
                    "winner_usable_points"):
        assert f"'{theorem}' does not depend on any axioms" in build or \
               f"'N83Rectangle14.{theorem}' does not depend on any axioms" in build
    print(json.dumps({"status": "PASS", "K": K, "B": B,
                      "rectangles": result["rectangle_count"],
                      "first_moment": exact_first_moment}), flush=True)


if __name__ == "__main__":
    main()
