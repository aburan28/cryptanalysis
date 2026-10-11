#!/usr/bin/env python3
"""Extend the exact n=83 known-log orbit base to 48,194 columns."""

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
OUTPUT = HERE / "runs" / "n83_knownlog_orbit_base_k48194.json"
BASE_FILE = HERE / "runs" / "n83_knownlog_orbit_keys_and_logs_k48194.bin"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from orbit_key import OrbitKey
from run_n23 import frozen, sha

N = 83
COLUMNS = 48194
ORBIT_SIZE = 2 * N
BASE_SEED = 831043
KEY_BYTES = 21
LOG_BYTES = 11


def main():
    reference = json.loads(REFERENCE.read_text())
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == curve_id
    order = identity["curve"]["subgroup_order"]
    assert curves.isPrimeBig(order)
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    generator = tuple(identity["curve"]["generator"])
    assert curve.mul(generator, order) is None
    eigen = curves.frobeniusEigenvalue(curve, generator, order)
    assert eigen != 1 and pow(eigen, N, order) == 1
    rng = random.Random(BASE_SEED)
    entries = {}
    drawn_scalars = 0
    started = time.perf_counter_ns()
    while len(entries) < COLUMNS:
        alpha = rng.randrange(1, order)
        drawn_scalars += 1
        point = curve.mul(generator, alpha)
        key, exponent, sign = orbit.canonical(point)
        if key in entries:
            continue
        entries[key] = sign * pow(eigen, exponent, order) * alpha % order
    build_ns = time.perf_counter_ns() - started
    keys = sorted(entries)
    key_stream = b"".join(key.to_bytes(KEY_BYTES, "little") for key in keys)
    log_stream = b"".join(entries[key].to_bytes(LOG_BYTES, "little")
                          for key in keys)
    BASE_FILE.write_bytes(b"".join(
        key.to_bytes(KEY_BYTES, "little") +
        entries[key].to_bytes(LOG_BYTES, "little") for key in keys))
    report = {
        "kind": "n83_exact_compressed_knownlog_signed_frobenius_factor_base",
        "scope": "target-independent complete known-log base geometry; no target relation or DLP",
        "proposal_id": "Q1051", "candidate_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none",
        "factor_base": {
            "construction": "first 48,194 distinct signed-Frobenius orbits of seeded uniform nonzero scalar multiples of G; exact seeded extension of the Q1043 base; every canonical log derived from the seed scalar and Frobenius eigenvalue",
            "seed_scalar_rng": "random.Random(831043).randrange(1,r)",
            "seed": BASE_SEED, "drawn_scalars": drawn_scalars,
            "selected_point_orbits": COLUMNS,
            "signed_frobenius_orbit_size": ORBIT_SIZE,
            "actual_usable_points_B_before_folding": COLUMNS * ORBIT_SIZE,
            "signed_frobenius_columns": COLUMNS,
            "initially_known_log_columns": COLUMNS,
            "unknown_log_columns": 0,
            "frobenius_eigenvalue_mod_r": eigen,
            "enumerated_set_encoding": "sorted canonical point keys, 21-byte little-endian each; expand by both signs and 83 Frobenius powers",
            "enumerated_set_sha256": hashlib.sha256(key_stream).hexdigest(),
            "canonical_log_encoding": "sorted canonical representative logs, 11-byte little-endian residues modulo r",
            "canonical_log_sha256": hashlib.sha256(log_stream).hexdigest(),
            "key_and_log_file": "runs/n83_knownlog_orbit_keys_and_logs_k48194.bin",
            "key_and_log_record_bytes": KEY_BYTES + LOG_BYTES,
            "key_and_log_file_bytes": BASE_FILE.stat().st_size,
            "key_and_log_file_sha256": sha(BASE_FILE),
        },
        "target_independent_base_build_wall_ns": build_ns,
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
                      "actual_B": COLUMNS * ORBIT_SIZE,
                      "columns": COLUMNS,
                      "drawn_scalars": drawn_scalars,
                      "wall_s": build_ns / 1e9,
                      "rss_mib": report["peak_parent_rss_bytes"] / 2**20,
                      "file": str(BASE_FILE)}))


if __name__ == "__main__":
    main()
