#!/usr/bin/env python3
"""Freeze planted and ordinary N83 public points for the W3/W4 SAT pilot."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


N = 83
R = 2417851639230796216685689
H = 4
HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "n83_w34_sat_protocol.json"
GEOMETRY = HERE / "runs/n83_full_w4_geometry_v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main(out):
    out = out.resolve()
    runtime = out / "sage_runtime_info.json"
    if not out.is_dir() or not runtime.is_file():
        raise FileNotFoundError("create output and save checked Sage runtime first")
    if (out / "public_input.json").exists() or (out / "started.json").exists():
        raise FileExistsError("fixture output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    geometry = json.loads((GEOMETRY / "geometry.json").read_text())
    archived = json.loads((GEOMETRY / "representatives.json").read_text())
    assert sha(GEOMETRY / "geometry.json") == protocol["full_w4_geometry_sha256"]
    assert sha(GEOMETRY / "representatives.json") == protocol["full_w4_representatives_sha256"]
    assert sha(GEOMETRY / "sage_replay.json") == protocol["full_w4_independent_replay_sha256"]
    assert geometry["curve_id"] == archived["curve_id"] == protocol["curve_id"]
    save(out / "started.json", {
        "kind": "n83_w34_sat_fixture_start", "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(PROTOCOL), "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime),
    })

    binary = GF(2)
    ring = PolynomialRing(binary, "u")
    u = ring.gen()
    field = GF(2**N, "z", modulus=u**N + u**7 + u**4 + u**2 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert ZZ(R).is_prime(proof=True) and curve.cardinality() == H * R

    def element(bits):
        return field(ring([(bits >> i) & 1 for i in range(N)]))

    def code(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def pair(point):
        if point == curve(0):
            return None
        return [str(code(point[0])), str(code(point[1]))]

    alpha = element(geometry["normal_element_polynomial_bits"])
    conjugates = [alpha]
    for _ in range(1, N):
        conjugates.append(conjugates[-1]**2)
    assert conjugates[-1]**2 == alpha
    representatives = {tuple(row) for row in archived["representatives"]}

    def orbit_key(point):
        x, y = point[0], point[1]
        values = []
        for _ in range(N):
            xword, yword = code(x), code(y)
            values.extend(((xword, yword), (xword, xword ^ yword)))
            x, y = x**2, y**2
        return min(values)

    def pick(weight, lower_bounds):
        selected = []
        visited = set()
        ordinal = 0
        cursor = 0
        for mask in itertools.combinations(range(N), weight):
            if mask in visited:
                continue
            shifts = {tuple(sorted((bit + shift) % N for bit in mask))
                      for shift in range(N)}
            assert len(shifts) == N
            visited.update(shifts)
            ordinal += 1
            if ordinal < lower_bounds[cursor]:
                continue
            x = sum((conjugates[bit] for bit in mask), field(0))
            lifts = list(curve.lift_x(x, all=True))
            if not lifts:
                continue
            assert len(lifts) == 2 and lifts[0] == -lifts[1]
            point = min(lifts, key=lambda value: code(value[1]))
            projected = H * point
            assert projected != curve(0) and R * projected == curve(0)
            assert orbit_key(projected) in representatives
            selected.append((ordinal, mask, point, projected))
            cursor += 1
            if cursor == len(lower_bounds):
                return selected
        raise AssertionError("not enough rational mask orbits")

    selected = pick(3, protocol["planted_w3_orbit_lower_bounds"])
    selected += pick(4, protocol["planted_w4_orbit_lower_bounds"])
    raw = [row[2] for row in selected]
    projected = [row[3] for row in selected]
    assert len({orbit_key(point) for point in projected}) == 5
    for size in range(1, len(raw)):
        for subset in itertools.combinations(raw, size):
            assert sum(subset, curve(0)) != curve(0)
    raw_sum = sum(raw, curve(0))
    planted_q = H * raw_sum
    assert planted_q != curve(0) and R * planted_q == curve(0)
    gx, gy = geometry["curve_identity_record"]["curve"]["G"]
    generator = curve(element(gx), element(gy))
    assert generator != curve(0) and R * generator == curve(0)
    ordinary_seed = b"n83-w34-ordinary-v1-0"
    ordinary_scalar = 1 + int.from_bytes(hashlib.sha256(ordinary_seed).digest(), "big") % (R - 1)
    ordinary_q = ordinary_scalar * generator
    assert ordinary_q != curve(0) and R * ordinary_q == curve(0)

    torsion = [curve(0), curve(field(0), field(1)),
               curve(field(1), field(0)), curve(field(1), field(1))]
    assert len(set(torsion)) == 4 and all(H * point == curve(0) for point in torsion)

    def fiber(q):
        root = pow(H, -1, R) * q
        values = [root + point for point in torsion]
        assert len(set(values)) == 4 and all(H * point == q for point in values)
        assert all(point != curve(0) for point in values)
        return [{"x": str(code(point[0])), "y": str(code(point[1]))}
                for point in values]

    planted_fiber = fiber(planted_q)
    assert pair(raw_sum) in [[row["x"], row["y"]] for row in planted_fiber]
    public = {
        "schema_version": 1, "kind": "n83_w34_sat_public_input",
        "curve_id": protocol["curve_id"], "candidate_id": None,
        "field_degree": N, "field_polynomial_low_terms": [0, 2, 4, 7],
        "subgroup_order_decimal": str(R), "cofactor": H,
        "normal_element_polynomial_bits_decimal": str(code(alpha)),
        "normal_conjugates_polynomial_bits_decimal": [str(code(value)) for value in conjugates],
        "full_w4_geometry_sha256": sha(GEOMETRY / "geometry.json"),
        "planted": {"target_Q": pair(planted_q), "raw_target_fiber": planted_fiber},
        "ordinary": {"target_Q": pair(ordinary_q), "raw_target_fiber": fiber(ordinary_q)},
        "claim_boundary": protocol["claim_boundary"],
    }
    save(out / "public_input.json", public)
    private = {
        "schema_version": 1, "kind": "n83_w34_sat_private_fixture",
        "curve_id": protocol["curve_id"],
        "selected": [
            {"weight": len(mask), "orbit_ordinal": ordinal, "mask": list(mask),
             "raw_point": pair(point), "projected_point": pair(image)}
            for ordinal, mask, point, image in selected
        ],
        "raw_sum": pair(raw_sum), "planted_Q": pair(planted_q),
        "ordinary_fixture_scalar_decimal": str(ordinary_scalar),
        "ordinary_Q": pair(ordinary_q),
        "public_input_sha256": sha(out / "public_input.json"),
    }
    save(out / "private_fixture.json", private)
    print(json.dumps({"status": "PASS", "planted_Q": public["planted"]["target_Q"],
                      "ordinary_Q": public["ordinary"]["target_Q"],
                      "selected_masks": [row["mask"] for row in private["selected"]]}, sort_keys=True))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    main(parser.parse_args().out)
