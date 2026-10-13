#!/usr/bin/env python3
"""Independent per-element Sage replay of two-bit rectangle translations."""

import hashlib
import itertools
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "experiments/n83-geometric-rectangle14-20261012"
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def half_trace_lift(x, curve):
    assert x != 0
    z = x + x**-2
    if int(z.trace()) != 0:
        return None
    u = z
    term = z
    for _ in range(41):
        term = term**4
        u += term
    assert u**2 + u == z
    y = u * x
    assert y**2 + x*y == x**3 + 1
    return curve(x, y)


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
    directions = set(manifest["basis_onb_coordinates"][12:])
    for a, b in itertools.combinations(range(12, 83), 2):
        valid = 0
        zero_count = 0
        for seed in affine:
            x = seed + gamma[a] + gamma[b]
            if x == 0:
                zero_count += 1
                continue
            valid += int((x + x**-1).trace()) == 0
        assert zero_count in (0, 1)
        equivalent = ((1 << a) ^ (1 << b)) in directions
        rows.append({"translation_bits": [a, b], "valid_lifts": valid,
                     "zero_x_candidates": zero_count,
                     "same_affine_plane": equivalent})
        if len(rows) % 64 == 0:
            print(json.dumps({"replayed": len(rows),
                              "max_other_lifts": max(r["valid_lifts"] for r in rows
                                                     if not r["same_affine_plane"])}), flush=True)
    assert rows == result["rows"]
    assert [row["translation_bits"] for row in rows if row["zero_x_candidates"]] == \
        [[37, 73], [37, 82], [68, 73], [68, 82]]
    equivalent_rows = [row["translation_bits"] for row in rows if row["same_affine_plane"]]
    assert equivalent_rows == result["equivalent_translation_bits"] == [[37, 68], [73, 82]]
    max_other = max(row["valid_lifts"] for row in rows if not row["same_affine_plane"])
    assert max_other == result["max_other_valid_lifts"]
    if result["best_translation_bits"] is None:
        prior_keys = BASE / "rectangle_keys.bin"
        assert (HERE / result["key_file"]).read_bytes() == prior_keys.read_bytes()
        assert result["key_sha256"] == sha(prior_keys)
        assert result["best_K"] == manifest["effective_columns_K"]
        key_digest = sha(prior_keys)
    else:
        # Recompute the complete winner key set in a polynomial field.
        inverse_basis = bridge["poly_to_onb_basis_images"]
        gamma_index = {value: i for i, value in enumerate(gamma)}
        permutation = [gamma_index[value**2] for value in gamma]
        cycle = []
        pos = 0
        for _ in range(83):
            cycle.append(pos)
            pos = permutation[pos]
        assert pos == 0 and len(set(cycle)) == 83
        cycle_pos = {coordinate: i for i, coordinate in enumerate(cycle)}

        def cycle_bits(value):
            bits = sum(int(c) << i for i, c in enumerate(value.polynomial().list()))
            onb = 0
            while bits:
                low = bits & -bits
                onb ^= inverse_basis[low.bit_length()-1]
                bits ^= low
            out = 0
            while onb:
                low = onb & -onb
                out |= 1 << cycle_pos[low.bit_length()-1]
                onb ^= low
            return out

        def canonical_key(point):
            x, y = cycle_bits(point[0]), cycle_bits(point[1])
            mask = (1 << 83)-1
            best = 1 << 166
            for _ in range(83):
                best = min(best, (x << 83)|y, (x << 83)|(x ^ y))
                x = ((x << 1)|(x >> 82)) & mask
                y = ((y << 1)|(y >> 82)) & mask
            return best

        curve = EllipticCurve(field, [1, 0, 0, 0, 1])
        zero = curve(0)
        a, b = result["best_translation_bits"]
        keys = set()
        valid = identities = duplicates = 0
        for seed in affine:
            point = half_trace_lift(seed + gamma[a] + gamma[b], curve)
            if point is None:
                continue
            valid += 1
            projected = 4 * point
            if projected == zero:
                identities += 1
                continue
            assert 2417851639230796216685689 * projected == zero
            key = canonical_key(projected)
            duplicates += key in keys
            keys.add(key)
        assert {"valid_lifts":valid,"identity_projections":identities,
                "duplicate_orbit_seeds":duplicates,"K":len(keys),
                "B":166*len(keys)} == result["best_geometry"]
        blob = b"".join(k.to_bytes(21,"little") for k in sorted(keys))
        assert (HERE / result["key_file"]).read_bytes() == blob
        key_digest = hashlib.sha256(blob).hexdigest()
        assert key_digest == result["key_sha256"]
    replay = {
        "kind": "n83_rectangle14_two_high_bit_translations_independent_sage_replay_v1",
        "status": "PASS",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "screen_sha256": sha(HERE / "screen.json"),
        "verifier_source_sha256": sha(Path(__file__)),
        "bridge_sha256": sha(BRIDGE),
        "rows_replayed": len(rows),
        "max_other_valid_lifts": max_other,
        "baseline_folded_columns_K": manifest["effective_columns_K"],
        "best_translation_bits": result["best_translation_bits"],
        "best_K": result["best_K"],
        "best_key_sha256": key_digest,
    }
    output.write_text(json.dumps(replay, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"status": "PASS", "rows": len(rows),
                      "max_other_valid_lifts": max_other,
                      "best_K": result["best_K"]}), flush=True)


if __name__ == "__main__":
    main()
