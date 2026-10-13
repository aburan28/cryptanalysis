#!/usr/bin/env python3
"""Independent Sage replay of the optimal union's exact subgroup key set."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "independent_union_sage_replay.json"
    assert not output.exists(), "refusing to overwrite evidence"
    protocol = json.loads((HERE / "union_protocol.json").read_text())
    report = json.loads((HERE / "union.json").read_text())
    screen = json.loads((HERE / "screen.json").read_text())
    bridge = json.loads(BRIDGE.read_text())
    assert report["protocol_sha256"] == sha(HERE / "union_protocol.json")
    assert report["source_sha256"] == sha(HERE / "union.py")
    assert report["screen_sha256"] == sha(HERE / "screen.json")
    assert protocol["screen_sha256"] == sha(HERE / "screen.json")
    assert bridge["curve_id"] == protocol["curve_id"]
    assert report["status"] == "complete_geometry"
    assert report["all_pair_optimum_certified"]
    rows = sorted(screen["rows"], key=lambda row: (-row["valid_lifts"], row["shift_coordinates"]))
    assert [row["shift_coordinates"] for row in rows[:2]] == protocol["component_offsets"]
    assert [row["valid_lifts"] for row in rows[:3]] == [2196, 2156, 2150]
    # Any pair other than the top two has at most top+third rational lifts.
    assert rows[0]["valid_lifts"] + rows[2]["valid_lifts"] == 4346 < report["best_K"]
    assert report["evaluated_pairs"] == 1 and report["full_scanned_offsets"] == 2

    R = PolynomialRing(GF(2), "t")
    t = R.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    F = GF(2**83, name="a", modulus=modulus)
    curve = EllipticCurve(F, [1, 0, 0, 0, 1])
    zero = curve(0)
    gamma = [F(R([(int(raw) >> bit) & 1 for bit in range(83)]))
             for raw in bridge["onb_to_poly_basis_images"]]
    inverse_basis = bridge["poly_to_onb_basis_images"]
    gamma_index = {value: i for i, value in enumerate(gamma)}
    permutation = [gamma_index[value**2] for value in gamma]
    cycle = []
    position = 0
    for _ in range(83):
        cycle.append(position)
        position = permutation[position]
    assert position == 0 and len(set(cycle)) == 83
    cycle_position = {coordinate: index for index, coordinate in enumerate(cycle)}

    def cycle_bits(value):
        bits = sum(int(c) << i for i, c in enumerate(value.polynomial().list()))
        onb = 0
        while bits:
            low = bits & -bits
            onb ^= inverse_basis[low.bit_length() - 1]
            bits ^= low
        result = 0
        while onb:
            low = onb & -onb
            result |= 1 << cycle_position[low.bit_length() - 1]
            onb ^= low
        return result

    def canonical_key(P):
        x, y = cycle_bits(P[0]), cycle_bits(P[1])
        mask = (1 << 83) - 1
        best = 1 << 166
        for _ in range(83):
            best = min(best, (x << 83) | y, (x << 83) | (x ^ y))
            x = ((x << 1) | (x >> 82)) & mask
            y = ((y << 1) | (y >> 82)) & mask
        return best

    base = [F(0)]
    for basis in gamma[:12]:
        base += [value + basis for value in base]
    assert len(base) == len(set(base)) == 4096
    component_keys = []
    component_geometry = []
    for bits in protocol["component_offsets"]:
        offset = gamma[bits[0]] + gamma[bits[1]]
        keys = set()
        valid = identities = duplicates = 0
        for seed in base:
            x = offset + seed
            try:
                p = curve.lift_x(x)
            except ValueError:
                continue
            valid += 1
            q = 4 * p
            if q == zero:
                identities += 1
                continue
            assert 2417851639230796216685689 * q == zero
            key = canonical_key(q)
            duplicates += key in keys
            keys.add(key)
        geometry = {"shift_coordinates": bits, "valid_lifts": valid,
                    "identity_projections": identities,
                    "duplicate_orbit_seeds": duplicates,
                    "K": len(keys), "B": 166 * len(keys)}
        assert geometry in report["components"]
        component_geometry.append(geometry)
        component_keys.append(keys)
        print(json.dumps({"component": bits, "K": len(keys)}), flush=True)
    union = component_keys[0] | component_keys[1]
    intersection = component_keys[0] & component_keys[1]
    assert len(intersection) == report["intersection_K"]
    assert len(union) == report["best_K"]
    assert 166 * len(union) == report["best_B"]
    blob = b"".join(key.to_bytes(21, "little") for key in sorted(union))
    assert (HERE / report["key_file"]).read_bytes() == blob
    assert hashlib.sha256(blob).hexdigest() == report["key_sha256"]
    result = {
        "kind": "n83_width12_two_coset_union_independent_sage_replay_v1",
        "status": "PASS",
        "protocol_sha256": sha(HERE / "union_protocol.json"),
        "union_sha256": sha(HERE / "union.json"),
        "screen_sha256": sha(HERE / "screen.json"),
        "bridge_sha256": sha(BRIDGE),
        "verifier_source_sha256": sha(Path(__file__)),
        "component_geometry": component_geometry,
        "intersection_K": len(intersection),
        "best_K": len(union),
        "best_B": 166 * len(union),
        "global_pair_upper_bound_other_pairs": 4346
    }
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "K": len(union), "B": 166 * len(union)}), flush=True)


if __name__ == "__main__":
    main()
