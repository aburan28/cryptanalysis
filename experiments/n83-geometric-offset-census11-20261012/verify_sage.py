#!/usr/bin/env python3
"""Independent polynomial-field replay of the width-11 shift census."""

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
    output = HERE / "independent_sage_replay.json"
    assert not output.exists(), "refusing to overwrite evidence"
    protocol_path = HERE / "protocol.json"
    census_path = HERE / "census.json"
    protocol = json.loads(protocol_path.read_text())
    census = json.loads(census_path.read_text())
    assert census["protocol_sha256"] == sha(protocol_path)
    bridge = json.loads(BRIDGE.read_text())
    assert bridge["curve_id"] == protocol["curve_id"]
    binary = GF(2)
    ring = PolynomialRing(binary, "t")
    t = ring.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**83, name="z", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)
    gamma = [field(ring([(int(raw) >> bit) & 1 for bit in range(83)]))
             for raw in bridge["onb_to_poly_basis_images"]]
    inverse = bridge["poly_to_onb_basis_images"]
    assert len(gamma) == len(inverse) == 83
    base = [field(0)]
    for element in gamma[:11]:
        base += [value + element for value in base]
    assert len(base) == 2048 and len(set(base)) == 2048
    for row in census["rows"]:
        shift = row["shift_coordinate"]
        offset = field(0) if shift is None else gamma[shift]
        valid = 0
        for seed in base:
            x = offset + seed
            if x != 0 and int((x + x**-1).trace()) == 0:
                valid += 1
        assert valid == row["valid_lifts"], (shift, valid, row["valid_lifts"])
        print(json.dumps({"shift_coordinate": shift, "valid": valid}), flush=True)

    def onb_coords(value):
        bits = sum(int(coefficient) << bit for bit, coefficient in
                   enumerate(value.polynomial().list()))
        coords = 0
        while bits:
            low = bits & -bits
            coords ^= inverse[low.bit_length() - 1]
            bits ^= low
        return coords

    gamma_index = {value: i for i, value in enumerate(gamma)}
    permutation = [gamma_index[value**2] for value in gamma]
    cycle = []
    index = 0
    for _ in range(83):
        cycle.append(index)
        index = permutation[index]
    assert index == 0 and len(set(cycle)) == 83
    positions = {coordinate: index for index, coordinate in enumerate(cycle)}

    def cycle_bits(value):
        coords = onb_coords(value)
        result = 0
        while coords:
            low = coords & -coords
            result |= 1 << positions[low.bit_length() - 1]
            coords ^= low
        return result

    def key_of(P):
        x = cycle_bits(P[0])
        y = cycle_bits(P[1])
        mask = (1 << 83) - 1
        best = (1 << 166)
        for _ in range(83):
            best = min((x << 83) | y, (x << 83) | (x ^ y), best)
            x = ((x << 1) | (x >> 82)) & mask
            y = ((y << 1) | (y >> 82)) & mask
        return best

    shift = census["best_shift_coordinate"]
    offset = field(0) if shift is None else gamma[shift]
    keys = set()
    valid = identities = duplicates = 0
    for seed in base:
        x = offset + seed
        if x == 0 or int((x + x**-1).trace()) != 0:
            continue
        P = curve.lift_x(x)
        valid += 1
        projected = 4 * P
        if projected == zero:
            identities += 1
            continue
        assert protocol["subgroup_order"] * projected == zero
        key = key_of(projected)
        if key in keys:
            duplicates += 1
        keys.add(key)
    winner = next(row for row in census["rows"]
                  if row["shift_coordinate"] == shift)
    assert (valid, identities, duplicates, len(keys)) == (
        winner["valid_lifts"], winner["identity_projections"],
        winner["duplicate_orbit_seeds"], winner["folded_columns_K"])
    key_path = HERE / census["best_key_file"]
    expected = b"".join(key.to_bytes(21, "little") for key in sorted(keys))
    assert key_path.read_bytes() == expected
    assert sha(key_path) == census["best_key_sha256"]
    report = {
        "kind": "n83_width11_shift_independent_sage_replay_v1",
        "status": "PASS",
        "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(protocol_path),
        "census_sha256": sha(census_path),
        "bridge_sha256": sha(BRIDGE),
        "verifier_source_sha256": sha(Path(__file__)),
        "all_shift_lift_counts": "PASS",
        "winner_full_subgroup_orbit_and_key_replay": "PASS",
        "winner_shift_coordinate": shift,
        "winner_K": len(keys),
        "winner_B": 166 * len(keys),
    }
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "winner": shift,
                      "K": len(keys)}), flush=True)


if __name__ == "__main__":
    main()
