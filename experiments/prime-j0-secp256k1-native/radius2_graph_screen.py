#!/usr/bin/env python3
"""Screen exact active-row matchings for bounded-distance tau-comb graphs."""

import argparse
from collections import Counter
from functools import lru_cache
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
SEEDS = (20261009241, 20261009242)
COUNT = 4096
ROWS = 12
MASK_COUNT = 1 << ROWS
SLOT_BYTES = 104
ENTRIES_PER_EDGE = 81 * 81 * 6
REFERENCE_BINARY_SHA256 = "e8ffd24be7ea2c976b9ab8f31cea7d7d1cda0b6fbeb35b7e5b95ba2e1ae411aa"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def graph(radius):
    return tuple((i, j) for i in range(ROWS) for j in range(i + 1, ROWS)
                 if j - i <= radius)


def matching_atlas(edges):
    neighbors = [0] * ROWS
    for left, right in edges:
        neighbors[left] |= 1 << right
        neighbors[right] |= 1 << left

    @lru_cache(maxsize=None)
    def solve(mask):
        if mask == 0:
            return ()
        bit = mask & -mask
        vertex = bit.bit_length() - 1
        rest = mask ^ bit
        best = solve(rest)
        choices = neighbors[vertex] & rest
        while choices:
            other_bit = choices & -choices
            other = other_bit.bit_length() - 1
            candidate = tuple(sorted(((vertex, other),) + solve(rest ^ other_bit)))
            if len(candidate) > len(best) or len(candidate) == len(best) and candidate < best:
                best = candidate
            choices ^= other_bit
        return best

    atlas = tuple(solve(mask) for mask in range(MASK_COUNT))
    for mask, edges_for_mask in enumerate(atlas):
        used = 0
        for left, right in edges_for_mask:
            bits = (1 << left) | (1 << right)
            assert bits & mask == bits and bits & used == 0
            used |= bits
    return atlas


def run(binary, scalars):
    process = subprocess.run(
        [str(binary), "--scalar-w6-comb13-hex9-path-fixed"],
        input="".join(scalar_text(value) + "\n" for value in scalars),
        text=True, capture_output=True, check=True, timeout=600,
    )
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def mask_stream(row, table):
    digits = digit_stream(tuple(map(int, row["representative"])), table, 162)
    return tuple(sum(1 << index for index in range(ROWS)
                     if index * 13 + column < len(digits)
                     and digits[index * 13 + column] is not None)
                 for column in range(13))


def summarize(rows, table, atlases):
    totals = Counter()
    occupancy = Counter()
    deltas = Counter()
    fingerprint = hashlib.sha256()
    for index, row in enumerate(rows):
        masks = mask_stream(row, table)
        for mask in masks:
            occupancy[mask.bit_count()] += 1
        counts = {name: sum(len(atlas[mask]) for mask in masks)
                  for name, atlas in atlases.items()}
        assert counts["g1"] == row["recoding_work"]["pair_fusions"], index
        assert counts["g1"] <= counts["g2"] <= counts["g3"] <= counts["complete"], index
        additions = row["nonzero_digits"] + counts["g1"]
        tau = row["tau_steps"]
        deltas[counts["g2"] - counts["g1"]] += 1
        totals.update({"cases": 1, "tau_steps": tau})
        for name, fusions in counts.items():
            totals[f"{name}_fusions"] += fusions
            totals[f"{name}_adds"] += additions - fusions
            totals[f"{name}_proxy"] += 5 * tau + 11 * (additions - fusions)
        fingerprint.update(
            f"{counts['g1']},{counts['g2']},{counts['g3']},{counts['complete']},{tau},{additions}\n".encode())
    return {"totals": dict(totals), "occupancy": dict(sorted(occupancy.items())),
            "g2_minus_g1_fusions_per_scalar": dict(sorted(deltas.items())),
            "per_case_sha256": fingerprint.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output already exists")
    binary = args.binary.resolve(strict=True)
    if sha(binary) != REFERENCE_BINARY_SHA256:
        raise SystemExit("reference binary differs from frozen path")
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    graphs = {"g1": graph(1), "g2": graph(2), "g3": graph(3),
              "complete": graph(ROWS - 1)}
    assert [len(graphs[name]) for name in graphs] == [11, 21, 30, 66]
    atlases = {name: matching_atlas(edges) for name, edges in graphs.items()}
    panels = {}
    for name, seed in zip(("design", "holdout"), SEEDS):
        rng = random.Random(seed)
        scalars = [rng.randrange(N) for _ in range(COUNT)]
        panels[name] = summarize(run(binary, scalars), table, atlases)
        panels[name]["scalar_sha256"] = hashlib.sha256(
            b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest()
    holdout = panels["holdout"]["totals"]
    improvement = holdout["g1_proxy"] - holdout["g2_proxy"]
    table_bytes = {name: len(edges) * ENTRIES_PER_EDGE * SLOT_BYTES
                   for name, edges in graphs.items()}
    passes = improvement * 100 >= 3 * holdout["g1_proxy"] and table_bytes["g2"] <= 90 * (1 << 20)
    result = {"schema": 1, "status": "screen_passed" if passes else "screen_stopped",
              "seeds": SEEDS, "count_per_panel": COUNT,
              "graphs": {name: list(edges) for name, edges in graphs.items()},
              "table_bytes": table_bytes,
              "atlas_sha256": {name: hashlib.sha256(json.dumps(atlas).encode()).hexdigest()
                               for name, atlas in atlases.items()},
              "reference_binary_sha256": sha(binary),
              "protocol_sha256": sha(HERE / "RADIUS2_GRAPH_PROTOCOL.md"),
              "checker_sha256": sha(Path(__file__)), "panels": panels}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "table_bytes": table_bytes,
                      "holdout_improvement_percent":
                      100 * improvement / holdout["g1_proxy"],
                      "holdout": holdout, "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
