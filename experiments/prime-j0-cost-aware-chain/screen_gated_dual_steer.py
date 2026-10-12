#!/usr/bin/env python3
"""Exploratory operation screen for a gated second carry-steered recode."""

import hashlib
import json
from pathlib import Path

from make_residue_atlas import build as build_atlas
from make_tau8_orbits import build_orbits
from make_tau8_pairs import make_map
from make_tau8_steer import ABSENT, build_map, correction
from run import omega_eigenvalues, representatives
from screen_carry_steer import canonical_step, steered
from screen_hot_orbits import ORDERS, uniform_scalar


SEED = 20270501
SAMPLES_PER_LAW = 5000


def requires_second(a, b, blocks, selected, indexes, patterns,
                    pair_map, orbit_ids, hot):
    for _ in range(blocks):
        if a == b == 0:
            return False
        cost, x, y, _ = canonical_step(a, b, indexes, patterns,
                                       pair_map, orbit_ids, hot)
        if cost == 2:
            alternative = selected[81 * (a % 81) + b % 81]
            if alternative == ABSENT:
                return True
            ca, cb = correction(patterns, *divmod(alternative, 217))
            da, db = a - ca, b - cb
            x, y = (-2 * da - 3 * db) // 81, (da + db) // 81
        a, b = x, y
    return bool(a or b)


def main():
    root = Path(__file__).resolve().parent
    screen_path = root / "hot-orbit-screen.json"
    hot_screen = json.loads(screen_path.read_text())
    hot = set(hot_screen["selected_orbit_ids"])
    selected = build_map(screen_path)
    indexes, patterns = build_atlas()
    pair_map = make_map()
    orbit_ids, _, _ = build_orbits()
    rows = []
    for law_index, (order, lam) in enumerate(
            (order, lam) for order in ORDERS for lam in omega_eigenvalues(order)):
        blocks = 4 if order == ORDERS[0] else 6
        state = SEED + law_index
        first_adds = full_adds = gated_adds = 0
        gated_recodes = full_second_selected = gated_second_selected = 0
        for _ in range(SAMPLES_PER_LAW):
            state, scalar = uniform_scalar(state, order)
            choices = sorted(enumerate(representatives(order, lam, scalar)),
                             key=lambda row: (row[1][0], row[0]))
            _, a, b = choices[0][1]
            _, second_a, second_b = choices[1][1]
            first = steered(a, b, blocks, selected, indexes, patterns,
                            pair_map, orbit_ids, hot)
            second = steered(second_a, second_b, blocks, selected, indexes,
                             patterns, pair_map, orbit_ids, hot)
            trigger = requires_second(a, b, blocks, selected, indexes,
                                      patterns, pair_map, orbit_ids, hot)
            choose_second = second[1] and (not first[1] or second[0] < first[0])
            first_adds += first[0]
            full_adds += second[0] if choose_second else first[0]
            gated_adds += second[0] if trigger and choose_second else first[0]
            gated_recodes += trigger
            full_second_selected += choose_second
            gated_second_selected += trigger and choose_second
        if not full_adds <= gated_adds <= first_adds:
            raise AssertionError("selector ordering failed")
        rows.append({"law_index": law_index, "subgroup_order": order,
                     "omega_eigenvalue": lam, "samples": SAMPLES_PER_LAW,
                     "first_adds": first_adds, "always_two_adds": full_adds,
                     "gated_adds": gated_adds,
                     "gated_saved_fraction": f"{(first_adds-gated_adds)/first_adds:.6f}",
                     "saving_retained":
                         f"{(first_adds-gated_adds)/(first_adds-full_adds):.6f}",
                     "gated_second_recodes": gated_recodes,
                     "second_recode_fraction":
                         f"{gated_recodes/SAMPLES_PER_LAW:.6f}",
                     "always_two_selected": full_second_selected,
                     "gated_second_selected": gated_second_selected})
    paths = (Path(__file__), root / "GATED_DUAL_STEER.md",
             root / "CARRY_STEERED_TAU8.md", root / "make_tau8_steer.py",
             root / "screen_carry_steer.py", root / "run.py",
             root / "screen_hot_orbits.py", screen_path,
             root / "make_residue_atlas.py", root / "make_tau8_pairs.py",
             root / "make_tau8_orbits.py")
    report = {"schema": 1, "status": "exploratory_gated_dual_steer_operations",
              "cpu_timing_claim": None, "seed_base": SEED,
              "samples_per_law": SAMPLES_PER_LAW,
              "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in paths}, "rows": rows}
    (root / "gated-dual-steer-screen.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"],
                      "saved": [row["gated_saved_fraction"] for row in rows],
                      "second_fraction": [row["second_recode_fraction"]
                                          for row in rows]}, sort_keys=True))


if __name__ == "__main__":
    main()
