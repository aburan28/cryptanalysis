#!/usr/bin/env python3
"""Capped conventional S6 ANF construction on correct original targets."""

import argparse
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from gf2n import Curve, GF2n, Point
from target_fiber import projected_preimages


def child(n, l, modulus, x):
    cap = 512 * 1024**2
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    import sumpoly
    from descend import descend
    field = GF2n(n, modulus)
    start = time.monotonic()
    polynomials = sumpoly.summation_polynomials(6)
    print(json.dumps({"stage": "s6", "terms": len(polynomials[6]),
                      "seconds": time.monotonic() - start,
                      "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)
    start = time.monotonic()
    anf = descend(polynomials, field, Curve(field, 1), 5, l, x)
    print(json.dumps({"stage": "anf", "terms": len(anf),
                      "degree": max((mask.bit_count() for mask in anf), default=0),
                      "seconds": time.monotonic() - start,
                      "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)


def driver(manifest_path, output, seconds):
    case = json.loads(manifest_path.read_text())
    base = case["base"]
    if base["n"] != 83 or base["cofactor"] != 4:
        raise ValueError("probe requires the frozen n83 four-lift case")
    curve = Curve(GF2n(83, base["modulus"]), 1)
    target = Point(*(int(v, 16) for v in case["streams"][0]["queries"][0]["target"]))
    branches = []
    for i, lifted in enumerate(projected_preimages(curve, target, base["r"])):
        begin = time.monotonic()
        cmd = [sys.executable, "-u", __file__, "child", "83", "17", str(base["modulus"]), str(lifted.x)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=seconds + 2)
            stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
            status = "complete" if code == 0 else "failure"
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout or ""
            stderr, code, status = "watchdog timeout", None, "timeout"
        stages = [json.loads(line) for line in stdout.splitlines()]
        branches.append({"branch": i, "original_target": [hex(lifted.x), hex(lifted.y)],
                         "status": status, "exit_code": code, "stderr": stderr[-1000:],
                         "stages": stages, "wall_seconds": time.monotonic() - begin,
                         "limit_seconds": seconds, "limit_mib": 512})
        print(json.dumps({"branch": i, "status": status, "stages": stages}), flush=True)
        output.write_text(json.dumps({"manifest": str(manifest_path), "branches": branches}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("child")
    for k in ("n", "l", "modulus", "x"):
        p.add_argument(k, type=int)
    p = sub.add_parser("run")
    p.add_argument("manifest", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--seconds", type=int, default=30)
    a = parser.parse_args()
    if a.action == "child":
        child(a.n, a.l, a.modulus, a.x)
    else:
        driver(a.manifest, a.output, a.seconds)
