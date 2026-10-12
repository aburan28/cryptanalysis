#!/usr/bin/env python3
"""Screen demand-gated second recoding on scalar streams disjoint from evaluation."""

import hashlib
import json
from pathlib import Path

from make_residue_atlas import build as build_atlas
from make_tau8_orbits import build_orbits
from run import omega_eigenvalues, representatives
from screen_hot_orbits import ORDERS, uniform_scalar


SAMPLES_PER_LAW = 5000
SEED = 20270201


def score(a, b, blocks, indexes, patterns, orbit_ids, hot):
    adds = positional_adds = steps = used = cold_two_digit = 0
    while a or b:
        pair = []
        for _ in range(2):
            pattern = indexes[81 * (a % 81) + b % 81]
            _, _, correction_a, correction_b = patterns[pattern]
            a -= correction_a
            b -= correction_b
            next_a, next_b = a + 3 * b, -a - 2 * b
            if next_a % 9 or next_b % 9:
                raise AssertionError("nonintegral atlas step")
            a, b = next_a // 9, next_b // 9
            pair.append(pattern)
            steps += 1
        first, second = pair
        positional_adds += (first != 0) + (second != 0)
        if first or second:
            orbit = orbit_ids[217 * first + second]
            if orbit == 65535:
                raise AssertionError("valid scalar reached invalid orbit")
            if orbit in hot:
                adds += 1
            else:
                adds += (first != 0) + (second != 0)
                cold_two_digit += first != 0 and second != 0
        used += 1
    fits = used <= blocks
    return (adds if fits else positional_adds), steps, fits, cold_two_digit


def main():
    root = Path(__file__).resolve().parent
    hot_screen = json.loads((root / "hot-orbit-screen.json").read_text())
    hot = set(hot_screen["selected_orbit_ids"])
    if len(hot) != 2048:
        raise AssertionError("unexpected hot table")
    indexes, patterns = build_atlas()
    orbit_ids, _, _ = build_orbits()
    laws = [(order, lam) for order in ORDERS
            for lam in omega_eigenvalues(order)]
    rows = []
    for law_index, (order, lam) in enumerate(laws):
        blocks = 4 if order == ORDERS[0] else 6
        state = SEED + law_index
        baseline_adds = full_adds = gated_adds = 0
        gated_second_recodes = full_second_chosen = gated_second_chosen = 0
        baseline_steps = full_steps = gated_steps = 0
        for _ in range(SAMPLES_PER_LAW):
            state, scalar = uniform_scalar(state, order)
            choices = sorted(enumerate(representatives(order, lam, scalar)),
                             key=lambda row: (row[1][0], row[0]))
            first = score(choices[0][1][1], choices[0][1][2], blocks,
                          indexes, patterns, orbit_ids, hot)
            second = score(choices[1][1][1], choices[1][1][2], blocks,
                           indexes, patterns, orbit_ids, hot)
            choose_second = second[2] and second[0] < first[0]
            trigger = not first[2] or first[3] > 0
            baseline_adds += first[0]
            full_adds += second[0] if choose_second else first[0]
            gated_adds += second[0] if trigger and choose_second else first[0]
            baseline_steps += first[1]
            full_steps += first[1] + second[1]
            gated_steps += first[1] + (second[1] if trigger else 0)
            gated_second_recodes += trigger
            full_second_chosen += choose_second
            gated_second_chosen += trigger and choose_second
        full_saving = baseline_adds - full_adds
        gated_saving = baseline_adds - gated_adds
        rows.append({
            "law_index": law_index, "subgroup_order": order,
            "omega_eigenvalue": lam, "samples": SAMPLES_PER_LAW,
            "baseline_adds": baseline_adds, "full_selector_adds": full_adds,
            "gated_selector_adds": gated_adds,
            "full_saved_adds": full_saving,
            "gated_saved_adds": gated_saving,
            "saving_retained": f"{gated_saving / full_saving:.6f}",
            "gated_second_recodes": gated_second_recodes,
            "second_recode_fraction":
                f"{gated_second_recodes / SAMPLES_PER_LAW:.6f}",
            "full_second_chosen": full_second_chosen,
            "gated_second_chosen": gated_second_chosen,
            "baseline_atlas_steps": baseline_steps,
            "full_selector_atlas_steps": full_steps,
            "gated_selector_atlas_steps": gated_steps,
        })
    paths = (Path(__file__), root / "GATED_TABLE_AWARE.md",
             root / "run.py", root / "screen_hot_orbits.py",
             root / "hot-orbit-screen.json",
             root / "make_residue_atlas.py", root / "make_tau8_orbits.py")
    report = {
        "schema": 1,
        "status": "exploratory_gated_selector_operation_screen",
        "cpu_timing_claim": None,
        "seed_base": SEED,
        "samples_per_law": SAMPLES_PER_LAW,
        "hot_selection_sha256": hot_screen["selected_orbit_ids_sha256"],
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths},
        "rows": rows,
    }
    (root / "gated-table-aware-screen.json").write_text(json.dumps(
        report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": report["status"],
        "saving_retained": [row["saving_retained"] for row in rows],
        "second_recode_fraction": [row["second_recode_fraction"]
                                   for row in rows],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
