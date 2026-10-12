#!/usr/bin/env python3
"""Read-only audit of the exact mixed-radix bounded-tail design screen."""

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
                                       lattice_norm, score, tail_oracle)
from screen_mixed_radix_tail import (HEADER, KIND_DOUBLE, KIND_PAIR, KIND_TAU,
                                     RAW, ROOT, SUMMARY, STEP_COSTS, cost,
                                     path_from, reconstruct_mixed, tau)
from screen_periodic_pair_atlas import periodic_plan, reference_plan
from screen_tau_tail_double import ENDO_LAMBDA


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    summary = json.loads(SUMMARY.read_text())
    assert summary["schema"] == 1
    assert summary["status"] == "retrospective_exact_mixed_radix_tail_screen"
    assert summary["header_sha256"] == sha256(HEADER)
    assert summary["raw_csv_sha256"] == sha256(RAW)
    assert summary["radix_step_model"] == {"tau2": 10, "tau": 6,
                                            "double": 8, "nonzero_digit": 16}
    assert summary["encoded_action_bytes"] == 2 * SIDE * SIDE == 33282
    for name, digest in summary["source_sha256"].items():
        assert sha256(ROOT.parents[1] / name) == digest, name
    body = HEADER.read_text().split("ca_tau_pair_mixed_action[16641] = {", 1)[1]
    body = body.split("};", 1)[0]
    codes = [int(item) for item in re.findall(r"\d+", body)]
    assert len(codes) == SIDE * SIDE
    actions = [(code >> 10, code & 1023) for code in codes]
    assert all(kind in (KIND_PAIR, KIND_TAU, KIND_DOUBLE) for kind, _ in actions)
    assert actions[index(0, 0)] == (KIND_PAIR, ZERO)

    reps, _, words_by_point, _, _ = catalog()
    points = {word: point for point, word in words_by_point.items()}
    options = sorted(((a, b, word) for (a, b), word in words_by_point.items()),
                     key=lambda item: (lattice_norm(item[0], item[1]), item[2]))
    pure_costs, pure_actions = tail_oracle(options)
    distances = [0] * (SIDE * SIDE)
    for a in range(-BOUND, BOUND + 1):
        for b in range(-BOUND, BOUND + 1):
            path = path_from((a, b), actions, points)
            assert reconstruct_mixed(path, points) == (a, b)
            pos = index(a, b)
            distances[pos] = cost(path)
            assert distances[pos] <= pure_costs[pos]
    assert sum(action is not None for action in pure_actions) == \
        summary["pure_reached_states"] == 15043
    assert len(actions) == summary["mixed_reached_states"] == 16641
    assert sum(distances[i] < pure_costs[i] and pure_actions[i] is not None
               for i in range(len(actions))) == summary["better_bounded_states"]

    units = ((0, 0), (1, 0), (-1, 0), (1, -1), (-1, 1), (-2, 1), (2, -1))
    unit_options = [(a, b, words_by_point[(a, b)]) for a, b in units]
    edges = 0
    for qa in range(-BOUND, BOUND + 1):
        for qb in range(-BOUND, BOUND + 1):
            base_cost = distances[index(qa, qb)]
            for kind, base, candidates in ((KIND_PAIR, tau2(qa, qb), options),
                                           (KIND_TAU, tau(qa, qb), unit_options),
                                           (KIND_DOUBLE, (2 * qa, 2 * qb), unit_options)):
                for da, db, word in candidates:
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
    selected = set(json.loads((ROOT / "firstword-pair-gate-screen.json").read_text())
                   ["selected_words"])
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
        totals = {"canonical_score": 0, "firstword_score": 0, "mixed_score": 0,
                  "mixed_tau_steps": 0, "mixed_doubles": 0, "mixed_adds": 0}
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
            mixed = tuple(high) + path_from(state, actions, points)
            assert reconstruct_mixed(mixed, points) == start
            reference = reference_plan(start, words_by_point, pure_actions, reps)
            periodic, _, misses = periodic_plan(start, 27, words_by_point,
                                                pure_actions, reps)
            assert periodic is not None and not misses
            expected = {"canonical_score": score(reference),
                        "firstword_score": score(periodic if periodic[0] in selected
                                                 else reference),
                        "mixed_score": cost(mixed),
                        "tail_pure_score": pure_costs[index(*state)] if state != (0, 0) else 0,
                        "tail_mixed_score": distances[index(*state)] if state != (0, 0) else 0,
                        "high_pairs": len(high),
                        "mixed_pairs": sum(kind == KIND_PAIR for kind, _ in mixed),
                        "mixed_tau_steps": sum(kind == KIND_TAU for kind, _ in mixed),
                        "mixed_doubles": sum(kind == KIND_DOUBLE for kind, _ in mixed),
                        "mixed_adds": sum(word != ZERO for _, word in mixed)}
            for key, wanted in expected.items():
                assert int(row[key]) == wanted, (case["id"], scalar_index, key)
            for key in totals:
                totals[key] += expected[key]
        reference_total = totals["canonical_score"]
        mixed_total = totals["mixed_score"]
        firstword_total = totals["firstword_score"]
        summaries.append({"case_id": case["id"], "count": samples,
                          **totals,
                          "saving_vs_canonical_percent":
                          100 * (reference_total - mixed_total) / reference_total,
                          "saving_vs_firstword_percent":
                          100 * (firstword_total - mixed_total) / firstword_total})
    assert summaries == summary["summaries"]
    print(f"PASS: {len(actions):,} exact states, {edges:,} Bellman edges, "
          f"{len(rows):,} scalar rows, four totals")


if __name__ == "__main__":
    main()
