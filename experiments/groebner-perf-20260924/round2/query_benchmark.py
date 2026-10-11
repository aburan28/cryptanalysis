"""Four-way paired complete PDP query comparison with frozen round-1 control."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import time

from solve_dual import HERE, make_instance, solve_dual
import boolean_m4ri_runner as current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--output", type=Path, default=HERE / "results/query-confirmation.json")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("round1_runner", HERE / "baseline/boolean_m4ri_runner.py")
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    binary = HERE / "build/round1-m4ri"
    sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    for module in (previous, current):
        module.m4ri_binary = lambda: (binary, {"binary_sha256": sha})
    names = ["round1", "certificate", "dual_process", "dual_library"]
    report = {"scope": "Complete solve query including serialization, process, independent basis verification, root extraction and curve replay; input construction and compilation excluded",
              "claim": "PDP stage diagnostic, not complete DLP cost; shared host", "repeats": 16,
              "load_at_start": os.getloadavg(), "cells": [],
              "cache_policy": "Library loaded once, no numerical basis cache; one warmup followed by 16 recorded solves per target. Warmup retained separately and included in charged_17_query_mean.",
              "sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                         [binary, HERE / "build/boolean-dual", HERE / "build/boolean-dual.dylib", HERE / "solve_dual.py",
                          Path(current.__file__), Path(previous.__file__), Path(__file__),
                          HERE.parent.parent / "pdp-scaling/boolean_basis.py"]}}
    for seed in range(args.seed_start, args.seed_start + 5):
        instance = make_instance(31, 3, 4, seed=seed)
        samples = {n: [] for n in names}
        answers = set()
        warmups = {}
        # Balanced four-arm orders. One warmup per arm, then 16
        # recorded queries per variant; library code resident, no basis cache.
        orders = [(0, 1, 3, 2), (1, 2, 0, 3), (2, 3, 1, 0), (3, 0, 2, 1)]
        for rep in range(17):
            for index in orders[(rep-1) % len(orders)]:
                name = names[index]
                start = time.perf_counter()
                result = solve_dual(instance, transport="subprocess" if index == 2 else "library") if index >= 2 else (
                    previous if index == 0 else current).solve_m4ri(instance, 30, 8, 8)
                elapsed = time.perf_counter() - start
                assert result["status"] == "solved", result
                assert result["groebner_verified"] and result["generators_reduce_to_zero"] and result["verified"]
                answers.add((result["basis_sha256"], result["assignment"]))
                if rep:
                    samples[name].append({"seconds": elapsed, "basis_seconds": result["basis_seconds"],
                                          "extraction_seconds": result["extraction_seconds"]})
                else:
                    warmups[name] = elapsed
        assert len(answers) == 1
        medians = {n: statistics.median(s["seconds"] for s in values) for n, values in samples.items()}
        report["cells"].append({"seed": seed, "answer": answers.pop(), "verified": True,
                                "medians": medians, "samples": samples,
                                "warmup_seconds": warmups,
                                "charged_17_query_mean": {n: (warmups[n]+sum(s["seconds"] for s in values))/17
                                                          for n, values in samples.items()},
                                "speedups": {n: medians["round1"] / medians[n] for n in names[1:]}})
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(seed, medians, report["cells"][-1]["speedups"], flush=True)


if __name__ == "__main__":
    main()
