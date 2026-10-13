#!/usr/bin/env python3
"""Independent N83 z-fiber and subgroup-orbit replay from frozen root bytes."""

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
    report = json.loads((HERE / "census.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    bridge = json.loads(BRIDGE.read_text())
    assert report["status"] == "complete"
    assert report["protocol_sha256"] == sha(HERE / "protocol.json")
    assert report["roots_file_sha256"] == sha(HERE / "roots.bin")
    assert report["keys_file_sha256"] == sha(HERE / "keys.bin")
    assert bridge["curve_id"] == protocol["curve_id"]

    R = PolynomialRing(GF(2), "t")
    t = R.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    F = GF(2**83, name="a", modulus=modulus)
    curve = EllipticCurve(F, [1, 0, 0, 0, 1])
    zero = curve(0)
    inverse_basis = bridge["poly_to_onb_basis_images"]
    gamma = [F(R([(int(raw) >> j) & 1 for j in range(83)]))
             for raw in bridge["onb_to_poly_basis_images"]]
    gamma_index = {g: i for i, g in enumerate(gamma)}
    permutation = [gamma_index[g**2] for g in gamma]
    cycle = []
    j = 0
    for _ in range(83):
        cycle.append(j)
        j = permutation[j]
    assert j == 0 and len(set(cycle)) == 83
    cycle_position = {coordinate: index for index, coordinate in enumerate(cycle)}

    def cycle_bits(value):
        coeffs = sum(int(c) << i for i, c in enumerate(value.polynomial().list()))
        onb = 0
        while coeffs:
            low = coeffs & -coeffs
            onb ^= inverse_basis[low.bit_length() - 1]
            coeffs ^= low
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

    blob = (HERE / "roots.bin").read_bytes()
    assert len(blob) % 11 == 0
    root_ints = [int.from_bytes(blob[i:i + 11], "little") for i in range(0, len(blob), 11)]
    assert root_ints == sorted(set(root_ints))
    assert len(root_ints) == report["raw_x_roots"]
    expected_z = {sum((int(mask >> j & 1) * F.gen()**(j + 1) for j in range(11)), F(0))
                  for mask in range(2048)}
    assert len(expected_z) == 2048
    seen_z = set()
    keys = set()
    identities = 0
    for i, value in enumerate(root_ints):
        x = F(R([(value >> j) & 1 for j in range(83)]))
        assert x != 0
        z = x + x**-2
        assert z in expected_z and z not in seen_z
        seen_z.add(z)
        assert int(z.trace()) == 0
        # Dividing the cubic by its known root leaves X^2+(z+x)X+1/x.
        # Its Artin-Schreier trace is one exactly when there are no more roots.
        a = z + x
        assert a != 0
        assert int((x**-1 / a**2).trace()) == 1
        p = curve.lift_x(x)
        assert p[1]**2 + x*p[1] == x**3 + 1
        q = protocol["cofactor"] * p
        if q == zero:
            identities += 1
        else:
            assert protocol["subgroup_order"] * q == zero
            keys.add(canonical_key(q))
        if (i + 1) % 512 == 0:
            print(json.dumps({"replayed_roots": i + 1, "K": len(keys)}), flush=True)
    assert seen_z == expected_z
    assert identities == report["subgroup_identities"]
    assert len(keys) == report["effective_columns_K"]
    assert 166 * len(keys) == report["actual_subgroup_points_B"]
    independent = {
        "kind": "n83_z_coordinate_independent_sage_replay_v1",
        "status": "PASS",
        "census_sha256": sha(HERE / "census.json"),
        "bridge_sha256": sha(BRIDGE),
        "verifier_source_sha256": sha(Path(__file__)),
        "unique_z_values": len(seen_z),
        "one_root_cubic_fibers_certified_by_quadratic_trace": len(seen_z),
        "subgroup_identities": identities,
        "effective_columns_K": len(keys),
        "actual_subgroup_points_B": 166 * len(keys),
        "independent_onb_key_sha256": hashlib.sha256(b"".join(
            key.to_bytes(21, "little") for key in sorted(keys))).hexdigest(),
    }
    output.write_text(json.dumps(independent, sort_keys=True, indent=2) + "\n")
    print(json.dumps(independent, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
