#!/usr/bin/env python3
"""Derive a public six-summand positive control by removing a planted pair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n83-costed-candidate-screen-20261005"
sys.path.insert(0, str(HERE.parent / "pdp-scaling"))
from gf2n import Curve, GF2n, INF, Point  # noqa: E402

PROTOCOL = HERE / "residual_six_protocol.json"
FIXTURE_DIR = PRIOR / "runs/shifted_m8_d11_sat_fixture_v1"
R = 2417851639230796216685689


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def times(curve: Curve, count: int, point: Point) -> Point:
    result = INF
    while count:
        if count & 1:
            result = curve.add(result, point)
        point = curve.add(point, point)
        count >>= 1
    return result


def pair(point: Point) -> list[str]:
    assert not point.inf
    return [str(point.x), str(point.y)]


def main(out: Path) -> None:
    out = out.resolve()
    if out.exists():
        raise FileExistsError("residual-six fixture output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    public_path = FIXTURE_DIR / "public_input.json"
    private_path = FIXTURE_DIR / "private_fixture.json"
    prior_replay_path = FIXTURE_DIR / "independent_replay.json"
    public = json.loads(public_path.read_text())
    private = json.loads(private_path.read_text())
    prior_replay = json.loads(prior_replay_path.read_text())
    assert sha(public_path) == protocol["source_public_fixture_sha256"]
    assert sha(private_path) == protocol["source_private_fixture_sha256_local_only"]
    assert public["private_witness_commitment_sha256"] == \
        protocol["source_witness_commitment_sha256"]
    assert private["public_input_sha256"] == sha(public_path)
    assert hashlib.sha256(canonical(private["witness"])).hexdigest() == \
        public["private_witness_commitment_sha256"]
    assert prior_replay["status"] == "PASS" and prior_replay["label"] == "shifted_m8_d11"
    assert public["curve_id"] == protocol["curve_id"]
    assert protocol["removed_pair_slot_indices"] == [0, 1]
    assert protocol["remaining_slot_indices"] == list(range(2, 8))
    out.mkdir(parents=True)
    save(out / "started.json", {
        "kind": "n83_shifted_m8_residual_six_fixture_start",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(PROTOCOL),
        "source_public_fixture_sha256": sha(public_path),
        "source_private_fixture_sha256_local_only": sha(private_path),
        "source_independent_replay_sha256": sha(prior_replay_path),
        "source_sha256": sha(Path(__file__)),
    })
    started = time.perf_counter_ns()
    field = GF2n(83, (1 << 83) | (1 << 7) | (1 << 4) | (1 << 2) | 1)
    curve = Curve(field, 1)
    selected = private["witness"]["selected"]
    assert len(selected) == 8 and [row["slot"] for row in selected] == list(range(8))
    raw = [Point(*map(int, row["raw_point"])) for row in selected]
    assert all(curve.on_curve(point) and point != INF for point in raw)
    raw_sum = curve.sum(raw)
    assert pair(raw_sum) == private["witness"]["raw_sum"]
    removed = curve.add(raw[0], raw[1])
    residual = curve.add(raw_sum, curve.neg(removed))
    assert residual == curve.sum(raw[2:]) != INF
    q = times(curve, 4, residual)
    assert q != INF and times(curve, R, q) == INF
    original_q = times(curve, 4, raw_sum)
    assert pair(original_q) == public["planted"]["target_Q"]
    assert curve.add(q, times(curve, 4, removed)) == original_q
    remaining_private = {
        "selected": selected[2:],
        "raw_residual_sum": pair(residual),
        "projected_residual_target": pair(q),
    }
    fixture = {
        "schema_version": 1,
        "kind": "n83_shifted_m8_residual_six_public_fixture",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "source_public_fixture_sha256": sha(public_path),
        "source_witness_commitment_sha256":
            public["private_witness_commitment_sha256"],
        "removed_pair_slot_indices": [0, 1],
        "removed_pair_raw_points": [pair(raw[0]), pair(raw[1])],
        "removed_pair_masks_decimal": [selected[0]["mask_decimal"],
                                       selected[1]["mask_decimal"]],
        "remaining_slot_indices": list(range(2, 8)),
        "raw_residual_target": pair(residual),
        "projected_residual_target_Q": pair(q),
        "private_remaining_witness_commitment_sha256":
            hashlib.sha256(canonical(remaining_private)).hexdigest(),
        "protocol_sha256": sha(PROTOCOL),
        "claim_boundary": protocol["claim_boundary"],
    }
    save(out / "public_input.json", fixture)
    save(out / "private_fixture.json", {
        "schema_version": 1,
        "kind": "n83_shifted_m8_residual_six_private_fixture",
        "public_input_sha256": sha(out / "public_input.json"),
        "source_private_fixture_sha256": sha(private_path),
        "remaining_witness": remaining_private,
    })
    save(out / "receipt.json", {
        "schema_version": 1,
        "kind": "n83_shifted_m8_residual_six_fixture_receipt",
        "status": "PASS", "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "removed_pair_raw_sum_verified": True,
        "six_factor_raw_sum_verified": True,
        "cofactor_projected_target_verified": True,
        "subgroup_order_verified": True,
        "public_input_sha256": sha(out / "public_input.json"),
        "private_fixture_sha256_local_only": sha(out / "private_fixture.json"),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "wall_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
        "claim_boundary": protocol["claim_boundary"],
    })
    print(json.dumps({"status": "PASS", "remaining_summands": 6,
                      "projected_target_Q": pair(q)}, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: make_residual_six_fixture.py OUTPUT_DIRECTORY")
    main(Path(sys.argv[1]))
