#!/usr/bin/env python3
"""Independent per-element Sage replay of all rectangle translations."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "experiments/n83-geometric-rectangle14-20261012"
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "independent_sage_replay.json"
    assert not output.exists(), "refusing to overwrite evidence"
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "screen.json").read_text())
    manifest = json.loads((BASE / "basis_manifest.json").read_text())
    bridge = json.loads(BRIDGE.read_text())
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["producer_source_sha256"] == sha(HERE / "screen.py")
    assert protocol["bridge_sha256"] == sha(BRIDGE)
    assert protocol["basis_manifest_sha256"] == sha(BASE / "basis_manifest.json")
    assert bridge["curve_id"] == result["curve_id"] == protocol["curve_id"]
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**83, name="a", modulus=modulus)
    gamma = [field(ring([(int(raw) >> bit) & 1 for bit in range(83)]))
             for raw in bridge["onb_to_poly_basis_images"]]

    def convert(raw):
        value = field(0)
        for bit in range(83):
            if raw & (1 << bit):
                value += gamma[bit]
        return value

    affine = {convert(manifest["affine_offset_onb_coordinates"])}
    for raw in manifest["basis_onb_coordinates"]:
        basis = convert(raw)
        affine |= {value + basis for value in affine}
    assert len(affine) == 16384
    rows = []
    for bit in range(12, 83):
        valid = 0
        for seed in affine:
            x = seed + gamma[bit]
            assert x != 0
            valid += int((x + x**-1).trace()) == 0
        rows.append({"translation_bit": bit, "valid_lifts": valid})
        if len(rows) % 8 == 0:
            print(json.dumps({"replayed": len(rows), "max_lifts": max(r["valid_lifts"] for r in rows)}), flush=True)
    assert rows == result["rows"]
    max_valid = max(row["valid_lifts"] for row in rows)
    assert max_valid == 8347 < result["best_K"] == 8532
    assert result["best_translation_bit"] is None
    assert result["full_scans"] == []
    prior_keys = BASE / "rectangle_keys.bin"
    assert (HERE / result["key_file"]).read_bytes() == prior_keys.read_bytes()
    assert result["key_sha256"] == sha(prior_keys)
    replay = {
        "kind": "n83_rectangle14_high_bit_translations_independent_sage_replay_v1",
        "status": "PASS",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "screen_sha256": sha(HERE / "screen.json"),
        "verifier_source_sha256": sha(Path(__file__)),
        "bridge_sha256": sha(BRIDGE),
        "rows_replayed": len(rows),
        "max_translated_valid_lifts": max_valid,
        "baseline_folded_columns_K": result["best_K"],
        "baseline_key_sha256": sha(prior_keys),
    }
    output.write_text(json.dumps(replay, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"status": "PASS", "rows": len(rows),
                      "max_translated_valid_lifts": max_valid}), flush=True)


if __name__ == "__main__":
    main()
