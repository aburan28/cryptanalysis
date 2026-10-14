#!/usr/bin/env python3
"""Read-only audit of the N83 rectangle translation screen."""

import hashlib
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
    assert protocol["translation_bits"] == list(range(12, 83))
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
    assert len(rows) == replay["rows_replayed"] == 71
    assert [row["translation_bit"] for row in rows] == list(range(12, 83))
    assert max(row["valid_lifts"] for row in rows) == replay["max_translated_valid_lifts"] == 8347
    assert result["best_translation_bit"] is None and result["best_geometry"] is None
    assert result["full_scans"] == []
    assert result["baseline_K"] == result["best_K"] == replay["baseline_folded_columns_K"] == 8532
    assert result["best_B"] == 166 * 8532
    assert max(row["valid_lifts"] for row in rows) < result["best_K"]
    assert (HERE / result["key_file"]).read_bytes() == (BASE / "rectangle_keys.bin").read_bytes()
    assert result["key_sha256"] == replay["baseline_key_sha256"] == sha(BASE / "rectangle_keys.bin")
    lean = (HERE / "TranslateBound.lean").read_text()
    assert all(token not in lean for token in ("sorry", "admit", "sorryAx", "axiom "))
    assert "'N83Rectangle14Translate.translated_base_below_original' does not depend on any axioms" in (HERE / "lean-build.txt").read_text()
    print(json.dumps({"status": "PASS", "translations": 71,
                      "max_translated_valid_lifts": 8347,
                      "baseline_columns_K": 8532}), flush=True)


if __name__ == "__main__":
    main()
