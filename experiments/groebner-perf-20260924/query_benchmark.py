#!/usr/bin/env python3
"""Matched query timing: subprocess, basis verification and curve extraction."""
import json
import importlib.util
from pathlib import Path
import statistics
import time

from benchmark import HERE, digest
from descend import make_instance
import boolean_m4ri_runner as runner


def main():
    spec = importlib.util.spec_from_file_location("control_m4ri_runner", HERE / "corrected/boolean_m4ri_runner.py")
    control = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(control)
    variants = {"corrected": HERE / "build/corrected-m4ri",
                "optimized": HERE / "build/screened-m4ri"}
    corpus = json.loads((HERE / "fixtures.json").read_text())
    report = {"scope": "solve_m4ri including input serialization, subprocess, independent verifier, root extraction and curve replay; instance construction and compilation excluded",
              "repeats": 9, "warmups": 1, "cells": [],
              "binary_sha256": {k:digest(p.read_bytes()) for k,p in variants.items()},
              "python_source_sha256": {"control":digest(Path(control.__file__).read_bytes()),
                                       "optimized":digest(Path(runner.__file__).read_bytes())}}
    for seed in range(1, 6):
        instance = make_instance(31, 3, 4, seed=seed)
        fixture = next(c for c in corpus if c["nvars"] == 12 and c["seed"] == seed)
        assert [sorted(g) for g in instance.equations() if g] == fixture["equations"]
        samples = {name:[] for name in variants}
        hashes = set()
        for repeat in range(10):
            order = list(variants) if repeat % 2 else list(reversed(variants))
            for name in order:
                path = variants[name]
                # Control includes the original exhaustive root extraction;
                # candidate prefilters with the basis before original checks.
                selected = control if name == "corrected" else runner
                selected.m4ri_binary = lambda path=path: (path, {"binary_sha256": report["binary_sha256"][name]})
                started = time.perf_counter()
                result = selected.solve_m4ri(instance, timeout=30, signature_limit=8, matrix_degree=8)
                seconds = time.perf_counter() - started
                assert result["status"] == "solved", result
                assert result["groebner_verified"] and result["generators_reduce_to_zero"] and result["verified"]
                hashes.add(result["basis_sha256"])
                if repeat:
                    samples[name].append({"query_seconds":seconds, "basis_seconds":result["basis_seconds"],
                                          "extraction_seconds":result["extraction_seconds"],
                                          "assignment":result["assignment"], "assignments_checked":result["assignments_checked"],
                                          "basis_candidates_checked":result.get("basis_candidates_checked")})
        assert len(hashes) == 1
        assert len({s["assignment"] for runs in samples.values() for s in runs}) == 1
        medians = {name:statistics.median(s["query_seconds"] for s in runs) for name,runs in samples.items()}
        cell = {"seed":seed,"basis_sha256":hashes.pop(),"verified":True,"samples":samples,
                "median_query_seconds":medians,"speedup":medians["corrected"]/medians["optimized"]}
        report["cells"].append(cell)
        (HERE / "results/query-confirmation.json").write_text(json.dumps(report,indent=2)+"\n")
        print(seed,medians,cell["speedup"],flush=True)


if __name__ == "__main__":
    main()
