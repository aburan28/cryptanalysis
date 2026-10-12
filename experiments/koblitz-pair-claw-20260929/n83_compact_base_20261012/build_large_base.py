#!/usr/bin/env python3
"""Extend the frozen seeded N83 known-log orbit set to 200,000 columns."""

import hashlib
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent
ROOT = PAIR.parents[1]
CODEGEN = ROOT / "ecc2k130/runner/codegen"
sys.path[:0] = [str(CODEGEN), str(PAIR)]

import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402

K = 200_000
PARENT = PAIR / "runs/n83_knownlog_orbit_base_k48194.json"
BASE = HERE / "large_base_keys_and_logs.bin"
OUTPUT = HERE / "large_base.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not BASE.exists() and not OUTPUT.exists(), "large base already frozen"
    parent = json.loads(PARENT.read_text())
    model = parent["curve_identity_record"]["curve"]
    old = parent["factor_base"]
    assert parent["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert old["selected_point_orbits"] == 48194 and old["seed"] == 831043
    old_path = PAIR / old["key_and_log_file"]
    assert sha(old_path) == old["key_and_log_file_sha256"]
    old_bytes = old_path.read_bytes()
    old_entries = {
        int.from_bytes(old_bytes[i:i + 21], "little"):
        int.from_bytes(old_bytes[i + 21:i + 32], "little")
        for i in range(0, len(old_bytes), 32)
    }
    assert len(old_entries) == 48194
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    order = model["subgroup_order"]
    eigen = old["frobenius_eigenvalue_mod_r"]
    generator = tuple(model["generator"])
    assert curves.isPrimeBig(order)
    assert curve.mul(generator, order) is None
    assert curve.mul(generator, eigen) == curve.frob(generator)
    assert pow(eigen, 83, order) == 1
    rng = random.Random(831043)
    entries = {}
    draws = duplicates = 0
    started = time.perf_counter()
    while len(entries) < K:
        scalar = rng.randrange(1, order)
        draws += 1
        point = curve.mul(generator, scalar)
        key, exponent, sign = orbit.canonical(point)
        assert key != -1 and 0 <= exponent < 83 and sign in (-1, 1)
        log = sign * pow(eigen, exponent, order) * scalar % order
        if key in entries:
            duplicates += 1
            assert entries[key] == log
        else:
            entries[key] = log
        if len(entries) == 48194:
            assert len(entries) == len(old_entries)
            assert entries == old_entries, "new stream diverged from verified base"
        if draws % 10000 == 0:
            print(json.dumps({"draws": draws, "K": len(entries),
                              "elapsed_seconds": time.perf_counter() - started}),
                  flush=True)
    ordered = sorted(entries)
    with BASE.open("xb") as stream:
        for key in ordered:
            stream.write(key.to_bytes(21, "little"))
            stream.write(entries[key].to_bytes(11, "little"))
    key_stream = b"".join(key.to_bytes(21, "little") for key in ordered)
    log_stream = b"".join(entries[key].to_bytes(11, "little") for key in ordered)
    for index in (0, 1, 42, 1024, 48193, K // 2, K - 1):
        key = ordered[index]
        representative = orbit.point_from_key(key)
        assert representative is not None and curve.onCurve(representative)
        assert curve.mul(generator, entries[key]) == representative
    record = {
        "kind": "n83_seeded_200000_orbit_knownlog_base",
        "curve_id": parent["curve_id"],
        "candidate_id": None,
        "seed": 831043,
        "seed_scalar_rng": old["seed_scalar_rng"],
        "K": K,
        "actual_usable_points_B_before_folding": 166 * K,
        "drawn_scalars": draws,
        "duplicate_orbit_draws": duplicates,
        "subgroup_order": order,
        "frobenius_eigenvalue_mod_r": eigen,
        "canonical_key_sha256": hashlib.sha256(key_stream).hexdigest(),
        "canonical_log_sha256": hashlib.sha256(log_stream).hexdigest(),
        "key_and_log_file_sha256": sha(BASE),
        "key_and_log_file_bytes": BASE.stat().st_size,
        "pair_rank_domain": 83 * K * (K - 1),
        "m32_table_plus_disjoint_query_capacity": 83 * K * (K - 1) - (1 << 32),
        "verified_parent_K": 48194,
        "verified_parent_file_sha256": sha(old_path),
        "parent_receipt_sha256": sha(PARENT),
        "source_sha256": {"builder": sha(Path(__file__)),
                          "curves": sha(CODEGEN / "curves.py"),
                          "field": sha(CODEGEN / "field.py"),
                          "orbit_key": sha(PAIR / "orbit_key.py")},
        "target_independent_build_seconds_exploratory": time.perf_counter() - started,
        "verification": "complete seeded parent match and selected group-law log replay",
    }
    OUTPUT.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "complete", "K": K, "B": 166 * K,
                      "base_sha256": record["key_and_log_file_sha256"]}), flush=True)


if __name__ == "__main__":
    main()
