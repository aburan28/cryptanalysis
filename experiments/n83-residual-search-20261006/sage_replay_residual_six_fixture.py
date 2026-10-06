#!/usr/bin/env python3
"""Independently replay the pair-prefix residual-six planted fixture in Sage."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n83-costed-candidate-screen-20261005"
FOLDER = HERE / "runs/planted_pair01_fixture_v1"
PROTOCOL = HERE / "residual_six_protocol.json"
SOURCE_PUBLIC = PRIOR / "runs/shifted_m8_d11_sat_fixture_v1/public_input.json"
OLD_PUBLIC = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json"
GEOMETRY = PRIOR / "runs/shifted_m8_d11_v1/geometry.json"
R = 2417851639230796216685689


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    runtime = FOLDER / "sage_replay_runtime_info.json"
    output = FOLDER / "sage_replay.json"
    if not runtime.is_file() or output.exists():
        raise FileExistsError("save a fresh checked Sage runtime before immutable replay")
    protocol = json.loads(PROTOCOL.read_text())
    public_path = FOLDER / "public_input.json"
    private_path = FOLDER / "private_fixture.json"
    public = json.loads(public_path.read_text())
    private = json.loads(private_path.read_text())
    source = json.loads(SOURCE_PUBLIC.read_text())
    old = json.loads(OLD_PUBLIC.read_text())
    geometry = json.loads(GEOMETRY.read_text())
    assert public["protocol_sha256"] == sha(PROTOCOL)
    assert private["public_input_sha256"] == sha(public_path)
    assert public["source_public_fixture_sha256"] == sha(SOURCE_PUBLIC)
    assert public["private_remaining_witness_commitment_sha256"] == \
        hashlib.sha256(canonical(private["remaining_witness"])).hexdigest()
    assert public["curve_id"] == source["curve_id"] == geometry["curve_id"] == \
        protocol["curve_id"]
    assert public["remaining_slot_indices"] == list(range(2, 8))
    started = time.perf_counter_ns()
    f2 = GF(2)
    ring = PolynomialRing(f2, "u")
    u = ring.gen()
    field = GF(2**83, "z", modulus=u**83 + u**7 + u**4 + u**2 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    identity = curve(0)
    assert curve.cardinality() == 4 * R and ZZ(R).is_prime(proof=True)

    def element(bits: int):
        return field(ring([(bits >> bit) & 1 for bit in range(83)]))

    def word(value) -> int:
        return sum(int(coefficient) << bit for bit, coefficient in
                   enumerate(value.polynomial().list()))

    def point(value):
        result = curve(element(int(value[0])), element(int(value[1])))
        assert result != identity
        return result

    def pair(value):
        assert value != identity
        return [str(word(value[0])), str(word(value[1]))]

    def orbit_key(value):
        x, y = value[0], value[1]
        keys = []
        for _ in range(83):
            a, b = word(x), word(y)
            keys.extend(((a, b), (a, a ^ b)))
            x, y = x**2, y**2
        return min(keys)

    representatives_path = GEOMETRY.parent / "representatives.json.gz"
    raw_reps = gzip.decompress(representatives_path.read_bytes())
    assert hashlib.sha256(raw_reps).hexdigest() == geometry["representatives_sha256"]
    reps = {tuple(row) for row in json.loads(raw_reps)["representatives"]}
    conjugates = [element(int(value)) for value in
                  old["normal_conjugates_polynomial_bits_decimal"]]
    selected = private["remaining_witness"]["selected"]
    assert len(selected) == 6 and [row["slot"] for row in selected] == list(range(2, 8))
    prefix = identity
    prior_x = None
    for row in selected:
        slot = geometry["slot_normal_basis_indices"][row["slot"]]
        mask = int(row["mask_decimal"])
        assert 1 <= mask < (1 << len(slot))
        x = sum((conjugates[slot[bit]] for bit in range(len(slot))
                 if mask & (1 << bit)), field(0))
        raw = point(row["raw_point"])
        assert raw[0] == x
        projected = 4 * raw
        assert projected != identity and R * projected == identity
        assert orbit_key(projected) in reps
        prefix += raw
        assert prefix != identity
        if prior_x is not None:
            e2 = prior_x * raw[0] + prior_x * prefix[0] + raw[0] * prefix[0]
            assert e2**2 + prior_x * raw[0] * prefix[0] + field(1) == 0
        prior_x = prefix[0]
    assert pair(prefix) == public["raw_residual_target"]
    assert pair(4 * prefix) == public["projected_residual_target_Q"]
    removed = point(public["removed_pair_raw_points"][0]) + \
        point(public["removed_pair_raw_points"][1])
    assert pair(4 * (removed + prefix)) == source["planted"]["target_Q"]
    assert pair(prefix) == private["remaining_witness"]["raw_residual_sum"]
    receipt = {
        "schema_version": 1,
        "kind": "n83_shifted_m8_residual_six_fixture_sage_replay",
        "status": "PASS", "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "all_six_masks_in_exact_slots": True,
        "all_projected_factors_in_measured_base_orbits": True,
        "all_residual_prefixes_nonidentity": True,
        "all_five_s3_links_zero": True,
        "raw_residual_group_sum_verified": True,
        "cofactor_and_original_target_verified": True,
        "public_fixture_sha256": sha(public_path),
        "private_fixture_sha256_local_only": sha(private_path),
        "source_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(PROTOCOL),
        "sage_replay_runtime_info_sha256": sha(runtime),
        "wall_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
        "claim_boundary": "Planted residual-six correctness only; no unpinned solve or ordinary yield.",
    }
    save(output, receipt)
    print(json.dumps({"status": "PASS", "remaining_summands": 6}, sort_keys=True))


if __name__ == "__main__":
    main()
