#!/usr/bin/env python3
"""Screen a budgeted tau-orbit point table using disjoint scalar streams."""

import collections
import hashlib
import json
from pathlib import Path

from make_residue_atlas import build as build_atlas
from make_tau8_orbits import build_orbits
from make_tau8_pairs import make_map
from run import omega_eigenvalues, representatives


BUDGET = 2048
SAMPLES_PER_LAW = 5000
ORDERS = (23729779, 53624256071278747)
TRAIN_SEED = 20261101
SCREEN_SEED = 20261201
MASK = (1 << 64) - 1


def uniform_scalar(state, order):
    """Use stable SplitMix64 draws with rejection for exact uniformity."""
    cutoff = (1 << 64) // order * order
    while True:
        state = (state + 0x9E3779B97F4A7C15) & MASK
        value = state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK
        value ^= value >> 31
        if value < cutoff:
            return state, value % order


def count_blocks(order, eigenvalue, seed, indexes, patterns, orbit_ids, pair_map):
    state = seed
    two_digit = collections.Counter()
    single_digit = zero_digit = 0
    for _ in range(SAMPLES_PER_LAW):
        state, scalar = uniform_scalar(state, order)
        _, a, b = min(representatives(order, eigenvalue, scalar),
                      key=lambda row: row[0])
        while a or b:
            ids = []
            for _ in range(2):
                pattern_id = indexes[81 * (a % 81) + b % 81]
                _, _, correction_a, correction_b = patterns[pattern_id]
                a -= correction_a
                b -= correction_b
                next_a, next_b = a + 3 * b, -a - 2 * b
                if next_a % 9 or next_b % 9:
                    raise AssertionError("nonintegral atlas step")
                a, b = next_a // 9, next_b // 9
                ids.append(pattern_id)
            first, second = ids
            pair = 217 * first + second
            if pair_map[pair] == 65535 or orbit_ids[pair] == 65535:
                raise AssertionError("reduced scalar reached invalid pair")
            if first and second:
                two_digit[orbit_ids[pair]] += 1
            elif first or second:
                single_digit += 1
            else:
                zero_digit += 1
    return two_digit, single_digit, zero_digit


def main():
    root = Path(__file__).resolve().parent
    indexes, patterns = build_atlas()
    orbit_ids, _, representatives_by_id = build_orbits()
    pair_map = make_map()
    if len(representatives_by_id) != 4933:
        raise AssertionError("unexpected orbit map size")
    laws = [(order, eigenvalue) for order in ORDERS
            for eigenvalue in omega_eigenvalues(order)]
    training = collections.Counter()
    screens = []
    for law_index, (order, eigenvalue) in enumerate(laws):
        train, _, _ = count_blocks(order, eigenvalue,
                                   TRAIN_SEED + law_index, indexes, patterns,
                                   orbit_ids, pair_map)
        training.update(train)
        screen, singles, zeros = count_blocks(
            order, eigenvalue, SCREEN_SEED + law_index, indexes, patterns,
            orbit_ids, pair_map)
        screens.append((order, eigenvalue, screen, singles, zeros))
    ranked = sorted(training, key=lambda orbit_id: (-training[orbit_id],
                                                     orbit_id))
    if len(ranked) < BUDGET:
        raise AssertionError("training did not see enough orbit classes")
    selected = ranked[:BUDGET]
    selected_set = set(selected)
    rows = []
    for law_index, (order, eigenvalue, screen, singles, zeros) in enumerate(
            screens):
        total = sum(screen.values())
        covered = sum(count for orbit_id, count in screen.items()
                      if orbit_id in selected_set)
        blocks = 4 if order == ORDERS[0] else 6
        rows.append({"law_index": law_index, "subgroup_order": order,
                     "omega_eigenvalue": eigenvalue,
                     "two_digit_blocks": total, "hot_two_digit_blocks": covered,
                     "hot_coverage": f"{covered / total:.6f}",
                     "single_digit_blocks": singles,
                     "zero_digit_blocks": zeros,
                     "predicted_hot_setup_adds": BUDGET * blocks,
                     "full_orbit_setup_adds": 4860 * blocks,
                     "predicted_hot_affine_bytes": BUDGET * blocks * 32,
                     "full_orbit_affine_bytes": 4933 * blocks * 32})
    selected_json = json.dumps(selected, separators=(",", ":")).encode()
    sources = (Path(__file__), root / "HOT_ORBIT_TABLE.md", root / "run.py",
               root / "make_residue_atlas.py", root / "make_tau8_pairs.py",
               root / "make_tau8_orbits.py")
    report = {"schema": 1, "status": "exploratory_hot_orbit_screen",
              "cpu_timing_claim": None, "candidate_budget": BUDGET,
              "training_samples_per_law": SAMPLES_PER_LAW,
              "training_seed_base": TRAIN_SEED,
              "screen_seed_base": SCREEN_SEED,
              "input_law": "uniform subgroup scalar; shortest L1 tau representative",
              "selection_rule": "most frequent two-digit orbit; smaller orbit ID breaks ties",
              "selected_orbit_ids": selected,
              "selected_orbit_ids_sha256": hashlib.sha256(
                  selected_json).hexdigest(),
              "source_sha256": {path.name: hashlib.sha256(
                  path.read_bytes()).hexdigest() for path in sources},
              "rows": rows}
    output = root / "hot-orbit-screen.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"],
                      "selected_orbit_ids_sha256": report[
                          "selected_orbit_ids_sha256"],
                      "coverage": [row["hot_coverage"] for row in rows]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
