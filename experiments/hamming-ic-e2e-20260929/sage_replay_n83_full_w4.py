#!/usr/bin/env python3
"""Independently replay all N83 weight-four mask orbits with Sage lift_x."""

from __future__ import annotations

import hashlib
import itertools
import json
from math import comb
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ, matrix, vector

from sage_replay_n83_next_geometry import digest, sha


N = 83
R = 2417851639230796216685689
H = 4
HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "n83_full_w4_protocol.json"
PREFIX = HERE / "runs/n83_next_geometry_v1"


def main(out: Path) -> None:
    out = out.resolve()
    started = time.perf_counter_ns()
    protocol = json.loads(PROTOCOL.read_text())
    record = json.loads((out / "geometry.json").read_text())
    archive = json.loads((out / "representatives.json").read_text())
    prefix = json.loads((PREFIX / "geometry.json").read_text())
    prefix_reps = json.loads((PREFIX / "representatives.json").read_text())
    assert record["status"] == "EXACT_GEOMETRY_PASS"
    assert record["curve_id"] == archive["curve_id"] == prefix["curve_id"] == protocol["curve_id"]
    assert record["protocol_sha256"] == sha(PROTOCOL)
    assert record["source_sha256"] == sha(HERE / "sage_measure_n83_full_w4.py")
    assert record["helper_source_sha256"] == sha(HERE / "sage_measure_n83_next_geometry.py")
    assert record["sage_runtime_info_sha256"] == sha(out / "sage_runtime_info.json")
    assert record["representatives_sha256"] == sha(out / "representatives.json")
    assert (out / "sage_runtime_info_replay.json").is_file()
    assert sha(PREFIX / "geometry.json") == protocol["input_prefix_geometry_sha256"]
    assert sha(PREFIX / "representatives.json") == protocol["input_prefix_representatives_sha256"]

    binary = GF(2)
    ring = PolynomialRing(binary, "v")
    v = ring.gen()
    field = GF(2**N, "w", modulus=v**N + v**7 + v**4 + v**2 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert ZZ(R).is_prime(proof=True) and curve.cardinality() == R * H

    def element(word):
        return field(ring([(word >> bit) & 1 for bit in range(N)]))

    def word(value):
        return sum(int(bit) << index for index, bit in enumerate(value.polynomial().list()))

    identity = record["curve_identity_record"]
    identity_bytes = json.dumps(identity, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=False).encode()
    assert record["curve_id"] == "EC1N83Ckb1h" + hashlib.sha256(identity_bytes).hexdigest()[:12]
    gx, gy = identity["curve"]["G"]
    generator = curve(element(gx), element(gy))
    assert generator != curve(0) and R * generator == curve(0)

    alpha = element(record["normal_element_polynomial_bits"])
    conjugates = [alpha]
    for _ in range(1, N):
        conjugates.append(conjugates[-1]**2)
    columns = [vector(binary, [(word(value) >> row) & 1 for row in range(N)])
               for value in conjugates]
    basis = matrix(binary, N, N, lambda row, col: columns[col][row])
    assert basis.rank() == N

    def orbit(point):
        px, py = point[0], point[1]
        values = set()
        for _ in range(N):
            xword, yword = word(px), word(py)
            values.update(((xword, yword), (xword, xword ^ yword)))
            px, py = px**2, py**2
        assert (px, py) == (point[0], point[1])
        assert len(values) == 2 * N
        return values

    representatives = {tuple(pair) for pair in prefix_reps["representatives"]}
    projected = set()
    for xword, yword in representatives:
        point = curve(element(xword), element(yword))
        assert R * point == curve(0)
        projected.update(orbit(point))
    assert len(projected) == prefix["checkpoints"][-1]["actual_usable_projected_points_B"]
    assert digest(projected) == prefix["projected_point_set_sha256"]
    assert record["checkpoints"][0] == prefix["checkpoints"][-1]

    seen_masks = set()
    count = rational = nonrational = duplicates = identities = 0
    rational = prefix["w4_rational_orbits"]
    nonrational = prefix["w4_nonrational_orbits"]
    duplicates = prefix["w4_duplicate_projected_orbits"]
    identities = prefix["w4_identity_projections"]
    checkpoint_index = 1
    for mask in itertools.combinations(range(N), 4):
        if mask in seen_masks:
            continue
        orbit_masks = {tuple(sorted((bit + shift) % N for bit in mask))
                       for shift in range(N)}
        assert len(orbit_masks) == N
        seen_masks.update(orbit_masks)
        count += 1
        if count <= 4000:
            continue
        x = sum((conjugates[bit] for bit in mask), field(0))
        lifts = list(curve.lift_x(x, all=True))
        if not lifts:
            nonrational += 1
        else:
            rational += 1
            assert len(lifts) == 2 and lifts[0] == -lifts[1]
            image = H * lifts[0]
            if image == curve(0):
                identities += 1
            else:
                assert R * image == curve(0)
                values = orbit(image)
                representative = min(values)
                if representative in representatives:
                    duplicates += 1
                else:
                    representatives.add(representative)
                    projected.update(values)
        if count == protocol["checkpoints_w4_mask_orbits"][checkpoint_index]:
            checkpoint = record["checkpoints"][checkpoint_index]
            assert checkpoint["w4_mask_orbits"] == count
            assert checkpoint["w4_rational_orbits"] == rational
            assert checkpoint["w4_nonrational_orbits"] == nonrational
            assert checkpoint["actual_usable_projected_points_B"] == len(projected)
            assert checkpoint["effective_signed_frobenius_columns"] == len(representatives)
            assert checkpoint["root_index_pair_state_loops_NK2"] == N * len(representatives)**2
            for m in (4, 5, 6):
                assert int(checkpoint["multisets_with_repetition"][str(m)]) == comb(len(projected) + m - 1, m)
            checkpoint_index += 1
            if checkpoint_index == len(protocol["checkpoints_w4_mask_orbits"]):
                break

    assert count == protocol["expected_w4_mask_orbits"] == record["w4_mask_orbits"]
    assert len(seen_masks) == N * count == comb(N, 4)
    assert rational == record["w4_rational_orbits"]
    assert nonrational == record["w4_nonrational_orbits"]
    assert duplicates == record["w4_duplicate_projected_orbits"]
    assert identities == record["w4_identity_projections"]
    assert {tuple(pair) for pair in archive["representatives"]} == representatives
    assert digest(projected) == record["projected_point_set_sha256"]
    assert len(projected) == 2 * N * len(representatives)

    report = {
        "schema_version": 1, "kind": "n83_complete_w4_geometry_independent_replay",
        "status": "PASS", "curve_id": record["curve_id"],
        "normal_basis_rank": int(basis.rank()),
        "w4_mask_orbits_replayed": count,
        "w4_rational_orbits": rational,
        "actual_usable_projected_points_B": len(projected),
        "effective_signed_frobenius_columns": len(representatives),
        "projected_point_set_sha256": digest(projected),
        "geometry_sha256": sha(out / "geometry.json"),
        "representatives_sha256": sha(out / "representatives.json"),
        "sage_runtime_info_replay_sha256": sha(out / "sage_runtime_info_replay.json"),
        "replay_source_sha256": sha(Path(__file__)),
        "replay_wall_ms": (time.perf_counter_ns() - started) / 1e6,
        "claim_boundary": protocol["claim_boundary"],
    }
    (out / "sage_replay.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "w4_mask_orbits_replayed": count,
                      "actual_usable_projected_points_B": len(projected)}, sort_keys=True))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    main(parser.parse_args().out)
