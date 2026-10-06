#!/usr/bin/env python3
"""Explore complete residue-orbit windows with a narrow exact tail."""

import hashlib
import json
from pathlib import Path

from make_residue_atlas import build as build_atlas
from make_tau8_orbits import build_orbits, unit_action
from make_tau8_pairs import make_map
from make_tau8_steer import build_map
from make_tau_wide_orbits import ID_BITS, MAX_ID, build, residue_key
from run import omega_eigenvalues, point_add, point_mul, representatives, toy_instance
from screen_carry_steer import positional_adds, steered
from screen_gated_dual_steer import requires_second
from screen_hot_orbits import ORDERS, uniform_scalar


SEED = 20271001
SAMPLES = 2000
SCHEDULE_32 = (10, 10, 10, 10)
SCHEDULE_56 = (12, 12, 12, 8, 8)


def plan(a, b, schedule, atlases, fallback_adds=None):
    original = a, b
    adds = rotations = 0
    terms = []
    offset = 0
    for width in schedule:
        if a == b == 0:
            return adds, rotations, True, terms
        atlas = atlases[width]
        modulus = atlas["modulus"]
        packed = atlas["packed"][residue_key(a, b, modulus)]
        orbit_id = packed & (MAX_ID - 1)
        code = packed >> ID_BITS
        ca, cb = unit_action(*atlas["corrections"][orbit_id], code)
        da, db = a - ca, b - cb
        if da % modulus or db % modulus:
            raise AssertionError("correction changed residue")
        s = width // 2
        inverse_code = (-s % 3) + (3 if s % 2 else 0)
        next_a, next_b = unit_action(da // modulus, db // modulus, inverse_code)
        forward_code = (s % 3) + (3 if s % 2 else 0)
        forward_a, forward_b = unit_action(next_a, next_b, forward_code)
        if (a, b) != (ca + modulus * forward_a,
                      cb + modulus * forward_b):
            raise AssertionError("tau-width carry identity failed")
        terms.append((offset, ca, cb))
        adds += orbit_id != 0
        rotations += code % 3 != 0 and orbit_id != 0
        a, b = next_a, next_b
        offset += width
    if a or b:
        if fallback_adds is None:
            return None, rotations, False, terms
        return fallback_adds, rotations, False, terms
    if sum(1 for _, ca, cb in terms if ca or cb) != adds:
        raise AssertionError("one-addition block model disagreed")
    if original != (0, 0) and not terms:
        raise AssertionError("nonzero representative had no terms")
    return adds, rotations, True, terms


def toy_point_checks(atlases):
    checks = 0
    for curve_b, order in ((2, 13), (10, 103)):
        modulus, _, point, _, omega_lambda, _ = toy_instance(curve_b, order)
        tau_lambda = (1 - omega_lambda) % order
        for schedule in (SCHEDULE_32, SCHEDULE_56):
            for scalar in range(order):
                _, a, b = min(representatives(order, omega_lambda, scalar),
                              key=lambda row: row[0])
                _, _, fits, terms = plan(a, b, schedule, atlases)
                if not fits:
                    continue
                got = None
                for offset, ca, cb in terms:
                    coefficient = ((ca + cb * tau_lambda) *
                                   pow(tau_lambda, offset, order)) % order
                    got = point_add(got, point_mul(point, coefficient,
                                                   modulus, curve_b), modulus, curve_b)
                if got != point_mul(point, scalar, modulus, curve_b):
                    raise AssertionError("toy point replay failed")
                checks += 1
    return checks


def main():
    root = Path(__file__).resolve().parent
    atlases = {width: build(width) for width in (8, 10, 12)}
    orbit_counts = {str(width): len(atlas["reps"])
                    for width, atlas in atlases.items()}
    toy_checks = toy_point_checks(atlases)
    indexes, patterns = build_atlas()
    valid = make_map()
    orbit_ids, _, _ = build_orbits()
    hot_screen = root / "hot-orbit-screen.json"
    hot = set(json.loads(hot_screen.read_text())["selected_orbit_ids"])
    selected_hot = build_map(hot_screen)
    rows = []
    for law_index, (order, omega_lambda) in enumerate((o, lam) for o in ORDERS
                                                      for lam in omega_eigenvalues(o)):
        state = SEED + law_index
        blocks = 4 if order == ORDERS[0] else 6
        schedule = SCHEDULE_32 if order == ORDERS[0] else SCHEDULE_56
        old_adds = new_adds = rotations = fallbacks = 0
        better = worse = equal = 0
        for _ in range(SAMPLES):
            state, scalar = uniform_scalar(state, order)
            choices = sorted(enumerate(representatives(order, omega_lambda, scalar)),
                             key=lambda row: (row[1][0], row[0]))
            _, a, b = choices[0][1]
            old = steered(a, b, blocks, selected_hot, indexes, patterns,
                          valid, orbit_ids, hot)
            if requires_second(a, b, blocks, selected_hot, indexes,
                               patterns, valid, orbit_ids, hot):
                _, a2, b2 = choices[1][1]
                second = steered(a2, b2, blocks, selected_hot, indexes,
                                 patterns, valid, orbit_ids, hot)
                if second[1] and (not old[1] or second[0] < old[0]):
                    old = second
            positional = positional_adds(a, b, indexes, patterns,
                                         valid, orbit_ids, hot)
            additions, unit_rotations, fits, _ = plan(
                a, b, schedule, atlases, positional)
            old_adds += old[0]
            new_adds += additions
            rotations += unit_rotations
            fallbacks += not fits
            better += additions < old[0]
            worse += additions > old[0]
            equal += additions == old[0]
        entries = sum(len(atlases[width]["reps"]) for width in schedule)
        map_bytes = sum((atlases[width]["modulus"] ** 2 * 4 +
                         len(atlases[width]["reps"]) * 4)
                        for width in set(schedule))
        rows.append({"law_index": law_index, "subgroup_order": order,
                     "omega_eigenvalue": omega_lambda, "samples": SAMPLES,
                     "schedule": schedule, "old_adds": old_adds,
                     "candidate_adds": new_adds,
                     "saved_fraction": f"{(old_adds-new_adds)/old_adds:.6f}",
                     "candidate_rotations": rotations,
                     "candidate_fallbacks": fallbacks,
                     "better": better, "worse": worse, "equal": equal,
                     "point_entries": entries,
                     "point_table_bytes_at_32_bytes_per_point": entries * 32,
                     "used_static_index_and_correction_bytes": map_bytes})
    paths = (Path(__file__), root / "TAPERED_RESIDUE_ORBITS.md",
             root / "make_tau_wide_orbits.py", root / "run.py",
             root / "make_tau8_orbits.py", root / "make_tau8_pairs.py",
             root / "make_residue_atlas.py", root / "screen_carry_steer.py",
             root / "screen_gated_dual_steer.py", root / "make_tau8_steer.py",
             root / "screen_hot_orbits.py", hot_screen)
    report = {"schema": 1, "status": "exploratory_tapered_residue_operations",
              "cpu_timing_claim": None, "seed_base": SEED,
              "samples_per_law": SAMPLES, "orbit_counts": orbit_counts,
              "toy_point_checks": toy_checks,
              "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in paths},
              "rows": rows}
    (root / "tapered-residue-screen.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "toy_point_checks": toy_checks,
                      "savings": [row["saved_fraction"] for row in rows],
                      "fallbacks": [row["candidate_fallbacks"] for row in rows]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
