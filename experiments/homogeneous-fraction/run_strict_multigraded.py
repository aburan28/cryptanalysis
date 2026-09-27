#!/usr/bin/env python3
"""Run and independently audit strict tri-graded versus total-graded M2 F4."""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

from block_fraction_solver import MODULI, equations
from math_model import GF2n
from strict_multigraded import boolean_lift_check, emit

ROOT = Path(__file__).resolve().parent
TERM = re.compile(r"([xh])_(\d+)(?:\^(\d+))?")


def parse_polynomial(line, nv):
    out = []
    for term in line.strip().replace("-", "+").split("+"):
        if not term or term == "0":
            continue
        if term == "1":
            out.append(tuple(0 for _ in range(nv + 3)))
            continue
        exponents = [0] * (nv + 3)
        factors = term.split("*")
        if not factors:
            raise ValueError(f"unknown polynomial syntax {term!r}")
        for factor in factors:
            match = TERM.fullmatch(factor)
            if match is None:
                raise ValueError(f"unknown factor {factor!r}")
            name, index, power = match.groups()
            position = int(index) if name == "x" else nv + int(index)
            exponents[position] += int(power or 1)
        out.append(tuple(exponents))
    return out


def evaluate(poly, bits, nv):
    parity = 0
    for term in poly:
        if all((bits >> i & 1) or exp == 0 for i, exp in enumerate(term[:nv])):
            parity ^= 1  # h_0=h_1=h_2=1
    return parity


def check_basis(n, k, target, arm, basis):
    width = 2 * (k + 1)
    nv = 3 * width
    parsed = [parse_polynomial(poly, nv) for poly in basis]
    if arm == "multi":
        for poly in parsed:
            profiles = {tuple(sum(exp for exp in term[b * width:(b + 1) * width])
                              + term[nv + b] for b in range(3)) for term in poly}
            if len(profiles) > 1:
                raise AssertionError(f"basis polynomial lost tri-grading: {profiles}")
    field = GF2n(n, MODULI[n])
    originals = equations(field, k, target)
    expected_roots = observed_roots = 0
    for bits in range(1 << nv):
        expected = all(not (sum((mon & bits) == mon for mon in poly) & 1)
                       for poly in originals)
        observed = all(evaluate(poly, bits, nv) == 0 for poly in parsed)
        if expected != observed:
            raise AssertionError(f"M2 basis changed affine Boolean roots: {arm=} {bits=}")
        expected_roots += expected
        observed_roots += observed
    return {"affine_roots": expected_roots, "basis_polynomials": len(basis),
            "graded_basis": arm == "multi"}


def run(n, k, target, arm, repeat, out, timeout):
    script = out / f"n{n}_k{k}_t{target}_{arm}_r{repeat}.m2"
    script.write_text(emit(n, k, target, arm))
    start = time.perf_counter()
    try:
        process = subprocess.run(["M2", "--script", str(script)], capture_output=True,
                                 text=True, timeout=timeout)
        status = "complete" if process.returncode == 0 else "error"
        output = process.stdout + process.stderr
    except subprocess.TimeoutExpired as exc:
        status = "timeout"
        output = "".join(part.decode(errors="replace") if isinstance(part, bytes) else part
                         for part in (exc.stdout or "", exc.stderr or ""))
    wall = time.perf_counter() - start
    (out / (script.stem + ".log")).write_text(output)
    record = {"n": n, "k": k, "target": target, "arm": arm, "repeat": repeat,
              "status": status, "process_wall_seconds": wall}
    if status != "complete":
        record["error_tail"] = output[-1000:]
        return record
    def marker(name):
        matches = re.findall(rf"^{name}\|([^\n]+)", output, re.MULTILINE)
        if len(matches) != 1:
            raise AssertionError(f"missing or duplicated M2 marker {name}: {matches}")
        return matches[0]
    record.update(input_generators=int(marker("INPUTCOUNT")),
                  saturation_cpu_seconds=float(marker("SATCPU")),
                  saturation_generators=int(marker("SATGENS")),
                  f4_cpu_seconds=float(marker("GBCPU")),
                  basis_size_reported=int(marker("GBCOUNT")))
    record["matrix_shapes"] = [list(map(int, shape)) for shape in
                               re.findall(r"F4\[(\d+) by (\d+)\]", output)]
    basis = re.findall(r"^GBPOLY\|([^\n]+)", output, re.MULTILINE)
    record.update(check_basis(n, k, target, arm, basis))
    assert record["basis_size_reported"] == record["basis_polynomials"]
    return record


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "strict_runs")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--extended", action="store_true")
    ap.add_argument("--extended-only", action="store_true",
                    help="run only the bounded n=7,k=1 cases")
    args = ap.parse_args()
    if args.repeats < 1:
        ap.error("at least one repeat required")
    args.out.mkdir(parents=True, exist_ok=True)
    cases = [] if args.extended_only else [(5, 0, 0), (5, 0, 2)]
    if args.extended or args.extended_only:
        cases += [(7, 1, 1), (7, 1, 50)]
    rows = []
    for n, k, target in cases:
        expected_verified = boolean_lift_check(n, k, target)
        for repeat in range(args.repeats):
            order = ("multi", "total") if repeat % 2 == 0 else ("total", "multi")
            for arm in order:
                row = run(n, k, target, arm, repeat, args.out, args.timeout)
                row["curve_relation_exists"] = expected_verified
                rows.append(row)
                (args.out / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
                print(json.dumps({key: row.get(key) for key in
                      ("n", "k", "target", "arm", "repeat", "status",
                       "affine_roots", "saturation_cpu_seconds", "f4_cpu_seconds",
                       "matrix_shapes")}), flush=True)
    if any(row["status"] != "complete" for row in rows):
        raise SystemExit("at least one M2 run did not complete")
    print("ALL_AFFINE_ROOTS_VERIFIED", flush=True)


if __name__ == "__main__":
    main()
