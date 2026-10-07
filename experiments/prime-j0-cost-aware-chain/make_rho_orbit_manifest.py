#!/usr/bin/env python3
"""Check the frozen rho point independently and emit an isolated-run manifest."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from isolated_bench import require_manifest  # noqa: E402


def add(p, q, modulus):
    if p is None:
        return q
    if q is None:
        return p
    x, y = p
    u, v = q
    if x == u and (y + v) % modulus == 0:
        return None
    if p == q:
        slope = 3 * x * x * pow(2 * y, -1, modulus) % modulus
    else:
        slope = (v - y) * pow(u - x, -1, modulus) % modulus
    out_x = (slope * slope - x - u) % modulus
    return out_x, (slope * (x - out_x) - y) % modulus


def mul(point, scalar, modulus):
    result = None
    while scalar:
        if scalar & 1:
            result = add(result, point, modulus)
        point = add(point, point, modulus)
        scalar >>= 1
    return result


FIXTURES = {
    "glv-j0-32": ("rho-orbit-one-target.json",
                  b"rho-j0-coordinate-orbit-2026-10-07-one-target-v1"),
    "j0-56": ("rho-orbit-primary-target.json",
              b"rho-j0-factored-hash-2026-10-07-primary-target-v1"),
}


def checked_fixture(case_name):
    filename, seed = FIXTURES[case_name]
    path = HERE / filename
    fixture = json.loads(path.read_text())
    p = fixture["p"]
    base = int(fixture["base_x"]), int(fixture["base_y"])
    target = int(fixture["target_x"]), int(fixture["target_y"])
    scalar = int(fixture["scalar"])
    assert fixture["curve"] == case_name and fixture["a"] == 0
    assert 0 < scalar < fixture["order"]
    for x, y in (base, target):
        assert (y * y - x * x * x - fixture["b"]) % p == 0
    assert mul(base, fixture["order"], p) is None
    assert mul(base, scalar, p) == target
    digest = hashlib.sha256(seed).hexdigest()
    assert digest == fixture["fixture_seed_sha256"]
    assert scalar == 1 + int(digest, 16) % (fixture["order"] - 1)
    return fixture


def make_manifest(args):
    fixture = checked_fixture(args.case_name)
    ref = args.reference.resolve()
    cand = args.candidate.resolve()
    if ref == cand:
        raise ValueError("reference and candidate must be distinct binaries")
    caches = (ref.parent / "CMakeCache.txt", cand.parent / "CMakeCache.txt")
    flags = {"coordinate": "CA_RHO_J0_COORDINATE_ORBIT",
             "factored": "CA_RHO_J0_FACTORED_HASH"}
    reference_cache = caches[0].read_text()
    candidate_cache = caches[1].read_text()
    for flag in flags.values():
        if f"{flag}:BOOL=OFF" not in reference_cache:
            raise ValueError("reference build must have both orbit experiments OFF")
    for kind, flag in flags.items():
        desired = "ON" if kind == args.candidate_kind else "OFF"
        if f"{flag}:BOOL={desired}" not in candidate_cache:
            raise ValueError(f"candidate build must have {flag}={desired}")
    fields = {key: str(fixture[key]) for key in
              ("curve", "base_x", "base_y", "target_x", "target_y")}
    fields["seed"] = str(fixture["walk_seed"])
    artifacts = [ROOT / "CMakeLists.txt", ROOT / "src" / "curve.c",
                 ROOT / "src" / "curve_internal.h", ROOT / "src" / "group_ec.c",
                 ROOT / "scripts" / "isolated_bench.py",
                 HERE / "rho_orbit_one_target.c", HERE / FIXTURES[args.case_name][0],
                 HERE / "RHO_J0_COORDINATE_ORBIT.md", HERE / "RHO_J0_FACTORED_HASH.md",
                 HERE / "make_rho_orbit_manifest.py", *caches,
                 ref.parent / "libcryptanalysis.a", cand.parent / "libcryptanalysis.a"]
    manifest = {
        "schema": 1,
        "workdir": str(ROOT),
        "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu,
                      "mem_nodes": str(args.mem_node)},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s or (600 if args.case_name == "j0-56" else 120),
        "repetitions": args.repetitions,
        "measurement_boundary": "rho_orbit_one_target.c: before ca_curve_solve through independent scalar replay, including target-dependent setup and recovery; process startup and point loading excluded",
        "pair_fields": list(fields),
        "result_field": "scalar",
        "cases": [{"id": args.case_name + "-target-0", "expected_fields": fields,
                   "expected_result": fixture["scalar"],
                   "reference": [str(ref)] + (["j0-56"] if args.case_name == "j0-56" else []),
                   "candidate": [str(cand)] + (["j0-56"] if args.case_name == "j0-56" else [])}],
    }
    require_manifest(manifest)  # schema and path validation; no host preflight
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--candidate-kind", choices=("coordinate", "factored"), required=True)
    parser.add_argument("--case", dest="case_name", choices=tuple(FIXTURES),
                        default="j0-56")
    parser.add_argument("--cgroup", required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-node", type=int, required=True)
    parser.add_argument("--timeout-s", type=int)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = make_manifest(args)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"validated one-target manifest: {args.output}")


if __name__ == "__main__":
    main()
