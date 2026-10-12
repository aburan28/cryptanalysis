#!/usr/bin/env python3
"""Screen matching graphs on frozen native tau-comb digit streams."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import scalar_text
from screen_coset_representatives import N
from tau6_comb_screen import digit_stream
from width6_tau_screen import build_width_six_table

HERE = Path(__file__).resolve().parent
SEEDS = (20261009161, 20261009162)
COUNT = 2048
EVEN_EDGES = tuple(range(0, 11, 2))
ENTRIES_PER_EDGE = 81 * 81 * 6
SLOT_BYTES = 104


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fusions(mask, edges):
    count = 0
    for row in edges:
        if mask & (3 << row) == 3 << row:
            count += 1
    return count


def path_fusions(mask):
    row = 0
    count = 0
    while row < 11:
        if mask & (3 << row) == 3 << row:
            count += 1
            row += 2
        else:
            row += 1
    return count


def run(binary, scalars):
    process = subprocess.run(
        [str(binary), "--scalar-w6-comb13-hex9-paired-fixed"],
        input="".join(scalar_text(value) + "\n" for value in scalars),
        text=True, capture_output=True, check=True, timeout=600,
    )
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def panel(rows, table):
    totals = Counter()
    occupancy = Counter()
    no_gain_cases = 0
    per_case = hashlib.sha256()
    for index, result in enumerate(rows):
        digits = digit_stream(tuple(map(int, result["representative"])), table, 162)
        even = path = complete = 0
        for column in range(13):
            mask = sum(1 << row for row in range(12)
                       if row * 13 + column < len(digits)
                       and digits[row * 13 + column] is not None)
            occupancy[mask.bit_count()] += 1
            even += fusions(mask, EVEN_EDGES)
            path += path_fusions(mask)
            complete += mask.bit_count() // 2
        assert even == result["recoding_work"]["pair_fusions"], index
        assert even <= path <= complete, index
        if even == path:
            no_gain_cases += 1
        adds = result["nonzero_digits"] + even
        tau = result["tau_steps"]
        totals.update({"cases": 1, "tau_steps": tau, "baseline_adds": adds - even,
                       "path_adds": adds - path, "complete_adds": adds - complete,
                       "baseline_fusions": even, "path_fusions": path,
                       "complete_fusions": complete,
                       "baseline_proxy": 5 * tau + 11 * (adds - even),
                       "path_proxy": 5 * tau + 11 * (adds - path),
                       "complete_proxy": 5 * tau + 11 * (adds - complete)})
        per_case.update(f"{even},{path},{complete},{tau},{adds}\n".encode())
    return {"totals": dict(totals), "occupancy": dict(sorted(occupancy.items())),
            "no_gain_cases": no_gain_cases,
            "per_case_sha256": per_case.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output already exists")
    binary = args.binary.resolve(strict=True)
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    panels = {}
    for name, seed in zip(("design", "holdout"), SEEDS):
        rng = random.Random(seed)
        scalars = [rng.randrange(N) for _ in range(COUNT)]
        panels[name] = panel(run(binary, scalars), table)
        panels[name]["scalar_sha256"] = hashlib.sha256(
            b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest()
    holdout = panels["holdout"]["totals"]
    improvement = (holdout["baseline_proxy"] - holdout["path_proxy"])
    passes = improvement * 100 >= holdout["baseline_proxy"]
    result = {"schema": 1, "status": "screen_passed" if passes else "screen_stopped",
              "seeds": SEEDS, "count_per_panel": COUNT,
              "baseline_edges": list(EVEN_EDGES), "path_edges": list(range(11)),
              "table_bytes": {"baseline": 6 * ENTRIES_PER_EDGE * SLOT_BYTES,
                              "path": 11 * ENTRIES_PER_EDGE * SLOT_BYTES,
                              "complete": 66 * ENTRIES_PER_EDGE * SLOT_BYTES},
              "source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
              "binary_sha256": sha(binary), "protocol_sha256": sha(HERE / "PAIR_GRAPH_PROTOCOL.md"),
              "checker_sha256": sha(Path(__file__)), "panels": panels}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "improvement_percent":
                      100 * improvement / holdout["baseline_proxy"],
                      "holdout": holdout, "result_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
