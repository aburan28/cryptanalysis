#!/usr/bin/env python3
"""Independent polynomial-field replay of the exhaustive rectangle result."""

import hashlib
import itertools
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"
PARENT = ROOT / "experiments/n83-geometric-two-shift12-20261012"


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


def independent_top_two(rows):
    lifts = {tuple(row["shift_coordinates"]): row["valid_lifts"] for row in rows}
    assert len(lifts) == 2485
    top = []
    count = 0
    # This loop chooses the bipartition directly, independently of the producer's edge loop.
    for vertices in itertools.combinations(range(12, 83), 4):
        for first in itertools.combinations(vertices[1:], 1):
            side = {vertices[0], first[0]}
            opposite = set(vertices) - side
            edges = sorted(tuple(sorted((u, v))) for u in side for v in opposite)
            score = sum(lifts[edge] for edge in edges)
            count += 1
            candidate = (score, edges)
            if len(top) < 2:
                top.append(candidate)
                top.sort(reverse=True)
            elif candidate > top[-1]:
                top.sort(reverse=True)
                top[-1] = candidate
                top.sort(reverse=True)
    top.sort(reverse=True)
    assert count == 2914905
    return count, top


def main():
    output = HERE / "independent_sage_replay.json"
    assert not output.exists(), "refusing to overwrite evidence"
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "rectangle.json").read_text())
    screen = json.loads((PARENT / "screen.json").read_text())
    bridge = json.loads(BRIDGE.read_text())
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["producer_source_sha256"] == sha(HERE / "rectangle.py")
    assert protocol["screen_sha256"] == sha(PARENT / "screen.json")
    assert protocol["bridge_sha256"] == sha(BRIDGE)
    assert bridge["curve_id"] == result["curve_id"] == protocol["curve_id"]
    count, top = independent_top_two(screen["rows"])
    assert count == result["rectangle_count"]
    assert top[0][0] == result["winner_rational_lift_bound"]
    assert top[1][0] == result["other_rectangle_column_upper_bound"]
    assert top[0][1] == [tuple(edge) for edge in result["winner_edges"]]
    assert top[1][1] == [tuple(edge) for edge in result["runner_edges"]]

    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**83, name="a", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)
    gamma = [field(ring([(int(raw) >> bit) & 1 for bit in range(83)]))
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
        result_bits = 0
        while onb:
            low = onb & -onb
            result_bits |= 1 << cycle_position[low.bit_length() - 1]
            onb ^= low
        return result_bits

    def canonical_key(point):
        x, y = cycle_bits(point[0]), cycle_bits(point[1])
        mask = (1 << 83) - 1
        best = 1 << 166
        for _ in range(83):
            best = min(best, (x << 83) | y, (x << 83) | (x ^ y))
            x = ((x << 1) | (x >> 82)) & mask
            y = ((y << 1) | (y >> 82)) & mask
        return best

    base = [field(0)]
    for basis in gamma[:12]:
        base += [value + basis for value in base]
    assert len(base) == len(set(base)) == 4096
    all_keys = set()
    component_rows = []
    for edge in result["winner_edges"]:
        offset = gamma[edge[0]] + gamma[edge[1]]
        keys = set()
        valid = identities = duplicates = 0
        for seed in base:
            point = half_trace_lift(offset + seed, curve)
            if point is None:
                continue
            valid += 1
            projected = 4 * point
            if projected == zero:
                identities += 1
                continue
            assert protocol["subgroup_order"] * projected == zero
            key = canonical_key(projected)
            duplicates += key in keys
            keys.add(key)
        geometry = {"shift_coordinates": edge, "valid_lifts": valid,
                    "identity_projections": identities,
                    "duplicate_orbit_seeds": duplicates,
                    "K": len(keys), "B": 166 * len(keys)}
        assert geometry in result["components"]
        component_rows.append(geometry)
        all_keys.update(keys)
        print(json.dumps({"edge": edge, "K": len(keys)}), flush=True)
    assert len(all_keys) == result["folded_columns_K"]
    assert 166 * len(all_keys) == result["actual_usable_points_B_before_folding"]
    assert result["winner_rational_lift_bound"] - sum(r["identity_projections"] for r in component_rows) - len(all_keys) == result["duplicate_orbit_seeds_in_union"]
    assert result["folded_columns_K"] > result["other_rectangle_column_upper_bound"]
    blob = b"".join(k.to_bytes(21, "little") for k in sorted(all_keys))
    assert (HERE / result["key_file"]).read_bytes() == blob
    assert hashlib.sha256(blob).hexdigest() == result["key_sha256"]
    replay = {
        "kind": "n83_rectangle14_independent_polynomial_field_replay_v1",
        "status": "PASS",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "result_sha256": sha(HERE / "rectangle.json"),
        "verifier_source_sha256": sha(Path(__file__)),
        "bridge_sha256": sha(BRIDGE),
        "rectangle_count": count,
        "top_two_lift_bounds": [top[0][0], top[1][0]],
        "component_geometry": component_rows,
        "folded_columns_K": len(all_keys),
        "actual_usable_points_B_before_folding": 166 * len(all_keys),
        "full_key_sha256": hashlib.sha256(blob).hexdigest(),
    }
    output.write_text(json.dumps(replay, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "K": len(all_keys)}), flush=True)


if __name__ == "__main__":
    main()
