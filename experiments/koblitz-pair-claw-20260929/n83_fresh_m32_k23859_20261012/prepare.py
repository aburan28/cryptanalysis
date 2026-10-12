#!/usr/bin/env python3
"""Freeze one fresh N83 public target and the minimum-base M32/R29 schedule."""

import hashlib
import json
import math
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent
ROOT = PAIR.parents[1]
CODEGEN = ROOT / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))

import curves  # noqa: E402
import field  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def main():
    target_path = HERE / "target_fixture.json"
    protocol_path = HERE / "protocol.json"
    assert not target_path.exists() and not protocol_path.exists(), "frozen input exists"
    base_path = PAIR / "n83_base_size_search_20261012" / "minimal_base.json"
    base = json.loads(base_path.read_text())
    group = base["curve_identity_record"]["curve"]
    r = group["subgroup_order"]
    K = base["factor_base"]["selected_point_orbits"]
    assert base["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert K == 23859 and r == 2417851639230796216685689
    key_path = PAIR / base["factor_base"]["key_and_log_file"]
    assert sha(key_path) == base["factor_base"]["key_and_log_file_sha256"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    generator = tuple(group["generator"])
    assert curve.mul(generator, r) is None
    scalar = 1 + secrets.randbelow(r - 1)
    point = curve.mul(generator, scalar)
    assert point is not None and curve.mul(point, r) is None
    target = {
        "kind": "n83_fresh_known_scalar_fixture",
        "curve_id": base["curve_id"],
        "generation_law": "uniform scalar in [1,r-1] from Python secrets, generated before any stage run",
        "scalar_decimal": str(scalar),
        "public_point_onb_raw": list(point),
        "scalar_sha256": hashlib.sha256(str(scalar).encode()).hexdigest(),
        "replay": "scalar times frozen generator equals public point",
    }
    target_path.write_text(json.dumps(target, indent=2, sort_keys=True) + "\n")
    M = 1 << 32
    R = 1 << 29
    wave_count = 80
    domain = 83 * K * (K - 1)
    step = 16461550037
    offset = 33178593942
    assert math.gcd(step, domain) == 1
    query_offset = (offset + step * M) % domain
    assert M + wave_count * R <= domain
    assert ((query_offset - offset) * pow(step, -1, domain)) % domain == M
    workload = {
        "curve_id": base["curve_id"],
        "target_public_point_onb_raw": list(point),
        "target_count": 1,
        "target_generation_law": target["generation_law"],
        "table_descriptors": M,
        "query_representatives_per_wave": R,
        "query_wave_count": wave_count,
        "table_step": step,
        "table_offset": offset,
        "query_offset": query_offset,
        "factor_base_file_sha256": sha(key_path),
        "bits_per_key": 15,
        "hashes": 10,
        "workers": 4,
        "memory_cap_bytes": 8 * (1 << 30),
    }
    protocol = {
        "kind": "n83_fresh_minimum_base_m32_r29_stage_protocol",
        "status": "frozen_before_first_stage_run",
        "curve_id": base["curve_id"],
        "proposal_id": "Q2026101238",
        "candidate_id": None,
        "factor_base_orbits_K": K,
        "actual_usable_points_B_before_folding": K * 166,
        "factor_base_receipt_sha256": sha(base_path),
        "factor_base_file_sha256": sha(key_path),
        "target_fixture_sha256": sha(target_path),
        "target_public_point_onb_raw": list(point),
        "workload_id": hashlib.sha256(canonical(workload)).hexdigest()[:12],
        "workload": workload,
        "pair_rank_domain": domain,
        "pair_rank_margin": domain - M - wave_count * R,
        "table_batch": 1024,
        "representative_batch": 8,
        "memory_cap_mib": 8192,
        "single_wave_timeout_seconds": 9000,
        "smoke_M20_R18_first": True,
        "measurement_tier": "exploratory_until_Tier_0_or_Tier_1_receipt",
        "input_boundary": "only public point and base key/log file passed to native producer; fixture scalar excluded",
        "complete_target_boundary": "all target-dependent waves, failures, recovery check, and same-point rho required",
        "source_sha256": sha(Path(__file__)),
    }
    protocol_path.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"workload_id": protocol["workload_id"],
                      "K": K, "B": K * 166, "query_offset": query_offset}))


if __name__ == "__main__":
    main()
