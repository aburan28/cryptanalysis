#!/usr/bin/env python3
"""Paired, uncached Boolean GB benchmarks with independent exact validation.

Run with Sage's Python (or Python >= 3.10); no third party modules required.
Each --variant is NAME:BACKEND:BINARY where BACKEND is native or m4ri.
Compilation, input generation and verification are outside basis timings.
Subprocess wall times are also recorded. Variants alternate execution order.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE.parent / "pdp-scaling"))
from descend import make_instance


def digest(data):
    return hashlib.sha256(data).hexdigest()


def order(mask):
    return mask.bit_count(), -mask


def multiply(poly, multiplier):
    out = set()
    for term in poly:
        product = term | multiplier
        out.symmetric_difference_update((product,))
    return out


def normal(poly, basis):
    value, remainder = set(poly), set()
    reducers = [(max(g, key=order), set(g)) for g in basis if g]
    while value:
        lead = max(value, key=order)
        for lm, reducer in reducers:
            if lm & lead == lm:
                value ^= multiply(reducer, lead & ~lm)
                break
        else:
            value.remove(lead)
            remainder.add(lead)
    return remainder


def verify(nvars, generators, basis):
    """Independent set arithmetic plus all-assignment truth tables.

    Boolean root-set equality proves equality of ideals in this finite Boolean
    ring; checking source reductions alone would only prove one containment.
    Field critical pairs are essential even for a singleton basis.
    """
    basis = [set(g) for g in basis]
    if any(not g for g in basis):
        raise AssertionError("zero basis row")
    for i, left in enumerate(basis):
        lm = max(left, key=order)
        for variable in range(nvars):
            bit = 1 << variable
            if lm & bit and normal(multiply(left, bit), basis):
                raise AssertionError("missing Boolean field critical pair")
        for right in basis[i + 1:]:
            rm = max(right, key=order)
            common = lm | rm
            if normal(multiply(left, common & ~lm) ^
                      multiply(right, common & ~rm), basis):
                raise AssertionError("nonzero S-pair")
        others = basis[:i] + basis[i + 1:]
        if normal(left, others) != left:
            raise AssertionError("basis not reduced")
    if any(normal(g, basis) for g in generators):
        raise AssertionError("source generator not in output ideal")
    all_bits = (1 << (1 << nvars)) - 1
    truth = [all_bits]
    variables = [sum(1 << a for a in range(1 << nvars) if a & (1 << v))
                 for v in range(nvars)]
    for mask in range(1, 1 << nvars):
        bit = mask & -mask
        truth.append(truth[mask ^ bit] & variables[bit.bit_length() - 1])
    def nonroots(polys):
        result = 0
        for poly in polys:
            value = 0
            for mask in poly:
                value ^= truth[mask]
            result |= value
        return result
    source_nonroots = nonroots(generators)
    if source_nonroots != nonroots(basis):
        raise AssertionError("Boolean root sets differ")
    return {"field_pairs": True, "s_pairs": True, "reduced": True,
            "ideal_equality_exhaustive": True,
            "roots": (all_bits ^ source_nonroots).bit_count()}


def fixtures():
    result = []
    for n, m, ell in [(11, 3, 2), (17, 3, 3), (31, 3, 4)]:
        for seed in range(1, 6):
            inst = make_instance(n, m, ell, seed=seed)
            result.append({"name": f"pdp-{n}-{m}-{ell}-seed{seed}",
                           "nvars": inst.nvars, "seed": seed,
                           "equations": [sorted(g) for g in inst.equations() if g]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--nvars", type=int, nargs="*", default=[6, 9, 12])
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    variants = []
    for spec in args.variant:
        name, backend, path = spec.split(":", 2)
        assert backend in ("native", "m4ri", "dual")
        binary = Path(path).resolve()
        variants.append({"name": name, "backend": backend, "binary": str(binary),
                         "binary_sha256": digest(binary.read_bytes())})
    corpus_path = HERE / "fixtures.json"
    if not corpus_path.exists():
        corpus_path.write_text(json.dumps(fixtures(), indent=2) + "\n")
    corpus = json.loads(corpus_path.read_text())
    report = {"schema": 1, "platform": platform.platform(),
              "python": sys.version, "repeats": args.repeats, "warmups": 1,
              "corpus_sha256": digest(corpus_path.read_bytes()),
              "variants": variants, "cells": [], "load_at_start": os.getloadavg(),
              "claim": "Exact same Boolean reduced GB output contract; dual is packed exhaustive evaluation plus Buchberger-Moller, not F4/F5. Local shared-host diagnostic, no global ranking"}
    for fixture in corpus:
        if fixture["nvars"] not in args.nvars:
            continue
        cell = {"fixture": fixture["name"], "nvars": fixture["nvars"],
                "variants": {v["name"]: {"samples": []} for v in variants}}
        bases = {}
        for repeat in range(args.repeats + 1):
            sequence = variants if repeat % 2 == 0 else list(reversed(variants))
            for variant in sequence:
                native = variant["backend"] == "native"
                entry = cell["variants"][variant["name"]]
                if entry.get("status") == "timeout":
                    continue
                equations = fixture["equations"]
                data = f'{fixture["nvars"]} {len(equations)} {128 if native else 8} { -1 if native else min(8,fixture["nvars"])}\n'
                data += "".join(f'{len(g)} {" ".join(map(str,g))}\n' for g in equations)
                started = time.perf_counter()
                cpu_start = resource.getrusage(resource.RUSAGE_CHILDREN)
                try:
                    run = subprocess.run([variant["binary"]], input=data, text=True,
                                         capture_output=True, timeout=args.timeout, check=True)
                except subprocess.TimeoutExpired:
                    entry.update(status="timeout", timeout_seconds=args.timeout,
                                 censored=True)
                    continue
                wall = time.perf_counter() - started
                cpu_end = resource.getrusage(resource.RUSAGE_CHILDREN)
                cpu = cpu_end.ru_utime + cpu_end.ru_stime - cpu_start.ru_utime - cpu_start.ru_stime
                lines = run.stdout.splitlines()
                head = lines[0].split()
                assert head[0] == "OK"
                basis = []
                for line in lines[1:]:
                    fields = list(map(int, line.split()))
                    assert fields[0] == len(fields) - 1
                    basis.append(fields[1:])
                assert len(basis) == int(head[1])
                key = digest(json.dumps(basis).encode())
                if key not in bases:
                    bases[key] = verify(fixture["nvars"], equations, basis)
                if "basis_sha256" in entry:
                    assert key == entry["basis_sha256"], "nondeterministic output"
                entry.update(status="ok", basis_sha256=key, verification=bases[key], basis_size=len(basis))
                names = (["initial", "signature", "interreduce", "completion", "final_reduce"]
                         if native else ["generation", "population", "elimination", "extraction_completion"])
                values = head[5:10] if native else head[8:12]
                sample = {"basis_seconds": float(head[2]), "wall_seconds": wall,
                          "child_cpu_seconds": cpu, "load_average": os.getloadavg(),
                          "phases": dict(zip(names, map(float, values)))}
                if run.stderr.startswith('{"inner_repeats":'):
                    sample["in_process_batch"] = json.loads(run.stderr)
                if variant["backend"] == "dual":
                    detail = json.loads(run.stderr)
                    sample["phases"] = {"evaluation":detail["evaluation_seconds"], "interpolation":detail["interpolation_seconds"]}
                    sample["root_count"] = detail["roots"]
                    sample["frontier_visits"] = detail["frontier_visits"]
                elif not native:
                    sample["phases"]["signature"] = float(head[5])
                    sample.update(matrix_rows=int(head[6]), matrix_rank=int(head[7]))
                if repeat:
                    entry["samples"].append(sample)
        assert len(bases) <= 1, "canonical bases disagree across variants"
        for entry in cell["variants"].values():
            if entry.get("status") == "timeout":
                continue
            for key in ["basis_seconds", "wall_seconds", "child_cpu_seconds"]:
                entry["median_" + key] = statistics.median(s[key] for s in entry["samples"])
            entry["median_phases"] = {key: statistics.median(s["phases"][key] for s in entry["samples"])
                                      for key in entry["samples"][0]["phases"]}
            if "in_process_batch" in entry["samples"][0]:
                entry["median_basis_cpu_seconds"] = statistics.median(
                    s["in_process_batch"]["basis_cpu_seconds"] for s in entry["samples"])
        report["cells"].append(cell)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(fixture["name"], {name: (round(v["median_basis_seconds"] * 1000, 3)
                                     if v.get("status") == "ok" else v.get("status"))
                               for name, v in cell["variants"].items()}, flush=True)


if __name__ == "__main__":
    main()
