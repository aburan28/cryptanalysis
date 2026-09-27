#!/usr/bin/env python3
"""Bound an n=13,k=2 homogeneous-component attempt on a frozen positive query.

A completed Macaulay matrix alone does not certify a subgroup relation. This
diagnostic keeps its rank and collection yield null until an exact lifted point
triple and projected subgroup row are independently checked.
"""

import argparse
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

from homogeneous_components import eliminate, tagged_rows
from relation_gate import ORDER, SEED, mul, prepare_base


def worker(target_index):
    t = time.perf_counter_ns()
    field, _, _, _, generator, base, setup_ns = prepare_base()
    import random
    rng = random.Random(SEED)
    scalar = [rng.randrange(1, ORDER) for _ in range(target_index + 1)][-1]
    point = mul(field, generator, scalar)
    target_x = point[0]
    print(json.dumps({"stage": "input_ready", "target_index": target_index,
                      "target_scalar": scalar, "target_point": point,
                      "base_points": len(base["projected_points"]),
                      "base_setup_ns": setup_ns,
                      "elapsed_ns": time.perf_counter_ns() - t}), flush=True)
    begin = time.perf_counter_ns()
    _, _, _, groups = tagged_rows(13, 2, target_x, (4, 4, 4))
    print(json.dumps({"stage": "rows_built",
                      "row_construction_ns": time.perf_counter_ns() - begin,
                      "degree_components": len(groups),
                      "rows": sum(map(len, groups.values())),
                      "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "elapsed_ns": time.perf_counter_ns() - t}), flush=True)
    begin = time.perf_counter_ns()
    _, matrix = eliminate(groups, True, 2)
    print(json.dumps({"stage": "matrix_reduced",
                      "elimination_ns": time.perf_counter_ns() - begin,
                      "matrix": matrix,
                      "elapsed_ns": time.perf_counter_ns() - t,
                      "subgroup_relation": None, "independent_rank": None}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--worker", action="store_true")
    p.add_argument("--target-index", type=int, default=16)
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--out", type=Path, default=Path("relation_probe_results.json"))
    args = p.parse_args()
    if args.worker:
        worker(args.target_index)
        return
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--target-index", str(args.target_index)]
    started = time.perf_counter()
    try:
        process = subprocess.run(command, capture_output=True, timeout=args.timeout,
                                 text=True, check=False)
        output = process.stdout
        status = "matrix_completed_relation_unverified" if process.returncode == 0 else "error"
        stderr_tail = process.stderr[-1000:]
    except subprocess.TimeoutExpired as exc:
        status = "timeout"
        output = exc.stdout or b""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        stderr_tail = None
    wall = time.perf_counter() - started
    stages = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    result = {
        "schema": "homogeneous-fraction-large-probe.v1",
        "status": status, "target_selection": "positive target selected from frozen "
        "seed after the direct control; diagnostic only, not a yield estimate",
        "seed": SEED, "target_index": args.target_index,
        "timeout_seconds": args.timeout, "charged_wall_seconds": wall,
        "stages": stages, "stderr_tail": stderr_tail,
        "independent_verified_relations": None,
        "seconds_per_independent_relation": None,
        "cost_ratio_to_control": None,
    }
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "charged_wall_seconds", "timeout_seconds",
                       "independent_verified_relations")}), flush=True)


if __name__ == "__main__":
    main()
