#!/usr/bin/env python3
"""Greedily co-design three long pair edges with graph-aware recoding."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import scalar_text
from graph_aware_cover_screen import active_masks, sha
from hex9_cover_screen import hex_choices, score_pair
from radius2_graph_screen import graph, matching_atlas
from screen_coset_representatives import N
from tau6_comb13_sparse_screen import SPARSE_TOP_ORBITS
from tau6_comb_screen import digit_stream
from width6_tau_screen import build_width_six_table


HERE = Path(__file__).resolve().parent
SEEDS = {"design": 20261009421, "holdout": 20261009422}
COUNTS = {"design": 2048, "holdout": 4096}
BASELINE_SHA256 = "fbd46d82b7b7867b4bf71dedc46b8ef8a43dd552a94b3779158b347ee1e40b80"
BASELINE_EDGES = tuple(tuple(edge) for edge in json.loads(
    (HERE / "radius3-balanced-screen-result.json").read_text())["edges"]["g33"])
ALL_EDGES = graph(11)


def scalar_features(scalar, table, selected):
    options = []
    for rank, (_, _, a, b) in enumerate(hex_choices(scalar)):
        record = score_pair(a, b, table, selected)
        if record is None:
            continue
        digits = digit_stream((a, b), table, 162)
        options.append((rank, record, tuple(active_masks(digits))))
    assert options and options[0][0] == 0
    return options


def choose_one(options, cardinalities):
    choices = []
    for rank, record, masks in options:
        fusions = sum(cardinalities[mask] for mask in masks)
        choices.append((record["field_product_proxy"] - 11 * fusions,
                        rank, record["mixed_additions"] - fusions,
                        record["tau_steps"], record["top_repaired"],
                        fusions, record["representative"]))
    return min(choices)


def graph_score(features, edges):
    atlas = matching_atlas(edges)
    cardinalities = tuple(len(entry) for entry in atlas)
    return sum(choose_one(options, cardinalities)[0] for options in features)


def select_edges(features):
    selected = set(graph(3))
    steps = []
    for _ in range(3):
        candidates = [(graph_score(features, tuple(sorted(selected | {edge}))), edge)
                      for edge in ALL_EDGES if edge not in selected]
        best_score, best_edge = min(candidates)
        selected.add(best_edge)
        steps.append({"edge": best_edge, "design_proxy": best_score,
                      "ties": sum(score == best_score for score, _ in candidates)})
    return tuple(sorted(selected)), steps


def native_baseline_check(binary, scalars, features):
    process = subprocess.run(
        [str(binary), "--scalar-w6-comb13-hex9-graphaware33-fixed"],
        input="".join(scalar_text(scalar) + "\n" for scalar in scalars),
        capture_output=True, text=True, check=True, timeout=900)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(features)
    cardinalities = tuple(len(entry) for entry in matching_atlas(BASELINE_EDGES))
    for index, (row, options) in enumerate(zip(rows, features)):
        cost, rank, additions, tau, repair, fusions, representative = choose_one(options, cardinalities)
        assert list(map(int, row["representative"])) == representative, index
        assert row["tau_steps"] == tau and row["nonzero_digits"] == additions, index
        work = row["recoding_work"]
        assert work["top_repaired"] == repair and work["pair_fusions"] == fusions, index
        assert work["coset_rank"] == rank and work["valid_representatives"] == len(options), index
        assert work["attempted_representatives"] == 9, index
        assert cost == 5 * tau + 11 * additions, index


def panel_features(panel, table, selected):
    rng = random.Random(SEEDS[panel])
    scalars = [rng.randrange(N) for _ in range(COUNTS[panel])]
    features = [scalar_features(value, table, selected) for value in scalars]
    digest = hashlib.sha256(b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest()
    return scalars, features, digest


def summarize(features, reference_edges, candidate_edges):
    atlases = {name: matching_atlas(edges) for name, edges in
               (("reference", reference_edges), ("candidate", candidate_edges))}
    counts = {name: tuple(len(entry) for entry in atlas) for name, atlas in atlases.items()}
    totals = Counter()
    deltas = Counter()
    rows = []
    for index, options in enumerate(features):
        reference = choose_one(options, counts["reference"])
        candidate = choose_one(options, counts["candidate"])
        delta = reference[0] - candidate[0]
        deltas[delta] += 1
        totals.update({"cases": 1, "reference_proxy": reference[0],
                       "candidate_proxy": candidate[0],
                       "reference_mixed_additions": reference[2],
                       "candidate_mixed_additions": candidate[2],
                       "reference_tau_steps": reference[3],
                       "candidate_tau_steps": candidate[3],
                       "reference_fusions": reference[5],
                       "candidate_fusions": candidate[5],
                       "rank_changes": int(reference[1] != candidate[1])})
        rows.append({"index": index, "reference_rank": reference[1],
                     "candidate_rank": candidate[1],
                     "reference_proxy": reference[0], "candidate_proxy": candidate[0],
                     "reference_fusions": reference[5], "candidate_fusions": candidate[5]})
    return {"totals": dict(totals), "delta_counts": dict(sorted(deltas.items())),
            "rows": rows, "atlas_sha256": {name: hashlib.sha256(
                json.dumps(atlas).encode()).hexdigest() for name, atlas in atlases.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", choices=SEEDS, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output exists")
    binary = args.binary.resolve(strict=True)
    if sha(binary) != BASELINE_SHA256:
        raise SystemExit("graph-aware reference binary differs from protocol")
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    selected = set(SPARSE_TOP_ORBITS)
    scalars, features, input_hash = panel_features(args.panel, table, selected)
    if args.panel == "design":
        chosen_edges, steps = select_edges(features)
    else:
        design = json.loads((HERE / "joint-graph-design.json").read_text())
        assert design["panel"] == "design" and design["status"] == "design_complete"
        assert design["protocol_sha256"] == sha(HERE / "JOINT_GRAPH_PROTOCOL.md")
        assert design["screen_sha256"] == sha(Path(__file__))
        chosen_edges = tuple(tuple(edge) for edge in design["candidate_edges"])
        steps = design["greedy_steps"]
    native_baseline_check(binary, scalars[:128], features[:128])
    result = summarize(features, BASELINE_EDGES, chosen_edges)
    totals = result["totals"]
    gain = totals["reference_proxy"] - totals["candidate_proxy"]
    passed = gain * 200 >= totals["reference_proxy"]
    result.update({"schema": 1, "panel": args.panel,
                   "status": "design_complete" if args.panel == "design" else
                             ("screen_passed" if passed else "screen_stopped"),
                   "seed": SEEDS[args.panel], "count": COUNTS[args.panel],
                   "input_sha256": input_hash, "baseline_binary_sha256": sha(binary),
                   "protocol_sha256": sha(HERE / "JOINT_GRAPH_PROTOCOL.md"),
                   "screen_sha256": sha(Path(__file__)),
                   "reference_edges": BASELINE_EDGES, "candidate_edges": chosen_edges,
                   "greedy_steps": steps, "table_bytes": 33 * 81 * 81 * 6 * 72,
                   "gain_percent": 100 * gain / totals["reference_proxy"],
                   "native_baseline_checks": 128,
                   "regression_cases": sum(count for delta, count in
                                           result["delta_counts"].items() if int(delta) < 0)})
    assert len(chosen_edges) == 33 and result["table_bytes"] <= 90 * (1 << 20)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"panel": args.panel, "status": result["status"],
                      "greedy_steps": steps, "gain_percent": result["gain_percent"],
                      "totals": totals, "regression_cases": result["regression_cases"],
                      "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
