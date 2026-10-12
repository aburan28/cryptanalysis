#!/usr/bin/env python3
"""Exact N83 search over the 72 one-coordinate affine cosets of W_11."""

from __future__ import annotations

import hashlib
import json
import math
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CODEGEN = ROOT / "ecc2k130/codegen"
PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path[:0] = [str(CODEGEN), str(PAIR)]

import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402

N = 83
D = 11
R = 2417851639230796216685689
KEY_BYTES = 21
ORBIT_SIZE = 2 * N
OUT = HERE / "runs/one_bit_cosets_20261011"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def scan(offset: int, onb, curve, orbit) -> tuple[dict, list[int]]:
    keys: set[int] = set()
    lifts = invalid = identities = projected_identities = duplicates = 0
    started = time.perf_counter_ns()
    for u in range(1 << D):
        coords = u ^ offset
        if not coords:
            identities += 1
            continue
        point = curve.pointFromX(onb.fromCoords(coords))
        if point is None:
            invalid += 1
            continue
        lifts += 1
        projected = curve.mul(point, 4)
        if projected is None:
            identities += 1
            projected_identities += 1
            continue
        key, _, _ = orbit.canonical(projected)
        if key in keys:
            duplicates += 1
        keys.add(key)
    ordered = sorted(keys)
    k = len(ordered)
    b = ORBIT_SIZE * k
    states = N * k * k
    row = {
        "offset_onb_coordinates": offset,
        "offset_bit": None if offset == 0 else offset.bit_length() - 1,
        "seed_count": 1 << D,
        "valid_lifts": lifts,
        "invalid_lifts": invalid,
        "identity_projections": identities,
        "duplicate_orbit_seeds": duplicates,
        "folded_columns_K": k,
        "actual_usable_points_B": b,
        "distinct_five_subset_first_moment": format(math.comb(b, 5) / R, ".12g"),
        "pair_root_states": states,
        "packed_descriptor_payload_upper_bytes": 32 * states,
        "scan_wall_ns": time.perf_counter_ns() - started,
    }
    assert lifts + invalid + (1 if offset == 0 else 0) == 1 << D
    assert lifts - projected_identities - duplicates == k
    return row, ordered


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    runtime_path = OUT / "sage_runtime_info.json"
    if json.loads(runtime_path.read_text()).get("status") != "verified":
        raise ValueError("save verified checked-Sage runtime receipt before sweeping")
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["offset_bits"] == list(range(D, N))
    assert protocol["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert not (OUT / "sweep.json").exists()
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    rows = []
    for offset in [0] + [1 << j for j in range(D, N)]:
        row, keys = scan(offset, onb, curve, orbit)
        rows.append(row)
        print(json.dumps({"offset_bit": row["offset_bit"], "K": row["folded_columns_K"]}), flush=True)
    winner = max(rows, key=lambda row: (row["folded_columns_K"], -row["offset_onb_coordinates"]))
    baseline = rows[0]
    for label, row in (("baseline", baseline), ("winner", winner)):
        _, keys = scan(row["offset_onb_coordinates"], onb, curve, orbit)
        payload = b"".join(key.to_bytes(KEY_BYTES, "little") for key in keys)
        path = OUT / f"{label}_canonical_keys.bin"
        path.write_bytes(payload)
        row["canonical_keys_sha256"] = sha(path)
        row["canonical_keys_file"] = path.name
        row["canonical_keys_bytes"] = len(payload)
        assert len(keys) == row["folded_columns_K"]
    receipt = {
        "kind": "n83_exact_one_bit_affine_coset_factor_base_sweep",
        "status": "completed_base_geometry_stage",
        "curve_id": protocol["curve_id"],
        "proposal_id": "Q20261011",
        "candidate_id": None,
        "workload_id": None,
        "run_id": None,
        "dimension": D,
        "selection_rule": "max K; ties use smallest offset coordinate integer",
        "baseline": baseline,
        "winner": winner,
        "rows": rows,
        "source_sha256": {"sweep": sha(Path(__file__)), "field": sha(CODEGEN / "field.py"),
                          "curve": sha(CODEGEN / "curves.py"), "orbit_key": sha(PAIR / "orbit_key.py"),
                          "protocol": sha(protocol_path), "sage_runtime_info": sha(runtime_path)},
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "natural_relation_yield": None,
        "factor_log_recovery": None,
        "one_target_online_ms": None,
        "rho_online_ms": None,
    }
    (OUT / "sweep.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
