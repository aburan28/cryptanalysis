#!/usr/bin/env python3
"""Read-only audit of every N83 rectangle two-bit translation."""

import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "experiments/n83-geometric-rectangle14-20261012"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    protocol = read("protocol.json")
    result = read("screen.json")
    replay = read("independent_sage_replay.json")
    assert protocol["translation_bits"] == "all 12 <= a < b <= 82"
    for key, path in (
        ("basis_manifest_sha256", BASE / "basis_manifest.json"),
        ("prior_result_sha256", BASE / "rectangle.json"),
        ("bridge_sha256", ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"),
        ("field_source_sha256", ROOT / "ecc2k130/codegen/field.py"),
        ("curve_source_sha256", ROOT / "ecc2k130/codegen/curves.py"),
        ("orbit_source_sha256", ROOT / "experiments/koblitz-pair-claw-20260929/orbit_key.py"),
    ):
        assert protocol[key] == sha(path), key
    assert result["protocol_sha256"] == replay["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["producer_source_sha256"] == sha(HERE / "screen.py")
    assert replay["verifier_source_sha256"] == sha(HERE / "verify_sage.py")
    assert replay["screen_sha256"] == sha(HERE / "screen.json")
    assert result["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert read("sage_runtime_info.json")["status"] == "verified"
    assert result["status"] == "complete_geometry_screen" and replay["status"] == "PASS"
    rows = result["rows"]
    pairs = [list(pair) for pair in itertools.combinations(range(12, 83), 2)]
    assert len(rows) == replay["rows_replayed"] == len(pairs) == 2485
    assert [row["translation_bits"] for row in rows] == pairs
    assert [row["translation_bits"] for row in rows if row["zero_x_candidates"]] == \
        [[37, 73], [37, 82], [68, 73], [68, 82]]
    equivalent = [row["translation_bits"] for row in rows if row["same_affine_plane"]]
    assert equivalent == result["equivalent_translation_bits"] == [[37, 68], [73, 82]]
    distinct = [row for row in rows if not row["same_affine_plane"]]
    best = max(distinct, key=lambda row: row["valid_lifts"])
    assert best["translation_bits"] == [50, 69]
    assert best["valid_lifts"] == result["max_other_valid_lifts"] == \
        replay["max_other_valid_lifts"] == 8421
    assert result["best_translation_bits"] is None
    assert result["tied_translations"] == result["full_scans"] == []
    assert result["baseline_K"] == result["best_K"] == replay["best_K"] == 8532
    assert result["best_B"] == 166 * 8532
    assert best["valid_lifts"] < result["best_K"]
    assert (HERE / result["key_file"]).read_bytes() == (BASE / "rectangle_keys.bin").read_bytes()
    assert result["key_sha256"] == replay["best_key_sha256"] == sha(BASE / "rectangle_keys.bin")
    assert replay["best_translation_bits"] is None
    assert sha(HERE / "protocol_attempt1.json") == sha(HERE / "protocol.json")
    assert sha(HERE / "screen_attempt1.py") != sha(HERE / "screen.py")
    failure = (HERE / "failure_attempt1.txt").read_text()
    assert "AssertionError" in failure and "1,472" in failure and "(37,73)" in failure
    lean = (HERE / "TranslateBound.lean").read_text()
    assert all(token not in lean for token in ("sorry", "admit", "sorryAx", "axiom "))
    assert "'N83Rectangle14TwoBitTranslate.distinct_translate_below_original' does not depend on any axioms" in (HERE / "lean-build.txt").read_text()
    print(json.dumps({"status": "PASS", "translations": 2485,
                      "best_distinct_lifts": 8421,
                      "baseline_columns_K": 8532}), flush=True)


if __name__ == "__main__":
    main()
