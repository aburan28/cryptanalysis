#!/usr/bin/env python3
"""Replay every canonical point/log entry of the 200,000-orbit N83 base."""

import hashlib
import json
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent
sys.path.insert(0, str(PAIR))
from verify_n83_quotient_receipt_sage import (  # noqa: E402
    coordinate_cycle, gamma_to_polynomial_bits, key_point_and_log,
    raw_to_coords,
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result_path = HERE / "large_base_sage_replay.json"
    progress_path = HERE / "large_base_sage_progress.json"
    assert not result_path.exists(), "Sage replay already frozen"
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    receipt_path = HERE / "large_base.json"
    receipt = json.loads(receipt_path.read_text())
    data_path = HERE / "large_base_keys_and_logs.bin"
    assert sha(data_path) == receipt["key_and_log_file_sha256"]
    data = data_path.read_bytes()
    K = receipt["K"]
    assert len(data) == 32 * K and K == 200000
    keys = [int.from_bytes(data[i:i + 21], "little")
            for i in range(0, len(data), 32)]
    assert keys == sorted(set(keys))
    parent_path = PAIR / "runs/n83_knownlog_orbit_base_k48194.json"
    assert sha(parent_path) == receipt["parent_receipt_sha256"]
    parent = json.loads(parent_path.read_text())
    model = parent["curve_identity_record"]["curve"]
    r = model["subgroup_order"]
    eigen = receipt["frobenius_eigenvalue_mod_r"]
    binary = GF(2)
    polynomial = PolynomialRing(binary, "t")
    t = polynomial.gen()
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
        return field(polynomial([(bits >> i) & 1 for i in range(83)]))

    curve = EllipticCurve(field, [model[f"a{i}"] for i in (1, 2, 3, 4, 6)])
    generator = curve(*[element(raw_to_coords(int(x)))
                        for x in model["generator"]])
    assert r * generator == curve(0)
    assert eigen * generator == curve(generator[0]**2, generator[1]**2)
    cycle = coordinate_cycle()
    started = time.perf_counter()
    for orbit in range(K):
        coords, log = key_point_and_log(orbit * 166, data, cycle, eigen, r)
        point = curve(element(coords[0]), element(coords[1]))
        assert point != curve(0)
        assert log * generator == point, f"log mismatch at orbit {orbit}"
        if (orbit + 1) % 10000 == 0:
            progress_path.write_text(json.dumps({
                "status": "running", "verified_orbits": orbit + 1,
                "elapsed_seconds": time.perf_counter() - started,
            }, sort_keys=True, indent=2) + "\n")
            print(json.dumps({"verified_orbits": orbit + 1}), flush=True)
    result = {
        "status": "PASS",
        "curve_id": receipt["curve_id"],
        "K": K,
        "B": receipt["actual_usable_points_B_before_folding"],
        "every_canonical_log_replayed": True,
        "key_file_sha256": sha(data_path),
        "base_receipt_sha256": sha(receipt_path),
        "runtime_info_sha256": sha(runtime_path),
        "verifier_source_sha256": sha(Path(__file__)),
        "replay_wall_seconds_exploratory": time.perf_counter() - started,
    }
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    progress_path.write_text(json.dumps({"status": "PASS", "verified_orbits": K},
                                        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "K": K}), flush=True)


if __name__ == "__main__":
    main()
