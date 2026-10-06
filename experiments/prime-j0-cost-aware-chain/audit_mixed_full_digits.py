#!/usr/bin/env python3
"""Read-only exact-path, Bellman, and scalar audit for the full-digit atlas."""

import csv
import hashlib
import json
from pathlib import Path
import re
import struct

from make_tau_pair_fused import ZERO, catalog
from make_tau_tail_double import tau2
from run import representatives
from screen_global_pair_search import (BOUND, SIDE, bounded, canonical_step, index,
                                       lattice_norm, tail_oracle)
from screen_mixed_radix_tail import (KIND_DOUBLE, KIND_PAIR, KIND_TAU,
                                     STEP_COSTS, cost, path_from,
                                     reconstruct_mixed, tau)
from screen_tau_tail_double import ENDO_LAMBDA


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
HEADER = REPO / "src/generated/tau_pair_mixed_full_digits.h"
OLD_HEADER = REPO / "src/generated/tau_pair_mixed_radix_tail.h"
RAW = ROOT / "mixed-full-digits-raw.csv"
SUMMARY = ROOT / "mixed-full-digits-screen.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path, symbol):
    body = path.read_text().split(f"{symbol}[16641] = {{", 1)[1].split("};", 1)[0]
    values = [int(value) for value in re.findall(r"\d+", body)]
    assert len(values) == SIDE * SIDE
    return [(value >> 10, value & 1023) for value in values]


def main():
    summary = json.loads(SUMMARY.read_text())
    assert summary["schema"] == 1
    assert summary["status"] == "retrospective_exact_full_digit_mixed_screen"
    assert summary["header_sha256"] == sha256(HEADER)
    assert summary["old_header_sha256"] == sha256(OLD_HEADER)
    assert summary["raw_csv_sha256"] == sha256(RAW)
    assert summary["digit_count_per_radix"] == 727
    assert summary["encoded_action_bytes"] == 2 * SIDE * SIDE == 33282
    for name, digest in summary["source_sha256"].items():
        assert sha256(REPO / name) == digest, name
    full_actions = parse(HEADER, "ca_tau_pair_mixed_full_action")
    old_actions = parse(OLD_HEADER, "ca_tau_pair_mixed_action")
    assert full_actions[index(0, 0)] == (KIND_PAIR, ZERO)

    _, _, words_by_point, _, _ = catalog()
    points = {word: point for point, word in words_by_point.items()}
    options = sorted(((a, b, word) for (a, b), word in words_by_point.items()),
                     key=lambda item: (lattice_norm(item[0], item[1]), item[2]))
    assert len(options) == 727
    _, pure_actions = tail_oracle(options)
    distances = [0] * (SIDE * SIDE)
    better = 0
    for a in range(-BOUND, BOUND + 1):
        for b in range(-BOUND, BOUND + 1):
            pos = index(a, b)
            path = path_from((a, b), full_actions, points)
            assert reconstruct_mixed(path, points) == (a, b)
            distances[pos] = cost(path)
            old_cost = cost(path_from((a, b), old_actions, points))
            assert distances[pos] <= old_cost
            better += distances[pos] < old_cost
    assert better == summary["strictly_better_states"]

    edges = 0
    for qa in range(-BOUND, BOUND + 1):
        for qb in range(-BOUND, BOUND + 1):
            base_cost = distances[index(qa, qb)]
            for kind, base in ((KIND_PAIR, tau2(qa, qb)),
                               (KIND_TAU, tau(qa, qb)),
                               (KIND_DOUBLE, (2 * qa, 2 * qb))):
                for da, db, word in options:
                    a, b = base[0] + da, base[1] + db
                    if not bounded(a, b) or (a, b) == (0, 0):
                        continue
                    edges += 1
                    edge_cost = (STEP_COSTS[kind] if (qa, qb) != (0, 0) else 0) + \
                        (16 if word != ZERO else 0)
                    assert distances[index(a, b)] <= base_cost + edge_cost
    assert edges == summary["graph_edges_examined"]

    with RAW.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    fixture = json.loads((ROOT / "tail-pair-fused-inputs.json").read_text())
    samples = summary["samples_per_case"]
    assert len(rows) == 4 * samples
    summaries = []
    offset = 0
    for case_index in (0, 1, 4, 5):
        case = fixture["cases"][case_index]
        group = rows[offset:offset + samples]
        offset += samples
        scalar_path = ROOT / case["scalar_file"]
        assert sha256(scalar_path) == case["scalar_file_sha256"]
        scalars = struct.unpack(f"<{samples}Q", scalar_path.read_bytes()[:8 * samples])
        curve = case["curve"]["name"]
        order = case["curve"]["order"]
        omega_lambda = order - ENDO_LAMBDA[curve]
        totals = {"mixed_score": 0, "full_digit_score": 0, "full_pairs": 0,
                  "full_tau_steps": 0, "full_doubles": 0, "full_adds": 0}
        improved = 0
        for scalar_index, (scalar, row) in enumerate(zip(scalars, group)):
            assert row["case_id"] == case["id"]
            assert row["curve"] == curve and int(row["point_index"]) == case["point_index"]
            assert int(row["scalar_index"]) == scalar_index
            assert int(row["scalar"]) == scalar
            _, a, b = min(representatives(order, omega_lambda, scalar),
                          key=lambda item: item[0])
            start = (a, b)
            state = start
            high = []
            while state != (0, 0) and (not bounded(*state) or
                                         pure_actions[index(*state)] is None):
                state, word = canonical_step(*state, words_by_point)
                high.append((KIND_PAIR, word))
            old = tuple(high) + path_from(state, old_actions, points)
            full = tuple(high) + path_from(state, full_actions, points)
            assert reconstruct_mixed(full, points) == start
            expected = {"mixed_score": cost(old), "full_digit_score": cost(full),
                        "high_pairs": len(high),
                        "full_pairs": sum(kind == KIND_PAIR for kind, _ in full),
                        "full_tau_steps": sum(kind == KIND_TAU for kind, _ in full),
                        "full_doubles": sum(kind == KIND_DOUBLE for kind, _ in full),
                        "full_adds": sum(word != ZERO for _, word in full)}
            for key, wanted in expected.items():
                assert int(row[key]) == wanted, (case["id"], scalar_index, key)
            for key in totals:
                totals[key] += expected[key]
            improved += expected["full_digit_score"] < expected["mixed_score"]
        old_total = totals["mixed_score"]
        full_total = totals["full_digit_score"]
        summaries.append({"case_id": case["id"], "count": samples,
                          **totals, "saved_score": old_total - full_total,
                          "saving_percent": 100 * (old_total - full_total) / old_total,
                          "improved_scalars": improved})
    assert summaries == summary["summaries"]
    print(f"PASS: {len(full_actions):,} exact states, {edges:,} Bellman edges, "
          f"{len(rows):,} old scalar rows, four totals")


if __name__ == "__main__":
    main()
