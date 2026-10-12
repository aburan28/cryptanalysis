#!/usr/bin/env python3
"""Explore high-order tau-pair choices beyond the bounded tail policy."""

import argparse
import csv
from functools import lru_cache
import hashlib
from heapq import heappop, heappush
import json
from pathlib import Path
import struct

from make_tau_pair_fused import ZERO, catalog, decode
from make_tau_tail_double import tau2
from run import TABLE, representatives
from screen_tau_tail_double import ENDO_LAMBDA


ROOT = Path(__file__).resolve().parent
BOUND = 64
SIDE = 2 * BOUND + 1
INF = 1 << 30


def index(a, b):
    return (a + BOUND) * SIDE + b + BOUND


def bounded(a, b):
    return max(abs(a), abs(b)) <= BOUND


def lattice_norm(a, b):
    return a * a + 3 * a * b + 3 * b * b


def quotient(a, b, da, db):
    ax, by = a - da, b - db
    assert ax % 3 == by % 3 == 0
    return 2 * (ax // 3) + by, -(ax + by) // 3


def score(words):
    if not words:
        return 0
    assert words[-1] != ZERO
    return 10 * (len(words) - 1) + 16 * sum(word != ZERO for word in words)


def tail_oracle(options):
    point_by_word = {word: (da, db) for da, db, word in options}
    costs = [INF] * (SIDE * SIDE)
    actions = [None] * (SIDE * SIDE)
    origin = index(0, 0)
    costs[origin] = 0
    actions[origin] = ZERO
    heap = [(0, 0, 0)]
    while heap:
        cost, qa, qb = heappop(heap)
        if cost != costs[index(qa, qb)]:
            continue
        base_a, base_b = tau2(qa, qb)
        for da, db, word in options:
            a, b = base_a + da, base_b + db
            if not bounded(a, b) or (a, b) == (0, 0):
                continue
            new_cost = cost + (16 if word != ZERO else 0) + (10 if (qa, qb) != (0, 0) else 0)
            pos = index(a, b)
            if new_cost < costs[pos] or (new_cost == costs[pos] and word < actions[pos]):
                costs[pos], actions[pos] = new_cost, word
                heappush(heap, (new_cost, a, b))
    for a in range(-BOUND, BOUND + 1):
        for b in range(-BOUND, BOUND + 1):
            pos = index(a, b)
            if actions[pos] is None:
                continue
            x, y = a, b
            words = []
            while (x, y) != (0, 0):
                word = actions[index(x, y)]
                da, db = point_by_word[word]
                x, y = quotient(x, y, da, db)
                assert bounded(x, y)
                words.append(word)
                assert len(words) <= 8
            if words:
                assert score(words) == costs[pos]
    return costs, actions


def canonical_step(a, b, words_by_point):
    contribution = [0, 0]
    for odd in (False, True):
        if a % 3:
            digit = TABLE[a % 9, b % 9]
            da, db = digit[:2]
            if odd:
                contribution[0] -= 3 * db
                contribution[1] += da + 3 * db
            else:
                contribution[0] += da
                contribution[1] += db
            a -= da
            b -= db
        assert a % 3 == 0
        a, b = a + b, -(a // 3)
    return (a, b), words_by_point[tuple(contribution)]


def reconstruct(words, representatives):
    a = b = 0
    for word in reversed(words):
        a, b = tau2(a, b)
        da, db = decode(word, representatives)
        a += da
        b += db
    return a, b


def search(start, width, words_by_point, options_by_residue, costs, actions,
           representatives, strategy="beam"):
    @lru_cache(maxsize=100000)
    def canonical_plan(a, b):
        if (a, b) == (0, 0):
            return ()
        if bounded(a, b) and actions[index(a, b)] is not None:
            out = []
            x, y = a, b
            while (x, y) != (0, 0):
                word = actions[index(x, y)]
                da, db = decode(word, representatives)
                out.append(word)
                x, y = quotient(x, y, da, db)
            assert score(out) == costs[index(a, b)]
            return tuple(out)
        (qa, qb), word = canonical_step(a, b, words_by_point)
        return (word,) + canonical_plan(qa, qb)

    baseline = canonical_plan(*start)
    best = baseline
    if start == (0, 0):
        return (), (), 0, canonical_plan.cache_info().misses
    if strategy == "norm":
        path = []
        a, b = start
        expanded = 0
        for _depth in range(32):
            if (a, b) == (0, 0) or (bounded(a, b) and
                                     actions[index(a, b)] is not None):
                break
            choices = options_by_residue[a % 3, b % 3]
            expanded += len(choices)
            def rank(item):
                qa, qb = quotient(a, b, item[0], item[1])
                return lattice_norm(qa, qb), item[2]

            da, db, word = min(choices, key=rank)
            a, b = quotient(a, b, da, db)
            path.append(word)
        candidate = tuple(path) + canonical_plan(a, b)
        if score(candidate) < score(best):
            best = candidate
        assert reconstruct(baseline, representatives) == start
        assert reconstruct(best, representatives) == start
        return baseline, best, expanded, canonical_plan.cache_info().misses
    assert strategy == "beam"
    frontier = [(start[0], start[1], 0, ())]
    expanded = 0
    for depth in range(1, 33):
        candidates = {}
        for a, b, used, path in frontier:
            for da, db, word in options_by_residue[a % 3, b % 3]:
                qa, qb = quotient(a, b, da, db)
                next_path = path + (word,)
                next_used = used + (word != ZERO)
                expanded += 1
                if (qa, qb) == (0, 0):
                    candidate = next_path
                else:
                    candidate = next_path + canonical_plan(qa, qb)
                if score(candidate) < score(best):
                    best = candidate
                if bounded(qa, qb) or (qa, qb) == (0, 0):
                    continue
                previous = candidates.get((qa, qb))
                if previous is None or (next_used, next_path) < previous:
                    candidates[qa, qb] = (next_used, next_path)
        if not candidates:
            break
        ranked = []
        for (a, b), (used, path) in candidates.items():
            completion = path + canonical_plan(a, b)
            ranked.append((score(completion), lattice_norm(a, b),
                           a, b, used, path))
        ranked.sort()
        frontier = [(a, b, used, path) for _estimate, _norm, a, b, used, path
                    in ranked[:width]]
    assert reconstruct(baseline, representatives) == start
    assert reconstruct(best, representatives) == start
    return baseline, best, expanded, canonical_plan.cache_info().misses


def main(args):
    reps, _recipes, words_by_point, _even, _odd = catalog()
    options = [(a, b, word) for (a, b), word in words_by_point.items()]
    assert all(decode(word, reps) == (a, b) for a, b, word in options)
    options.sort(key=lambda item: (lattice_norm(item[0], item[1]), item[2]))
    options_by_residue = {(a, b): [] for a in range(3) for b in range(3)}
    for a, b, word in options:
        options_by_residue[a % 3, b % 3].append((a, b, word))
    costs, actions = tail_oracle(options)
    reached = sum(action is not None for action in actions)
    sources = [Path(__file__).resolve(), ROOT / "make_tau_pair_fused.py",
               ROOT / "make_tau_tail_double.py", ROOT / "screen_tau_tail_double.py",
               ROOT / "run.py", ROOT / "tail-pair-fused-inputs.json"]
    fixture = json.loads((ROOT / "tail-pair-fused-inputs.json").read_text())
    datasets = []
    for case in (fixture["cases"][0], fixture["cases"][4]):
        scalar_path = ROOT / case["scalar_file"]
        raw = scalar_path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == case["scalar_file_sha256"]
        sources.append(scalar_path)
        scalars = struct.unpack(f"<{len(raw)//8}Q", raw)[:args.samples]
        curve = case["curve"]["name"]
        order = case["curve"]["order"]
        omega_lambda = order - ENDO_LAMBDA[curve]
        points = [min(representatives(order, omega_lambda, scalar),
                      key=lambda row: row[0])[1:] for scalar in scalars]
        tau_lambda = (1 - omega_lambda) % order
        assert all((a + b * tau_lambda - scalar) % order == 0
                   for scalar, (a, b) in zip(scalars, points))
        datasets.append((curve, scalars, points))

    widths = tuple(int(item) for item in args.widths.split(","))
    limits = tuple(None if item == "all" else int(item)
                   for item in args.high_options.split(","))
    assert widths and limits and all(width > 0 for width in widths)
    assert all(limit is None or limit > 0 for limit in limits)
    configurations = []
    raw_rows = []
    for limit in limits:
        selected = {residue: options[:limit] for residue, options in
                    options_by_residue.items()}
        for strategy, width in [("norm", 1)] + [("beam", width) for width in widths]:
            rows = []
            for curve, scalars, points in datasets:
                individual = []
                for scalar_index, (scalar, point) in enumerate(zip(scalars, points)):
                    baseline, candidate, expanded, canonical_states = search(
                        point, width, words_by_point, selected, costs, actions,
                        reps, strategy)
                    individual.append({"scalar": scalar,
                                       "baseline_score": score(baseline),
                                       "candidate_score": score(candidate),
                                       "baseline_pairs": len(baseline),
                                       "candidate_pairs": len(candidate),
                                       "baseline_adds": sum(x != ZERO for x in baseline),
                                       "candidate_adds": sum(x != ZERO for x in candidate),
                                       "expanded": expanded,
                                       "canonical_states": canonical_states})
                    raw_rows.append((strategy, "all" if limit is None else limit,
                                     width, curve, scalar_index, scalar,
                                     score(baseline), score(candidate),
                                     len(baseline), len(candidate),
                                     sum(x != ZERO for x in baseline),
                                     sum(x != ZERO for x in candidate),
                                     expanded, canonical_states))
                old = sum(row["baseline_score"] for row in individual)
                new = sum(row["candidate_score"] for row in individual)
                rows.append({"curve": curve, "scalars": len(scalars),
                             "baseline_score": old, "candidate_score": new,
                             "saved_score": old - new,
                             "improved_scalars": sum(
                                 row["candidate_score"] < row["baseline_score"]
                                 for row in individual),
                             "expanded": sum(row["expanded"] for row in individual),
                             "canonical_states": sum(row["canonical_states"]
                                                     for row in individual)})
            configurations.append({"strategy": strategy, "beam_width": width,
                                   "high_options_per_residue": limit,
                                   "results": rows})
    raw_path = ROOT / "global-pair-search-raw.csv"
    with raw_path.open("w", newline="") as raw_file:
        writer = csv.writer(raw_file, lineterminator="\n")
        writer.writerow(("strategy", "high_options_per_residue", "beam_width",
                         "curve", "scalar_index", "scalar", "baseline_score",
                         "candidate_score", "baseline_pairs", "candidate_pairs",
                         "baseline_adds", "candidate_adds", "expanded",
                         "canonical_states"))
        writer.writerows(raw_rows)
    result = {"schema": 1, "status": "design_data_global_pair_recode_screen_only",
              "cpu_timing_claim": None, "academic_novelty_claim": None,
              "sample_per_curve": args.samples,
              "tail_bound": BOUND, "tail_reached_states": reached,
              "exact_pair_options": len(options),
              "reconstructed_outputs": 2 * sum(len(scalars) for _, scalars, _ in datasets) *
                                       len(configurations),
              "raw_csv": raw_path.name,
              "raw_csv_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
              "raw_csv_rows": len(raw_rows),
              "option_counts_by_residue": {f"{a},{b}": len(options_by_residue[a, b])
                                           for a in range(3) for b in range(3)},
              "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in sources}, "configurations": configurations}
    path = ROOT / "global-pair-search-screen.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "tail_reached_states": reached,
                      "configurations": [
                          {"strategy": config["strategy"],
                           "width": config["beam_width"],
                           "high_options": config["high_options_per_residue"],
                           "results": [{k: row[k] for k in
                                        ("curve", "scalars", "saved_score",
                                         "improved_scalars", "expanded",
                                         "canonical_states")}
                                       for row in config["results"]]}
                          for config in configurations]}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--widths", default="1,2,4,8")
    parser.add_argument("--high-options", default="4,8,16,32,all")
    main(parser.parse_args())
