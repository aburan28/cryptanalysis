#!/usr/bin/env python3
"""Exploratory operation screen for two table-aware Eisenstein representatives."""

import hashlib
import json
from pathlib import Path

from make_residue_atlas import build as build_atlas
from make_tau8_orbits import build_orbits
from run import omega_eigenvalues, representatives
from screen_hot_orbits import ORDERS, uniform_scalar


SAMPLES_PER_LAW = 1000
SEED = 20261301
BLOCKS = (4, 6)


def plan(a, b, blocks, indexes, patterns, orbit_ids, selected):
    """Return (charged additions, atlas steps, fits) for one representative."""
    hot_adds = positional_adds = steps = used = 0
    while a or b:
        ids = []
        for _ in range(2):
            pattern = indexes[81 * (a % 81) + b % 81]
            _, _, correction_a, correction_b = patterns[pattern]
            a -= correction_a
            b -= correction_b
            next_a, next_b = a + 3 * b, -a - 2 * b
            if next_a % 9 or next_b % 9:
                raise AssertionError("nonintegral atlas step")
            a, b = next_a // 9, next_b // 9
            ids.append(pattern)
            steps += 1
        first, second = ids
        positional_adds += (first != 0) + (second != 0)
        if first or second:
            orbit = orbit_ids[217 * first + second]
            if orbit == 65535:
                raise AssertionError("valid scalar reached invalid orbit")
            hot_adds += 1 if orbit in selected else (
                (first != 0) + (second != 0))
        used += 1
    fits = used <= blocks
    return (hot_adds if fits else positional_adds), steps, fits


def main():
    root = Path(__file__).resolve().parent
    screen = json.loads((root / "hot-orbit-screen.json").read_text())
    selected = set(screen["selected_orbit_ids"])
    if len(selected) != 2048:
        raise AssertionError("unexpected hot table")
    indexes, patterns = build_atlas()
    orbit_ids, _, _ = build_orbits()
    laws = [(order, lam) for order in ORDERS
            for lam in omega_eigenvalues(order)]
    rows = []
    for law_index, (order, lam) in enumerate(laws):
        blocks = BLOCKS[0] if order == ORDERS[0] else BLOCKS[1]
        state = SEED + law_index
        baseline_adds = selected_adds = baseline_steps = selected_steps = 0
        second_chosen = baseline_fallbacks = selected_fallbacks = 0
        for _ in range(SAMPLES_PER_LAW):
            state, scalar = uniform_scalar(state, order)
            choices = []
            for position, (l1, a, b) in enumerate(
                    representatives(order, lam, scalar)):
                choices.append((l1, position, a, b))
            choices.sort(key=lambda item: (item[0], item[1]))
            first = plan(choices[0][2], choices[0][3], blocks, indexes,
                         patterns, orbit_ids, selected)
            second = plan(choices[1][2], choices[1][3], blocks, indexes,
                          patterns, orbit_ids, selected)
            choose_second = second[2] and second[0] < first[0]
            chosen = second if choose_second else first
            baseline_adds += first[0]
            selected_adds += chosen[0]
            baseline_steps += first[1]
            selected_steps += first[1] + second[1]
            second_chosen += choose_second
            baseline_fallbacks += not first[2]
            selected_fallbacks += not chosen[2]
        rows.append({
            "law_index": law_index, "subgroup_order": order,
            "omega_eigenvalue": lam, "samples": SAMPLES_PER_LAW,
            "baseline_adds": baseline_adds, "selected_adds": selected_adds,
            "saved_additions": baseline_adds - selected_adds,
            "saved_addition_fraction":
                f"{(baseline_adds-selected_adds)/baseline_adds:.6f}",
            "second_chosen": second_chosen,
            "baseline_out_of_span": baseline_fallbacks,
            "selected_out_of_span": selected_fallbacks,
            "baseline_atlas_steps": baseline_steps,
            "two_recode_atlas_steps": selected_steps,
        })
    report = {
        "schema": 1,
        "status": "exploratory_table_aware_operation_screen",
        "cpu_timing_claim": None,
        "seed_base": SEED,
        "samples_per_law": SAMPLES_PER_LAW,
        "selection_rule": "strictly fewer predicted additions among two shortest L1 representatives",
        "hot_selection_sha256": screen["selected_orbit_ids_sha256"],
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), root / "TABLE_AWARE_HOT.md",
                         root / "run.py", root / "screen_hot_orbits.py",
                         root / "hot-orbit-screen.json",
                         root / "make_residue_atlas.py",
                         root / "make_tau8_orbits.py")},
        "rows": rows,
    }
    (root / "table-aware-screen.json").write_text(json.dumps(
        report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"],
                      "savings": [row["saved_addition_fraction"]
                                  for row in rows]}, sort_keys=True))


if __name__ == "__main__":
    main()
