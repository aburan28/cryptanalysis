#!/usr/bin/env python3
"""Independently replay the frozen N83 W3/W4 SAT public/private fixture."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ, matrix, vector


N = 83
R = 2417851639230796216685689
H = 4
HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "n83_w34_sat_protocol.json"
GEOMETRY = HERE / "runs/n83_full_w4_geometry_v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(out):
    out = out.resolve()
    started = time.perf_counter_ns()
    protocol = json.loads(PROTOCOL.read_text())
    public = json.loads((out / "public_input.json").read_text())
    private = json.loads((out / "private_fixture.json").read_text())
    geometry = json.loads((GEOMETRY / "geometry.json").read_text())
    representatives = json.loads((GEOMETRY / "representatives.json").read_text())
    receipt = json.loads((out / "started.json").read_text())
    assert sha(GEOMETRY / "geometry.json") == protocol["full_w4_geometry_sha256"]
    assert sha(GEOMETRY / "representatives.json") == protocol["full_w4_representatives_sha256"]
    assert sha(GEOMETRY / "sage_replay.json") == protocol["full_w4_independent_replay_sha256"]
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["source_sha256"] == sha(HERE / "sage_make_n83_w34_sat_fixture.py")
    assert receipt["sage_runtime_info_sha256"] == sha(out / "sage_runtime_info.json")
    assert (out / "sage_runtime_info_replay.json").is_file()
    assert private["public_input_sha256"] == sha(out / "public_input.json")
    assert public["curve_id"] == private["curve_id"] == geometry["curve_id"] == protocol["curve_id"]
    assert public["field_degree"] == N and public["field_polynomial_low_terms"] == [0, 2, 4, 7]

    binary = GF(2)
    ring = PolynomialRing(binary, "v")
    v = ring.gen()
    field = GF(2**N, "w", modulus=v**N + v**7 + v**4 + v**2 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert ZZ(R).is_prime(proof=True) and curve.cardinality() == H * R

    def element(word):
        return field(ring([(word >> bit) & 1 for bit in range(N)]))

    def word(value):
        return sum(int(bit) << index for index, bit in enumerate(value.polynomial().list()))

    def point(encoded):
        assert encoded is not None and len(encoded) == 2
        return curve(element(int(encoded[0])), element(int(encoded[1])))

    def pair(value):
        assert value != curve(0)
        return [str(word(value[0])), str(word(value[1]))]

    alpha = element(int(public["normal_element_polynomial_bits_decimal"]))
    conjugates = [alpha]
    for _ in range(1, N):
        conjugates.append(conjugates[-1]**2)
    assert [str(word(value)) for value in conjugates] == public["normal_conjugates_polynomial_bits_decimal"]
    columns = [vector(binary, [(word(value) >> row) & 1 for row in range(N)])
               for value in conjugates]
    assert matrix(binary, N, N, lambda row, col: columns[col][row]).rank() == N

    rep_set = {tuple(row) for row in representatives["representatives"]}

    def orbit_key(value):
        x, y = value[0], value[1]
        keys = set()
        for _ in range(N):
            xword, yword = word(x), word(y)
            keys.update(((xword, yword), (xword, xword ^ yword)))
            x, y = x**2, y**2
        assert len(keys) == 2 * N
        return min(keys)

    selected = private["selected"]
    assert len(selected) == 5
    lower_bounds = (protocol["planted_w3_orbit_lower_bounds"],
                    protocol["planted_w4_orbit_lower_bounds"])
    found = []
    for weight, bounds in zip((3, 4), lower_bounds):
        seen = set()
        ordinal = 0
        cursor = 0
        for mask in itertools.combinations(range(N), weight):
            if mask in seen:
                continue
            shifts = {tuple(sorted((bit + shift) % N for bit in mask))
                      for shift in range(N)}
            assert len(shifts) == N
            seen.update(shifts)
            ordinal += 1
            if ordinal < bounds[cursor]:
                continue
            x = sum((conjugates[bit] for bit in mask), field(0))
            lifts = list(curve.lift_x(x, all=True))
            if not lifts:
                continue
            raw = min(lifts, key=lambda value: word(value[1]))
            projected = H * raw
            assert projected != curve(0) and R * projected == curve(0)
            assert orbit_key(projected) in rep_set
            found.append({"weight": weight, "orbit_ordinal": ordinal,
                          "mask": list(mask), "raw_point": pair(raw),
                          "projected_point": pair(projected)})
            cursor += 1
            if cursor == len(bounds):
                break
        assert cursor == len(bounds)
    assert found == selected

    raw = [point(row["raw_point"]) for row in selected]
    for size in range(1, len(raw)):
        for subset in itertools.combinations(raw, size):
            assert sum(subset, curve(0)) != curve(0)
    raw_sum = sum(raw, curve(0))
    planted_q = H * raw_sum
    assert pair(raw_sum) == private["raw_sum"]
    assert pair(planted_q) == private["planted_Q"] == public["planted"]["target_Q"]
    gx, gy = geometry["curve_identity_record"]["curve"]["G"]
    generator = curve(element(gx), element(gy))
    scalar = 1 + int.from_bytes(hashlib.sha256(b"n83-w34-ordinary-v1-0").digest(), "big") % (R - 1)
    ordinary_q = scalar * generator
    assert str(scalar) == private["ordinary_fixture_scalar_decimal"]
    assert pair(ordinary_q) == private["ordinary_Q"] == public["ordinary"]["target_Q"]

    kernel = [curve(0), curve(field(0), field(1)),
              curve(field(1), field(0)), curve(field(1), field(1))]
    assert len(set(kernel)) == 4 and all(H * value == curve(0) for value in kernel)
    for label, q in (("planted", planted_q), ("ordinary", ordinary_q)):
        root = pow(H, -1, R) * q
        fiber = [root + value for value in kernel]
        assert len(set(fiber)) == 4 and all(H * value == q for value in fiber)
        expected = [{"x": str(word(value[0])), "y": str(word(value[1]))}
                    for value in fiber]
        assert public[label]["raw_target_fiber"] == expected
    assert private["raw_sum"] in [[row["x"], row["y"]]
                                  for row in public["planted"]["raw_target_fiber"]]

    report = {
        "schema_version": 1,
        "kind": "n83_w34_sat_fixture_independent_replay",
        "status": "PASS",
        "curve_id": protocol["curve_id"],
        "selected_weight_mix": [row["weight"] for row in found],
        "planted_raw_sum_replayed": True,
        "both_four_point_target_fibers_replayed": True,
        "ordinary_scalar_derivation_replayed": True,
        "public_input_sha256": sha(out / "public_input.json"),
        "private_fixture_sha256": sha(out / "private_fixture.json"),
        "protocol_sha256": sha(PROTOCOL),
        "replay_source_sha256": sha(Path(__file__)),
        "sage_runtime_info_replay_sha256": sha(out / "sage_runtime_info_replay.json"),
        "replay_wall_ms": (time.perf_counter_ns() - started) / 1e6,
        "claim_boundary": protocol["claim_boundary"],
    }
    (out / "sage_replay.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "selected_weight_mix": report["selected_weight_mix"]}, sort_keys=True))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    main(parser.parse_args().out)
