#!/usr/bin/env python3
"""Freeze and audit a larger explicit ECC2K83 factor base before PDP work.

The tuple bound is necessary for ordinary-query yield but never certifies yield.
No sampled query is deliberately decomposable and no relation is claimed here.
"""

import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import platform
import random
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from gf2n import Curve, GF2n, INF, Point
from ordinary_campaign import check_prime, curve_order, scalar_mul

SOURCE = HERE / "explicit_base_frontier.cpp"
CASES = [(13, 5), (83, 6), (83, 12), (83, 16)]
CONTROLS = {
    13: HERE / "ordinary-evidence-20260928/n13.json",
    83: HERE / "ordinary-evidence-20260928/n83.json",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(path):
    controls = {str(n): {"path": str(CONTROLS[n].relative_to(ROOT)),
                         "sha256": sha(CONTROLS[n])} for n in CONTROLS}
    manifest = {"schema": "explicit-base-frontier-v1", "scope": "base_feasibility_only",
                "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in (SOURCE, Path(__file__))},
                "controls": controls, "cases": [{"n": n, "l": l, "seed": 20260928+n+l,
                                              "sample_size": 32 if l <= 12 else 64,
                                              "watchdog_seconds": 120,
                                              "memory_mib": 512} for n, l in CASES],
                "criterion": "exact actual B and B^m/(r-1) for m=3,4,5; compare to 1% necessary bound",
                "stop": "each enumerator has 120 seconds and 512 MiB; timeout leaves B unknown",
                "excluded_cost": "C++ compiler; include construction, all output, independent sample verification and checksums",
                "new_independent_relations": None, "natural_yield": None,
                "candidate_id": None, "full_dlp_speedup": None}
    with path.open("x") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({"manifest": str(path), "sha256": sha(path)}))


def parse_hex(s):
    if not isinstance(s, str) or not s or len(s) > 32 or any(c not in "0123456789abcdef" for c in s):
        raise ValueError("invalid field element encoding")
    return int(s, 16)


def necessary_B(r, m, percent=1):
    target = (percent * (r - 1) + 99) // 100
    low, high = 0, 1
    while high**m < target:
        high *= 2
    while low + 1 < high:
        mid = (low + high) // 2
        if mid**m < target:
            low = mid
        else:
            high = mid
    return high


def check_source(manifest):
    for name, value in manifest["source_sha256"].items():
        if sha(ROOT / name) != value:
            raise ValueError(f"changed frozen source: {name}")
    for entry in manifest["controls"].values():
        if sha(ROOT / entry["path"]) != entry["sha256"]:
            raise ValueError("changed prior certified control")


def verify_case(raw, reference, case):
    base = reference["base"]
    n, l = case["n"], case["l"]
    if n != base["n"] or not check_prime(base["prime_certificate"]):
        raise ValueError("invalid exact subgroup order certificate")
    if base["cofactor"] != 4 or curve_order(n) != 4 * base["subgroup_order"]:
        raise ValueError("curve order / cofactor mismatch")
    field = GF2n(n, base["modulus"])
    curve = Curve(field, 1)
    reps = set()
    rows = []
    summary = None
    t = time.monotonic()
    with raw.open() as data:
        for line in data:
            row = json.loads(line)
            if row.get("summary") is True:
                if summary is not None:
                    raise ValueError("multiple summaries")
                summary = row
                continue
            if summary is not None:
                raise ValueError("data after summary")
            x = parse_hex(row["x"])
            y = parse_hex(row["y"])
            qx = parse_hex(row["projected_x"])
            qy = parse_hex(row["projected_y"])
            if x >= 1 << l or qx >= 1 << n or y >= 1 << n or qy >= 1 << n or qx == 0:
                raise ValueError("invalid original/projected point")
            if rows and x <= rows[-1][0]:
                raise ValueError("not exactly ordered distinct abscissae")
            if qy > (qy ^ qx):
                raise ValueError("noncanonical sign")
            if (qx, qy) in reps:
                # Multiple originals may have the same projected representative.
                pass
            reps.add((qx, qy))
            rows.append((x, y, qx, qy))
    if summary is None or summary["n"] != n or summary["l"] != l:
        raise ValueError("incomplete or wrong C base")
    if summary["signed_projected_B"] != 2 * len(reps) or summary["signed_columns"] != len(reps):
        raise ValueError("actual B inconsistent with raw points")
    if summary["lifted_original_points"] < len(rows) or len(rows) > 1 << l:
        raise ValueError("impossible original base size")
    if summary["repeated_orbit_representatives"] != len(rows)-len(reps):
        raise ValueError("repeated projected count mismatch")
    rng = random.Random(case["seed"])
    picks = (list(range(len(rows))) if (n, l) in ((13, 5), (83, 6))
             else sorted(set([*range(min(16, len(rows))),
                              *rng.sample(range(len(rows)), min(case["sample_size"], len(rows)))])))
    for i in picks:
        x, y, qx, qy = rows[i]
        p = curve.lift_x(x)
        if p is None or y not in (p.y, p.y ^ x):
            raise ValueError("independent lift failed")
        q = scalar_mul(curve, Point(x, y), 4)
        if q == INF or (q.x, min(q.y, q.y ^ q.x)) != (qx, qy):
            raise ValueError("independent group projection failed")
        if scalar_mul(curve, q, base["subgroup_order"]) != INF:
            raise ValueError("subgroup membership failed")
    if (n, l) in ((13, 5), (83, 6)):
        previous = {(p[0], min(p[1], p[1] ^ p[0])) for p in base["projected_points"]}
        if reps != previous or summary["signed_projected_B"] != base["B"]:
            raise ValueError("exact prior-control base does not match")
    pairs = [[x, y] for x, y in sorted(reps)]
    digest = hashlib.sha256(json.dumps(pairs, separators=(",", ":")).encode()).hexdigest()
    r = base["subgroup_order"]
    return {"original_abscissae": len(rows), "original_lifted_points": summary["lifted_original_points"],
            "signed_projected_B": summary["signed_projected_B"],
            "signed_columns": summary["signed_columns"], "representatives_sha256": digest,
            "independent_sample_checks": len(picks), "independent_control_set_match": (n, l) in ((13, 5), (83, 6)),
            "sample_verification_seconds": time.monotonic() - t,
            "prime_certificate_checked": True, "on_curve_checked_by_enumerator": True,
            "uniform_query_coverage_upper_bounds": {str(m): {
                "ordered_tuple_numerator": (summary["signed_projected_B"] + 1)**m,
                "denominator": r-1,
                "capped_decimal": min(1.0, (summary["signed_projected_B"]+1)**m/(r-1)),
                "necessary_B_for_1_percent_bound": max(0, necessary_B(r, m)-1)} for m in (3, 4, 5)}}


def run(manifest_path, output):
    manifest = json.loads(manifest_path.read_text())
    check_source(manifest)
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_text(manifest_path.read_text())
    build = subprocess.run(["g++", "-O3", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            str(SOURCE), "-o", str(output / "enumerator")],
                           capture_output=True, text=True, timeout=60)
    (output / "compiler.txt").write_text(build.stdout + build.stderr)
    if build.returncode:
        raise RuntimeError("C++ build failed; compiler output retained")
    host = {"platform": platform.platform(), "compiler": subprocess.check_output(["g++", "--version"], text=True).splitlines()[0],
            "binary_sha256": sha(output / "enumerator"), "source_sha256": manifest["source_sha256"],
            "memory_limit_mib": 512, "cpu_count": os.cpu_count()}
    (output / "host.json").write_text(json.dumps(host, indent=2) + "\n")
    results = []
    for case in manifest["cases"]:
        n, l = case["n"], case["l"]
        base = json.loads((ROOT / manifest["controls"][str(n)]["path"]).read_text())
        raw = output / f"n{n}-l{l}.jsonl"
        started = time.monotonic()
        timed_out = False
        with raw.open("w") as stdout, (output / f"n{n}-l{l}.stderr").open("w") as stderr:
            def restrict():
                limit = case["memory_mib"] * 1024**2
                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
            try:
                p = subprocess.run([str(output / "enumerator"), str(n), str(l), str(base["base"]["modulus"])],
                                   stdout=stdout, stderr=stderr, timeout=case["watchdog_seconds"], preexec_fn=restrict)
                code = p.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                code = None
        construction_seconds = time.monotonic() - started
        result = {"n": n, "l": l, "status": "timeout" if timed_out else "error" if code else "complete",
                  "exit_code": code, "construction_seconds": construction_seconds,
                  "raw_sha256": sha(raw), "raw_bytes": raw.stat().st_size,
                  "base": None, "candidate_id": None, "new_independent_relations": None}
        if code == 0 and not timed_out:
            try:
                result["base"] = verify_case(raw, base, case)
            except (ValueError, KeyError) as error:
                result["status"] = "verification_failed"
                result["verification_error"] = str(error)
            if result["base"]:
                result["base_preparation_seconds"] = construction_seconds + result["base"]["sample_verification_seconds"]
        results.append(result)
        (output / "results.json").write_text(json.dumps({"manifest_sha256": sha(manifest_path), "results": results}, indent=2)+"\n")
        print(json.dumps({"n": n, "l": l, "status": result["status"], "B": result["base"]["signed_projected_B"] if result["base"] else None}), flush=True)
    # Compression and hashing of immutable evidence are outside the base-preparation cost.
    for case in manifest["cases"]:
        raw = output / f"n{case['n']}-l{case['l']}.jsonl"
        with raw.open("rb") as src, lzma.open(str(raw)+".xz", "wb", preset=6) as dst:
            for chunk in iter(lambda: src.read(1<<20), b""):
                dst.write(chunk)
    (output / "archives.json").write_text(json.dumps({p.name: {"bytes": p.stat().st_size, "sha256": sha(p)}
                                                      for p in output.glob("*.jsonl.xz")}, indent=2)+"\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    f = subs.add_parser("freeze"); f.add_argument("manifest", type=Path)
    r = subs.add_parser("run"); r.add_argument("manifest", type=Path); r.add_argument("output", type=Path)
    a = parser.parse_args()
    if a.action == "freeze": freeze(a.manifest)
    else: run(a.manifest, a.output)


if __name__ == "__main__":
    main()
