#!/usr/bin/env python3
"""Independent chunked-inversion and curve replay of two-bit N83 shifts."""

import hashlib
import itertools
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chunked_lift_count(xs, one):
    count = 0
    for start in range(0, len(xs), 512):
        block = xs[start:start + 512]
        prefix = [one]
        for x in block:
            assert x != 0
            prefix.append(prefix[-1] * x)
        suffix_inverse = prefix[-1]**-1
        for local in range(len(block) - 1, -1, -1):
            inv = suffix_inverse * prefix[local]
            suffix_inverse *= block[local]
            count += int((block[local] + inv).trace()) == 0
        assert suffix_inverse == one
    return count


def half_trace_lift(x, curve):
    """Solve (y/x)^2+(y/x)=x+1/x^2 in the odd-degree binary field."""
    assert x != 0
    z = x + x**-2
    if int(z.trace()) != 0:
        return None
    term = z
    u = z
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
    protocol_path = HERE / "protocol.json"
    screen_path = HERE / "screen.json"
    protocol = json.loads(protocol_path.read_text())
    screen = json.loads(screen_path.read_text())
    assert screen["protocol_sha256"] == sha(protocol_path)
    prior_protocol = json.loads((ROOT / "experiments/n83-geometric-m5-gate-20261012/protocol.json").read_text())
    assert prior_protocol["curve_id"] == protocol["curve_id"]
    subgroup_order = protocol["subgroup_order"]
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
    inverse_basis = bridge["poly_to_onb_basis_images"]
    assert len(gamma) == len(inverse_basis) == 83
    base = [field(0)]
    for basis in gamma[:12]:
        base += [x + basis for x in base]
    assert len(base) == len(set(base)) == 4096
    pairs = list(itertools.combinations(range(12, 83), 2))
    assert len(pairs) == len(screen["rows"]) == 2485
    for index, ((i, j), row) in enumerate(zip(pairs, screen["rows"])):
        assert row["shift_coordinates"] == [i, j]
        offset = gamma[i] + gamma[j]
        xs = [offset + seed for seed in base]
        valid = chunked_lift_count(xs, field(1))
        assert valid == row["valid_lifts"], (i, j, valid, row["valid_lifts"])
        # Direct curve lifting spot-checks the trace predicate for each coset.
        for x in (xs[0], xs[-1]):
            lift = half_trace_lift(x, curve)
            assert (lift is not None) == (int((x + x**-1).trace()) == 0)
        if (index + 1) % 128 == 0:
            print(json.dumps({"checked": index + 1}), flush=True)
    needed = {tuple(row["shift_coordinates"]) for row in screen["rows"]
              if row["valid_lifts"] > screen["best_K"]}
    replayed = {tuple(row["shift_coordinates"]) for row in screen["competitive_full_scans"]}
    assert needed <= replayed
    assert all(row["K"] <= screen["best_K"] for row in screen["competitive_full_scans"])

    def onb_coords(value):
        bits = sum(int(coefficient) << bit for bit, coefficient in
                   enumerate(value.polynomial().list()))
        coords = 0
        while bits:
            low = bits & -bits
            coords ^= inverse_basis[low.bit_length() - 1]
            bits ^= low
        return coords

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
        coords = onb_coords(value)
        result = 0
        while coords:
            low = coords & -coords
            result |= 1 << cycle_position[low.bit_length() - 1]
            coords ^= low
        return result

    def canonical_key(P):
        x = cycle_bits(P[0])
        y = cycle_bits(P[1])
        mask = (1 << 83) - 1
        best = 1 << 166
        for _ in range(83):
            best = min(best, (x << 83) | y, (x << 83) | (x ^ y))
            x = ((x << 1) | (x >> 82)) & mask
            y = ((y << 1) | (y >> 82)) & mask
        return best

    winner = screen["best_shift_coordinates"]
    assert winner == [82] or (len(winner) == 2 and tuple(winner) in pairs)
    offset = sum((gamma[index] for index in winner), field(0))
    keys = set()
    valid = identities = duplicates = 0
    for seed in base:
        x = offset + seed
        P = half_trace_lift(x, curve)
        if P is None:
            continue
        valid += 1
        projected = 4 * P
        if projected == zero:
            identities += 1
            continue
        assert subgroup_order * projected == zero
        key = canonical_key(projected)
        if key in keys:
            duplicates += 1
        keys.add(key)
    if screen["best_full_scan"] is not None:
        geometry = screen["best_full_scan"]
        assert (valid, identities, duplicates, len(keys)) == (
            geometry["valid_lifts"], geometry["identity_projections"],
            geometry["duplicate_orbit_seeds"], geometry["K"])
    assert screen["best_K"] == len(keys)
    key_path = HERE / screen["best_key_file"]
    assert key_path.read_bytes() == b"".join(
        key.to_bytes(21, "little") for key in sorted(keys))
    assert sha(key_path) == screen["best_key_sha256"]
    report = {
        "kind": "n83_width12_two_shift_independent_sage_replay_v1",
        "status": "PASS",
        "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(protocol_path),
        "screen_sha256": sha(screen_path),
        "bridge_sha256": sha(BRIDGE),
        "verifier_source_sha256": sha(Path(__file__)),
        "all_2485_lift_counts": "PASS",
        "winner_full_subgroup_orbit_and_key_replay": "PASS",
        "winner_shift_coordinates": winner,
        "winner_K": len(keys),
        "winner_B": 166 * len(keys),
    }
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "best_K": len(keys)}), flush=True)


if __name__ == "__main__":
    main()
