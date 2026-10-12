#!/usr/bin/env python3
"""Exploratory operation screen for carry-steered eight-step tau blocks."""

import hashlib
import json
from pathlib import Path

from make_residue_atlas import build as build_atlas
from make_tau8_orbits import build_orbits
from make_tau8_pairs import make_map
from make_tau8_steer import ABSENT, MODULUS, build_map, correction
from run import omega_eigenvalues, representatives
from screen_hot_orbits import ORDERS, uniform_scalar
from screen_table_aware import plan


SAMPLES_PER_LAW = 5000
SEED = 20270301


def canonical_step(a, b, indexes, patterns, pair_map, orbit_ids, hot):
    x, y = a, b
    ids = []
    for _ in range(2):
        pattern = indexes[81 * (x % 81) + y % 81]
        _, _, ca, cb = patterns[pattern]
        x -= ca
        y -= cb
        nx, ny = x + 3 * y, -x - 2 * y
        if nx % 9 or ny % 9:
            raise AssertionError("nonintegral canonical step")
        x, y = nx // 9, ny // 9
        ids.append(pattern)
    u, v = ids
    pair = 217 * u + v
    if pair_map[pair] == ABSENT:
        raise AssertionError("canonical pair invalid")
    cost = 0 if u == v == 0 else (
        1 if u == 0 or v == 0 or orbit_ids[pair] in hot else 2)
    return cost, x, y, pair


def positional_adds(a, b, indexes, patterns, pair_map, orbit_ids, hot):
    adds = 0
    while a or b:
        _, a, b, pair = canonical_step(
            a, b, indexes, patterns, pair_map, orbit_ids, hot)
        u, v = divmod(pair, 217)
        adds += (u != 0) + (v != 0)
    return adds


def steered(a, b, blocks, selected, indexes, patterns, pair_map,
            orbit_ids, hot):
    original = a, b
    adds = substitutions = 0
    for _ in range(blocks):
        if a == b == 0:
            return adds, True, substitutions
        old_a, old_b = a, b
        cost, x, y, canonical_pair = canonical_step(
            a, b, indexes, patterns, pair_map, orbit_ids, hot)
        if cost == 2:
            key = MODULUS * (a % MODULUS) + b % MODULUS
            alternative = selected[key]
            if alternative != ABSENT:
                u, v = divmod(alternative, 217)
                ca, cb = correction(patterns, u, v)
                da, db = a - ca, b - cb
                if da % 81 or db % 81:
                    raise AssertionError("steer map changed residue")
                x, y = (-2 * da - 3 * db) // 81, (da + db) // 81
                if (old_a != ca + 81 * (x + 3 * y) or
                        old_b != cb + 81 * (-x - 2 * y)):
                    raise AssertionError("tau-eight carry identity failed")
                cost = 0 if u == v == 0 else (
                    1 if u == 0 or v == 0 or orbit_ids[alternative] in hot
                    else 2)
                if cost >= 2:
                    raise AssertionError("selected pair did not save one add")
                substitutions += 1
        adds += cost
        a, b = x, y
    if a or b:
        return positional_adds(*original, indexes, patterns,
                               pair_map, orbit_ids, hot), False, substitutions
    return adds, True, substitutions


def main():
    root = Path(__file__).resolve().parent
    screen_path = root / "hot-orbit-screen.json"
    hot_screen = json.loads(screen_path.read_text())
    hot = set(hot_screen["selected_orbit_ids"])
    selected = build_map(screen_path)
    indexes, patterns = build_atlas()
    pair_map = make_map()
    orbit_ids, _, _ = build_orbits()
    laws = [(order, lam) for order in ORDERS
            for lam in omega_eigenvalues(order)]
    rows = []
    for law_index, (order, lam) in enumerate(laws):
        blocks = 4 if order == ORDERS[0] else 6
        state = SEED + law_index
        baseline_adds = steered_adds = baseline_fallbacks = steered_fallbacks = 0
        better = worse = equal = substitutions = 0
        for _ in range(SAMPLES_PER_LAW):
            state, scalar = uniform_scalar(state, order)
            _, a, b = min(representatives(order, lam, scalar),
                          key=lambda row: row[0])
            baseline = plan(a, b, blocks, indexes, patterns, orbit_ids, hot)
            candidate = steered(a, b, blocks, selected, indexes, patterns,
                                pair_map, orbit_ids, hot)
            baseline_adds += baseline[0]
            steered_adds += candidate[0]
            baseline_fallbacks += not baseline[2]
            steered_fallbacks += not candidate[1]
            substitutions += candidate[2]
            better += candidate[0] < baseline[0]
            worse += candidate[0] > baseline[0]
            equal += candidate[0] == baseline[0]
        rows.append({
            "law_index": law_index, "subgroup_order": order,
            "omega_eigenvalue": lam, "samples": SAMPLES_PER_LAW,
            "baseline_adds": baseline_adds, "steered_adds": steered_adds,
            "saved_additions": baseline_adds - steered_adds,
            "saved_addition_fraction":
                f"{(baseline_adds-steered_adds)/baseline_adds:.6f}",
            "baseline_span_fallbacks": baseline_fallbacks,
            "steered_span_fallbacks": steered_fallbacks,
            "substituted_blocks": substitutions,
            "better_scalars": better, "worse_scalars": worse,
            "equal_scalars": equal,
        })
    paths = (Path(__file__), root / "CARRY_STEERED_TAU8.md",
             root / "make_tau8_steer.py", root / "run.py",
             root / "screen_hot_orbits.py", screen_path,
             root / "screen_table_aware.py",
             root / "make_residue_atlas.py",
             root / "make_tau8_pairs.py",
             root / "make_tau8_orbits.py")
    report = {
        "schema": 1,
        "status": "exploratory_carry_steer_operation_screen",
        "cpu_timing_claim": None,
        "seed_base": SEED,
        "samples_per_law": SAMPLES_PER_LAW,
        "static_map_bytes": 6561 * 2,
        "hot_selection_sha256": hot_screen["selected_orbit_ids_sha256"],
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths},
        "rows": rows,
    }
    (root / "carry-steer-screen.json").write_text(json.dumps(
        report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": report["status"],
        "savings": [row["saved_addition_fraction"] for row in rows],
        "span_fallbacks": [row["steered_span_fallbacks"] for row in rows],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
