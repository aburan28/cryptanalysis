#!/usr/bin/env python3
"""Independently check the frozen N83 public point in the Sage field."""

import hashlib
import json
import math
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent
sys.path.insert(0, str(PAIR))
from verify_n83_quotient_receipt_sage import (  # noqa: E402
    gamma_to_polynomial_bits, raw_to_coords,
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "independent_sage_target_check.json"
    assert not output.exists(), "check already frozen"
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    target_path = HERE / "target_fixture.json"
    fixture = json.loads(target_path.read_text())
    assert sha(target_path) == protocol["target_fixture_sha256"]
    assert fixture["public_point_onb_raw"] == protocol[
        "target_public_point_onb_raw"]
    base_path = PAIR / "n83_base_size_search_20261012/minimal_base.json"
    assert sha(base_path) == protocol["factor_base_receipt_sha256"]
    base = json.loads(base_path.read_text())
    model = base["curve_identity_record"]["curve"]
    order = model["subgroup_order"]
    binary = GF(2)
    ring = PolynomialRing(binary, "t")
    t = ring.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**83, name="z", modulus=modulus)
    gamma = gamma_to_polynomial_bits()

    def element(coords):
        bits = 0
        while coords:
            low = coords & -coords
            bits ^= gamma[low.bit_length() - 1]
            coords ^= low
        return field(ring([(bits >> i) & 1 for i in range(83)]))

    curve = EllipticCurve(field, [model[f"a{i}"] for i in (1, 2, 3, 4, 6)])

    def point(encoded):
        return curve(*[element(raw_to_coords(int(x))) for x in encoded])

    generator = point(model["generator"])
    target = point(fixture["public_point_onb_raw"])
    scalar = int(fixture["scalar_decimal"])
    assert 1 <= scalar < order and order * generator == curve(0)
    assert order * target == curve(0) and target != curve(0)
    assert scalar * generator == target
    K = protocol["factor_base_orbits_K"]
    M = protocol["workload"]["table_descriptors"]
    R = protocol["workload"]["query_representatives_per_wave"]
    waves = protocol["workload"]["query_wave_count"]
    domain = 83 * K * (K - 1)
    assert math.gcd(protocol["workload"]["table_step"], domain) == 1
    assert M + R * waves <= domain
    assert domain - M - R * waves == protocol["pair_rank_margin"]
    report = {
        "status": "PASS",
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "target_in_prime_order_subgroup": True,
        "scalar_replay": True,
        "disjoint_pair_rank_schedule": True,
        "target_fixture_sha256": sha(target_path),
        "protocol_sha256": sha(protocol_path),
        "base_receipt_sha256": sha(base_path),
        "runtime_info_sha256": sha(runtime_path),
        "verifier_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "workload_id": report["workload_id"]}))


if __name__ == "__main__":
    main()
