#!/usr/bin/env python3
"""Create an N83 planted shifted-base target; keep its witness local."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "shifted_sat_protocol.json"
OLD_PUBLIC = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json"
N = 83
R = 2417851639230796216685689
H = 4


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main(label: str, out: Path, seed_path: Path) -> None:
    out, seed_path = out.resolve(), seed_path.resolve()
    runtime = out / "sage_runtime_info.json"
    if not out.is_dir() or not runtime.is_file():
        raise FileNotFoundError("save checked Sage runtime beside output first")
    if (out / "started.json").exists() or (out / "public_input.json").exists():
        raise FileExistsError("fixture output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    old_public = json.loads(OLD_PUBLIC.read_text())
    options = {item["label"]: item for item in protocol["geometry"]}
    if label not in options:
        raise ValueError("unknown frozen label")
    seed = seed_path.read_bytes()
    if len(seed) != 32 or sha(seed_path) != protocol["planted_selection_seed_sha256"]:
        raise ValueError("wrong local selection seed")
    geometry_path = HERE / "runs" / f"{label}_v1" / "geometry.json"
    geometry = json.loads(geometry_path.read_text())
    assert sha(geometry_path) == options[label]["geometry_sha256"]
    assert sha(OLD_PUBLIC) == protocol["public_ordinary_input_sha256"]
    assert geometry["status"] == "EXACT_GEOMETRY_PASS"
    assert geometry["curve_id"] == old_public["curve_id"] == protocol["curve_id"]
    started = time.perf_counter_ns()
    save(out / "started.json", {
        "kind": "n83_shifted_sat_fixture_start", "candidate_id": None,
        "label": label, "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(PROTOCOL), "geometry_sha256": sha(geometry_path),
        "seed_sha256_local_only": sha(seed_path),
        "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime),
    })

    f2 = GF(2)
    ring = PolynomialRing(f2, "u")
    u = ring.gen()
    field = GF(2**N, "z", modulus=u**N + u**7 + u**4 + u**2 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    identity = curve(0)
    assert ZZ(R).is_prime(proof=True) and curve.cardinality() == H * R

    def element(bits: int):
        return field(ring([(bits >> bit) & 1 for bit in range(N)]))

    def word(value) -> int:
        return sum(int(coefficient) << bit for bit, coefficient in
                   enumerate(value.polynomial().list()))

    def pair(point):
        assert point != identity
        return [str(word(point[0])), str(word(point[1]))]

    conjugates = [element(int(value)) for value in
                  old_public["normal_conjugates_polynomial_bits_decimal"]]
    assert len(conjugates) == N and all(conjugates[i]**2 == conjugates[(i + 1) % N]
                                        for i in range(N))
    packed = HERE / "runs" / f"{label}_v1" / "representatives.json.gz"
    raw_representatives = gzip.decompress(packed.read_bytes())
    assert hashlib.sha256(raw_representatives).hexdigest() == geometry["representatives_sha256"]
    representative_set = {tuple(row) for row in
                          json.loads(raw_representatives)["representatives"]}

    def orbit_key(point):
        x, y = point[0], point[1]
        values = []
        for _ in range(N):
            xword, yword = word(x), word(y)
            values.extend(((xword, yword), (xword, xword ^ yword)))
            x, y = x**2, y**2
        return min(values)

    slots = geometry["slot_normal_basis_indices"]
    m, d = geometry["arity"], geometry["dimension"]
    assert len(slots) == m
    selected = []
    used_orbits = set()
    raw_sum = identity
    for slot_index, slot in enumerate(slots):
        maximum = (1 << d) - 1
        digest = hashlib.sha256(seed + label.encode() + bytes([slot_index])).digest()
        initial = 1 + int.from_bytes(digest, "big") % maximum
        for shift in range(maximum):
            mask = 1 + ((initial - 1 + shift) % maximum)
            x = sum((conjugates[slot[bit]] for bit in range(d)
                     if mask & (1 << bit)), field(0))
            if x == 0:
                continue
            lifts = list(curve.lift_x(x, all=True))
            if len(lifts) != 2:
                continue
            point = min(lifts, key=lambda value: word(value[1]))
            projected = H * point
            if projected == identity or R * projected != identity:
                continue
            key = orbit_key(projected)
            if key not in representative_set or key in used_orbits:
                continue
            next_sum = raw_sum + point
            if next_sum == identity or (slot_index == m - 1 and H * next_sum == identity):
                continue
            selected.append({
                "slot": slot_index, "mask_decimal": str(mask),
                "selected_after_trials": shift + 1,
                "raw_point": pair(point), "projected_point": pair(projected),
                "orbit_representative": [str(key[0]), str(key[1])],
            })
            used_orbits.add(key)
            raw_sum = next_sum
            break
        else:
            raise RuntimeError(f"no regular planted factor for slot {slot_index}")
    assert raw_sum != identity and H * raw_sum != identity
    target_q = H * raw_sum
    assert R * target_q == identity
    torsion = [identity, curve(field(0), field(1)),
               curve(field(1), field(0)), curve(field(1), field(1))]
    assert len(set(torsion)) == 4 and all(H * value == identity for value in torsion)
    root = pow(H, -1, R) * target_q
    fiber = [root + value for value in torsion]
    assert len(set(fiber)) == 4 and all(H * value == target_q for value in fiber)
    assert pair(raw_sum) in [pair(value) for value in fiber]

    witness = {"selected": selected, "raw_sum": pair(raw_sum),
               "target_Q": pair(target_q)}
    public = {
        "schema_version": 1, "kind": "n83_shifted_sat_public_fixture",
        "label": label, "curve_id": protocol["curve_id"], "candidate_id": None,
        "geometry_sha256": sha(geometry_path), "protocol_sha256": sha(PROTOCOL),
        "old_ordinary_public_input_sha256": sha(OLD_PUBLIC),
        "planted": {"target_Q": pair(target_q),
                    "raw_target_fiber": [{"x": str(word(value[0])),
                                          "y": str(word(value[1]))} for value in fiber]},
        "ordinary": old_public["ordinary"],
        "private_witness_commitment_sha256": hashlib.sha256(canonical(witness)).hexdigest(),
        "claim_boundary": protocol["claim_boundary"],
    }
    save(out / "public_input.json", public)
    private = {
        "schema_version": 1, "kind": "n83_shifted_sat_private_fixture",
        "label": label, "curve_id": protocol["curve_id"],
        "seed_sha256": sha(seed_path), "witness": witness,
        "public_input_sha256": sha(out / "public_input.json"),
    }
    save(out / "private_fixture.json", private)
    save(out / "receipt.json", {
        "schema_version": 1, "kind": "n83_shifted_sat_fixture_receipt",
        "status": "PASS", "label": label, "candidate_id": None,
        "curve_id": protocol["curve_id"], "factor_count": m,
        "all_factors_in_measured_base_orbits": True,
        "all_prefix_sums_nonidentity": True,
        "raw_target_fiber_count": 4,
        "public_input_sha256": sha(out / "public_input.json"),
        "private_fixture_sha256_local_only": sha(out / "private_fixture.json"),
        "witness_commitment_sha256": public["private_witness_commitment_sha256"],
        "source_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(PROTOCOL),
        "sage_runtime_info_sha256": sha(runtime),
        "wall_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
        "claim_boundary": protocol["claim_boundary"],
    })
    print(json.dumps({"status": "PASS", "label": label,
                      "factor_count": m, "target_Q": pair(target_q)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("out", type=Path)
    parser.add_argument("seed", type=Path)
    args = parser.parse_args()
    main(args.label, args.out, args.seed)
