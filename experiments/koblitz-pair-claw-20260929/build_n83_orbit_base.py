#!/usr/bin/env python3
"""Build an exact compressed n=83 signed-Frobenius factor base."""

import hashlib
import json
import platform
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
             "runs" / "n83_perf_prefix.json")
OUTPUT = HERE / "runs" / "n83_weight5_orbit_base.json"
KEY_FILE = HERE / "runs" / "n83_weight5_orbit_keys.bin"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from orbit_key import OrbitKey
from run_n23 import frozen, sha

N = 83
WEIGHT = 5
ORBIT_SIZE = 2 * N
TARGET_COLUMNS = 24097
SEED = 830929
KEY_BYTES = 21  # 166 packed quotient bits.


def cyclic_minimum(bits, width):
    mask = (1 << width) - 1
    current = bits
    minimum = bits
    for _ in range(1, width):
        current = ((current << 1) | (current >> (width - 1))) & mask
        if current < minimum:
            minimum = current
    return minimum


def main():
    reference = json.loads(REFERENCE.read_text())
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == curve_id
    order = identity["curve"]["subgroup_order"]
    cofactor = identity["curve"]["cofactor"]
    assert cofactor == 4 and identity["curve"]["order"] == order * cofactor
    assert curves.isPrimeBig(order)
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    generator = tuple(identity["curve"]["generator"])
    assert curve.mul(generator, order) is None
    eigenvalue = curves.frobeniusEigenvalue(curve, generator, order)
    assert eigenvalue != 1 and pow(eigenvalue, N, order) == 1
    # Prime N and odd order imply every nonidentity subgroup point has
    # Frobenius orbit N and disjoint positive/negative orbits, hence 2N.

    rng = random.Random(SEED)
    seen_x_orbits = set()
    point_orbits = set()
    drawn_supports = 0
    rational_x_orbits = 0
    zero_projection = 0
    repeated_projected_orbits = 0
    started = time.perf_counter_ns()
    while len(point_orbits) < TARGET_COLUMNS:
        support = rng.sample(range(N), WEIGHT)
        coordinate_mask = sum(1 << bit for bit in support)
        drawn_supports += 1
        x = onb.fromCoords(coordinate_mask)
        x_orbit_key = cyclic_minimum(orbit.cycle_bits(x), N)
        if x_orbit_key in seen_x_orbits:
            continue
        seen_x_orbits.add(x_orbit_key)
        point = curve.pointFromX(x)
        if point is None:
            continue
        rational_x_orbits += 1
        projected = curve.mul(point, cofactor)
        if projected is None:
            zero_projection += 1
            continue
        point_key = orbit.canonical(projected)[0]
        if point_key in point_orbits:
            repeated_projected_orbits += 1
            continue
        point_orbits.add(point_key)
    base_wall_ns = time.perf_counter_ns() - started
    keys = sorted(point_orbits)
    assert len(keys) == TARGET_COLUMNS and all(key >= 0 for key in keys)
    KEY_FILE.write_bytes(b"".join(key.to_bytes(KEY_BYTES, "little") for key in keys))
    key_digest = sha(KEY_FILE)
    report = {
        "kind": "n83_exact_compressed_weight5_signed_frobenius_factor_base",
        "scope": "target-independent complete factor-base geometry; no relation or DLP",
        "proposal_id": "Q1041", "candidate_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none",
        "factor_base": {
            "construction": "first 24,097 unique nonidentity projected point orbits from a deterministic PRNG stream of five-bit normal-x supports; rational lift; [4] projection; both signs and all 83 Frobenius powers",
            "normal_x_hamming_weight": WEIGHT,
            "normal_x_support_seed": SEED,
            "normal_x_support_sampler": "random.Random(seed).sample(range(83),5); coordinate-mask bits are sampled positions",
            "selected_point_orbits": TARGET_COLUMNS,
            "signed_frobenius_orbit_size": ORBIT_SIZE,
            "actual_usable_points_B_before_folding": TARGET_COLUMNS * ORBIT_SIZE,
            "signed_frobenius_columns": TARGET_COLUMNS,
            "drawn_supports": drawn_supports,
            "unique_x_orbits_considered": len(seen_x_orbits),
            "rational_x_orbits": rational_x_orbits,
            "zero_projection": zero_projection,
            "repeated_projected_orbits": repeated_projected_orbits,
            "frobenius_eigenvalue_mod_r": eigenvalue,
            "enumerated_set_encoding": "21-byte little-endian sorted signed-Frobenius canonical point keys; each expands by both signs and all 83 Frobenius powers",
            "enumerated_set_sha256": key_digest,
            "orbit_key_file": "runs/n83_weight5_orbit_keys.bin",
            "orbit_key_file_bytes": KEY_FILE.stat().st_size,
        },
        "target_independent_base_wall_ns": base_wall_ns,
        "peak_parent_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                  if platform.system() == "Darwin" else
                                  resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "verified_relation_count": 0,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
        "orbit_key_sha256": sha(HERE / "orbit_key.py"),
        "reference_sha256": sha(REFERENCE),
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py", "indexcalc.py")},
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": curve_id,
                      "actual_B": TARGET_COLUMNS * ORBIT_SIZE,
                      "columns": TARGET_COLUMNS,
                      "drawn_supports": drawn_supports,
                      "wall_s": base_wall_ns / 1e9,
                      "rss_mib": report["peak_parent_rss_bytes"] / 2**20,
                      "key_file": str(KEY_FILE)}))


if __name__ == "__main__":
    main()
