#!/usr/bin/env python3
"""Screen a minimum-norm tau^6 atlas and an 18-orbit sparse overlay."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from check_eisenstein_scalar_fixed import LAMBDA_TAU
import lazy_tau_screen as curve
import redundant_tau4_screen as w4


HERE = Path(__file__).resolve().parent
RADIUS = 35


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_orbit(seed):
    return frozenset(w4.orbit(seed))


def build_width_six_table():
    # tau^6 = -27, so coefficient residues modulo 27 classify the ideal.
    nearest = {}
    for a in range(-RADIUS, RADIUS + 1):
        for b in range(-RADIUS, RADIUS + 1):
            if a % 3 == 0:
                continue
            key = (a % 27, b % 27)
            candidate = (w4.norm((a, b)), a, b)
            if key not in nearest or candidate < nearest[key]:
                nearest[key] = candidate
    assert len(nearest) == 486
    max_norm = max(item[0] for item in nearest.values())
    # N(a,b) >= a^2/4 and >= 3b^2/4. Every possibly better digit is
    # inside the enumerated square; the selected representatives are global.
    assert max_norm == 217 and 4 * max_norm < RADIUS * RADIUS
    remaining = set(nearest)
    table = {}
    seeds = []
    while remaining:
        first = min(remaining)
        point = nearest[first][1:]
        classes = {(d[0] % 27, d[1] % 27) for d in w4.orbit(point)}
        assert len(classes) == 6 and classes <= remaining
        _, a, b = min(nearest[key] for key in classes)
        seed = (a, b)
        orbit_id = len(seeds)
        seeds.append(seed)
        for digit in w4.orbit(seed):
            key = (digit[0] % 27, digit[1] % 27)
            assert key in remaining and w4.norm(digit) == nearest[key][0]
            table[key] = (digit, orbit_id)
            remaining.remove(key)
    assert len(seeds) == 81 and len(table) == 486
    return table, seeds, max_norm


def quotient_six(z, digit):
    a, b = z[0] - digit[0], z[1] - digit[1]
    assert a % 27 == 0 and b % 27 == 0
    result = (-a // 27, -b // 27)
    assert w4.norm(result) < w4.norm(z), (z, digit, result)
    return result


def recode(start, mode, table, sparse, policy_four):
    assert mode in ("width_six", "sparse_eighteen")
    terminal = ({(0, 0)} | {digit for digit, _ in table.values()}
                if mode == "width_six" else policy_four.terminal)
    z = start
    actions = []
    steps = additions = six_blocks = alternate_uses = 0
    while z not in terminal:
        if z[0] % 3 == 0:
            actions.append((1, (0, 0)))
            z = w4.zero_quotient(z)
            steps += 1
        else:
            key = (z[0] % 27, z[1] % 27)
            chosen = table[key][0] if mode == "width_six" else sparse.get(key)
            if chosen is not None:
                actions.append((6, chosen))
                z = quotient_six(z, chosen)
                steps += 6
                six_blocks += 1
            else:
                choices = policy_four.table[(z[0] % 9, z[1] % 9)]
                quotients = [w4.block_quotient(z, d) for d in choices]
                values = [policy_four.look_value(q, 1) for q in quotients]
                index = int(values[1] < values[0])
                actions.append((4, choices[index]))
                z = quotients[index]
                steps += 4
                alternate_uses += index
            additions += 1
        assert steps <= 512
    rebuilt = z
    for width, digit in reversed(actions):
        if width == 1:
            rebuilt = w4.tau(rebuilt)
        elif width == 4:
            rebuilt = (9 * (-2 * rebuilt[0] - 3 * rebuilt[1]) + digit[0],
                       9 * (rebuilt[0] + rebuilt[1]) + digit[1])
        else:
            rebuilt = (-27 * rebuilt[0] + digit[0],
                       -27 * rebuilt[1] + digit[1])
    assert rebuilt == start
    return {"tau_steps": steps, "additions": additions,
            "six_blocks": six_blocks, "alternate_uses": alternate_uses,
            "field_product_proxy": 5 * steps + 11 * additions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=HERE / "redundant-tau4-result.json")
    parser.add_argument("--output", type=Path,
                        default=HERE / "width6-tau-result.json")
    args = parser.parse_args()
    source_path = args.input.resolve(strict=True)
    source = json.loads(source_path.read_text())
    assert source["schema"] == 1 and source["status"] == "passed"
    assert len(source["cases"]) == 214
    table, seeds, max_norm = build_width_six_table()
    four_table = w4.digit_table()
    policy_four = w4.Policy(four_table, dual_terminal=True)
    dual_digits = {digit for pair in four_table.values() for digit in pair}
    sparse = {}
    for digit in dual_digits:
        key = (digit[0] % 27, digit[1] % 27)
        assert table[key][0] == digit
        sparse[key] = digit
    sparse_orbits = sorted({table[key][1] for key in sparse})
    assert len(sparse) == 108 and len(sparse_orbits) == 18
    panels = ("frozen_edges", "frozen_random", "holdout_random")
    methods = ("tau4_rollout_2", "width_six", "sparse_eighteen")
    totals = {panel: {method: 0 for method in methods} for panel in panels}
    wins = {panel: {method: Counter() for method in methods[1:]}
            for panel in panels}
    cases = []
    for row in source["cases"]:
        scalar = int(row["scalar_hex"], 16)
        representative = tuple(row["representative"])
        assert (representative[0] + representative[1] * LAMBDA_TAU
                - scalar) % curve.ORDER == 0
        baseline = row["policies"]["rollout_2"]["field_product_proxy"]
        results = {method: recode(representative, method, table, sparse, policy_four)
                   for method in methods[1:]}
        panel = row["panel"]
        totals[panel]["tau4_rollout_2"] += baseline
        for method, result in results.items():
            cost = result["field_product_proxy"]
            totals[panel][method] += cost
            wins[panel][method]["win" if cost < baseline else
                                "tie" if cost == baseline else "loss"] += 1
        cases.append({"index": row["index"], "panel": panel,
                      "scalar_hex": row["scalar_hex"],
                      "representative": list(representative),
                      "tau4_rollout_2": baseline, "methods": results})
    assert all(totals[panel]["tau4_rollout_2"] ==
               source["totals"][panel]["rollout_2"] for panel in panels)
    output = {"schema": 1, "status": "passed", "curve": "secp256k1",
              "base": "standard-generator", "algorithm": "minimum-norm-tau6-atlas",
              "digit_classes": len(table), "seed_orbits": len(seeds),
              "max_digit_norm": max_norm, "enumeration_radius": RADIUS,
              "width_six_seeds": seeds, "sparse_orbit_ids": sparse_orbits,
              "totals": totals,
              "comparisons": {panel: {method: dict(counts)
                                      for method, counts in values.items()}
                              for panel, values in wins.items()},
              "cases": cases,
              "input_sha256": sha(source_path),
              "source_sha256": sha(Path(__file__))}
    if args.output.exists():
        raise SystemExit("result exists; refusing overwrite")
    args.output.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": output["status"], "cases": len(cases),
                      "totals": totals, "comparisons": output["comparisons"],
                      "result_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
