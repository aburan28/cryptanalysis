#!/usr/bin/env python3
"""Derive the smallest seeded known-log base for one M32 plus 80 R29 ranges."""

import hashlib
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CODEGEN = ROOT.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))
sys.path.insert(0, str(ROOT))

import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402

K = 23859
L = 166
M = 1 << 32
R = 80 * (1 << 29)
PARENT = ROOT / "runs" / "n83_knownlog_orbit_base.json"
OUTPUT = HERE / "minimal_base.json"
BASE = HERE / "minimal_base_keys_and_logs.bin"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert 83 * (K - 1) * (K - 2) < M + R <= 83 * K * (K - 1)
    parent = json.loads(PARENT.read_text())
    identity = parent["curve_identity_record"]
    base = parent["factor_base"]
    assert parent["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert base["seed"] == 831043 and base["selected_point_orbits"] == 24097
    order = identity["curve"]["subgroup_order"]
    eigen = base["frobenius_eigenvalue_mod_r"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    generator = tuple(identity["curve"]["generator"])
    assert curves.isPrimeBig(order)
    assert curve.mul(generator, order) is None
    assert curve.mul(generator, eigen) == curve.frob(generator)
    assert pow(eigen, 83, order) == 1
    parent_file = ROOT / base["key_and_log_file"]
    assert sha(parent_file) == base["key_and_log_file_sha256"]
    raw = parent_file.read_bytes()
    assert len(raw) == 24097 * 32
    parent_entries = {
        int.from_bytes(raw[i:i + 21], "little"):
        int.from_bytes(raw[i + 21:i + 32], "little")
        for i in range(0, len(raw), 32)
    }
    assert len(parent_entries) == 24097
    rng = random.Random(base["seed"])
    entries = {}
    draws = 0
    start = time.perf_counter()
    while len(entries) < K:
        scalar = rng.randrange(1, order)
        draws += 1
        point = curve.mul(generator, scalar)
        key, exponent, sign = orbit.canonical(point)
        log = sign * pow(eigen, exponent, order) * scalar % order
        assert parent_entries[key] == log
        entries.setdefault(key, log)
    build_seconds = time.perf_counter() - start
    keys = sorted(entries)
    assert len(keys) == K
    assert keys == sorted(set(keys))
    key_stream = b"".join(key.to_bytes(21, "little") for key in keys)
    log_stream = b"".join(entries[key].to_bytes(11, "little") for key in keys)
    BASE.write_bytes(b"".join(
        key.to_bytes(21, "little") + entries[key].to_bytes(11, "little")
        for key in keys))
    # Re-read the artifact and check selected group-law log certificates.
    written = BASE.read_bytes()
    assert len(written) == K * 32
    for index in (0, 1, 42, 1024, K // 2, K - 1):
        key = int.from_bytes(written[index * 32:index * 32 + 21], "little")
        log = int.from_bytes(written[index * 32 + 21:(index + 1) * 32], "little")
        representative = orbit.point_from_key(key)
        assert representative is not None and curve.onCurve(representative)
        assert curve.mul(generator, log) == representative
    record = {
        "kind": "n83_minimum_orbit_count_knownlog_factor_base",
        "curve_id": parent["curve_id"],
        "curve_identity_record": identity,
        "isogeny": "none",
        "candidate_id": None,
        "factor_base": {
            "construction": "first 23,859 distinct signed-Frobenius orbits from the Q1043 seeded scalar stream",
            "seed_scalar_rng": base["seed_scalar_rng"],
            "seed": base["seed"],
            "drawn_scalars": draws,
            "selected_point_orbits": K,
            "signed_frobenius_orbit_size": L,
            "actual_usable_points_B_before_folding": K * L,
            "signed_frobenius_columns": K,
            "initially_known_log_columns": K,
            "unknown_log_columns": 0,
            "frobenius_eigenvalue_mod_r": eigen,
            "enumerated_set_encoding": base["enumerated_set_encoding"],
            "enumerated_set_sha256": hashlib.sha256(key_stream).hexdigest(),
            "canonical_log_encoding": base["canonical_log_encoding"],
            "canonical_log_sha256": hashlib.sha256(log_stream).hexdigest(),
            "key_and_log_record_bytes": 32,
            "key_and_log_file": "n83_base_size_search_20261012/minimal_base_keys_and_logs.bin",
            "key_and_log_file_bytes": len(written),
            "key_and_log_file_sha256": sha(BASE),
        },
        "capacity": {
            "pair_rank_domain": 83 * K * (K - 1),
            "table_descriptors": M,
            "planned_query_representatives": R,
            "remaining_pair_ranks": 83 * K * (K - 1) - M - R,
            "minimum_K_for_this_schedule": True,
        },
        "source_sha256": sha(Path(__file__)),
        "parent_receipt_sha256": sha(PARENT),
        "parent_key_and_log_file_sha256": sha(parent_file),
        "orbit_key_source_sha256": sha(ROOT / "orbit_key.py"),
        "curve_source_sha256": sha(CODEGEN / "curves.py"),
        "field_source_sha256": sha(CODEGEN / "field.py"),
        "target_independent_base_build_seconds": build_seconds,
        "verification": "all sampled canonical keys and logs matched the verified parent base; selected group-law logs replayed from the saved artifact",
    }
    OUTPUT.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"K": K, "B": K * L, "draws": draws,
                      "build_seconds": build_seconds,
                      "capacity_margin": record["capacity"]["remaining_pair_ranks"],
                      "base_sha256": sha(BASE)}))


if __name__ == "__main__":
    main()
