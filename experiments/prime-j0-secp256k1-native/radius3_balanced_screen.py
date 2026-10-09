#!/usr/bin/env python3
"""Select three edges beyond radius three on frozen public-scalar panels."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import scalar_text
from radius2_graph_screen import ENTRIES_PER_EDGE, ROWS, graph, mask_stream, matching_atlas, sha
from screen_coset_representatives import N
from width6_tau_screen import build_width_six_table


HERE = Path(__file__).resolve().parent
SEEDS = (20261009331, 20261009332)
COUNT = 4096
SLOT_BYTES = 72
REFERENCE_SHA256 = "b9c194c9105ef41daf95cef229d72434d5421e72ffd714dc32ed8ee7bb41f6ad"


def run(binary, scalars):
    process = subprocess.run(
        [str(binary), "--scalar-w6-comb13-hex9-radius2-fixed"],
        input="".join(scalar_text(value) + "\n" for value in scalars),
        text=True, capture_output=True, check=True, timeout=900,
    )
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def masks_and_rows(binary, seed, table):
    rng = random.Random(seed)
    scalars = [rng.randrange(N) for _ in range(COUNT)]
    rows = run(binary, scalars)
    masks = [mask_stream(row, table) for row in rows]
    occupancy = Counter(mask for case_masks in masks for mask in case_masks)
    for index, (row, case_masks) in enumerate(zip(rows, masks)):
        assert len(case_masks) == 13
        expected = sum(len(ATLAS2[mask]) for mask in case_masks)
        assert row["recoding_work"]["pair_fusions"] == expected, index
    scalar_hash = hashlib.sha256(
        b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest()
    return rows, masks, occupancy, scalar_hash


def score(atlas, occupancy):
    return sum(frequency * len(atlas[mask]) for mask, frequency in occupancy.items())


def choose_edges(occupancy):
    chosen = set(graph(3))
    steps = []
    all_edges = graph(ROWS - 1)
    for _ in range(3):
        proposals = []
        for edge in all_edges:
            if edge in chosen:
                continue
            atlas = matching_atlas(tuple(sorted(chosen | {edge})))
            proposals.append((edge, score(atlas, occupancy)))
        best_score = max(value for _, value in proposals)
        best_edge = min(edge for edge, value in proposals if value == best_score)
        chosen.add(best_edge)
        steps.append({"edge": best_edge, "design_fusions": best_score,
                      "ties": sum(value == best_score for _, value in proposals)})
    return tuple(sorted(chosen)), steps


def summarize(rows, masks, atlases):
    totals = Counter()
    deltas = Counter()
    fingerprint = hashlib.sha256()
    minimum = 100
    for index, (row, case_masks) in enumerate(zip(rows, masks)):
        fusions = {name: sum(len(atlas[mask]) for mask in case_masks)
                   for name, atlas in atlases.items()}
        assert fusions["g2"] == row["recoding_work"]["pair_fusions"], index
        assert fusions["g2"] <= fusions["g3"] <= fusions["g33"], index
        unfused = row["nonzero_digits"] + fusions["g2"]
        tau = row["tau_steps"]
        delta = fusions["g33"] - fusions["g2"]
        minimum = min(minimum, delta)
        deltas[delta] += 1
        totals.update({"cases": 1, "tau_steps": tau})
        for name, count in fusions.items():
            additions = unfused - count
            totals[f"{name}_fusions"] += count
            totals[f"{name}_adds"] += additions
            totals[f"{name}_proxy"] += 5 * tau + 11 * additions
        fingerprint.update(
            f"{fusions['g2']},{fusions['g3']},{fusions['g33']},{tau},{unfused}\n".encode())
    return {"totals": dict(totals), "g33_minus_g2_per_scalar": dict(sorted(deltas.items())),
            "minimum_fusion_delta": minimum, "per_case_sha256": fingerprint.hexdigest()}


ATLAS2 = matching_atlas(graph(2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output already exists")
    binary = args.binary.resolve(strict=True)
    if sha(binary) != REFERENCE_SHA256:
        raise SystemExit("radius-two reference binary differs from frozen parent")
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    design = masks_and_rows(binary, SEEDS[0], table)
    edges33, steps = choose_edges(design[2])
    assert len(edges33) == 33
    atlases = {"g2": ATLAS2, "g3": matching_atlas(graph(3)),
               "g33": matching_atlas(edges33)}
    holdout = masks_and_rows(binary, SEEDS[1], table)
    panels = {}
    for name, panel in (("design", design), ("holdout", holdout)):
        rows, masks, occupancy, scalar_hash = panel
        panels[name] = summarize(rows, masks, atlases)
        panels[name]["scalar_sha256"] = scalar_hash
        panels[name]["mask_occupancy_sha256"] = hashlib.sha256(
            json.dumps(sorted(occupancy.items())).encode()).hexdigest()
    totals = panels["holdout"]["totals"]
    gain = totals["g2_proxy"] - totals["g33_proxy"]
    bytes_by_graph = {name: len(edges) * ENTRIES_PER_EDGE * SLOT_BYTES
                      for name, edges in (("g2", graph(2)),
                                          ("g3", graph(3)), ("g33", edges33))}
    passes = (gain * 100 >= 3 * totals["g2_proxy"]
              and panels["holdout"]["minimum_fusion_delta"] >= 0
              and bytes_by_graph["g33"] <= 90 * (1 << 20))
    result = {
        "schema": 1, "status": "screen_passed" if passes else "screen_stopped",
        "seeds": SEEDS, "count_per_panel": COUNT, "slot_bytes": SLOT_BYTES,
        "edges": {"g2": graph(2), "g3": graph(3), "g33": edges33},
        "greedy_steps": steps, "table_bytes": bytes_by_graph,
        "atlas_sha256": {name: hashlib.sha256(json.dumps(atlas).encode()).hexdigest()
                         for name, atlas in atlases.items()},
        "reference_binary_sha256": sha(binary),
        "protocol_sha256": sha(HERE / "RADIUS3_BALANCED_PROTOCOL.md"),
        "checker_sha256": sha(Path(__file__)), "panels": panels,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "selected_edges": steps,
                      "table_bytes": bytes_by_graph, "holdout": totals,
                      "gain_percent": 100 * gain / totals["g2_proxy"],
                      "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
