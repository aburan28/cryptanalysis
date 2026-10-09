#!/usr/bin/env python3
"""Retrospective small-rule screen for zero-digit 2/tau exits."""

import hashlib
import json
from math import isqrt
from pathlib import Path

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS, norm
from mixed_radix_scalar import reconstruct, source_cost


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixture.json"  # Already-inspected design data.
MAX_ACTIONS = 512


def choose_double(a, b, table, policy):
    assert a % 2 == b % 2 == 0
    if policy == "greedy":
        return True
    if policy == "skip_zero_tau":
        return a % 3 != 0
    if policy == "skip_zero_or_mixed_tau":
        return a % 3 != 0 and table[a % 9, b % 9][1] != 0
    if policy == "skip_zero_or_low_tau":
        return a % 3 != 0 and table[a % 9, b % 9][1] not in (0, 1, 2)
    if policy == "double_only_v2ge2":
        return a % 4 == b % 4 == 0
    if policy == "double_only_v2ge2_nonzero_tau":
        return a % 4 == b % 4 == 0 and a % 3 != 0
    if policy == "double_only_a1_mod3":
        return a % 3 == 1
    if policy == "double_only_a2_mod3":
        return a % 3 == 2
    raise ValueError(policy)


def recode(short, table, policy):
    a, b = short
    seen = set()
    actions = []
    while a or b:
        if (a, b) in seen:
            return None, "cycle"
        if len(actions) >= MAX_ACTIONS:
            return None, "limit"
        seen.add((a, b))
        if a % 2 == b % 2 == 0 and choose_double(a, b, table, policy):
            actions.append(("two", None, None))
            a, b = a // 2, b // 2
        else:
            if a % 3:
                digit, seed = table[a % 9, b % 9]
                da, db = digit
            else:
                digit, seed, da, db = None, None, 0, 0
            x, y = a - da, b - db
            assert x % 3 == 0
            actions.append(("tau", digit, seed))
            a, b = x + y, -x // 3
    assert actions and actions[-1][1] is not None
    assert reconstruct(actions) == short
    return actions, "verified"


def termination_audit(table, policy):
    max_digit_norm = max(norm(digit) for digit, _ in table.values())
    radius = 2 * max_digit_norm
    bound = 3 * isqrt(radius) + 4
    states = {(a, b) for a in range(-bound, bound + 1)
              for b in range(-bound, bound + 1)
              if norm((a, b)) <= radius}
    terminating = {(0, 0)}
    for start in sorted(states):
        a, b = start
        seen = set()
        while (a, b) not in terminating:
            if (a, b) not in states:
                return {"status": "escaped_closed_ball", "state": [a, b]}
            if (a, b) in seen:
                return {"status": "cycle", "state": [a, b]}
            seen.add((a, b))
            if a % 2 == b % 2 == 0 and choose_double(a, b, table, policy):
                a, b = a // 2, b // 2
            else:
                da, db = table[a % 9, b % 9][0] if a % 3 else (0, 0)
                x, y = a - da, b - db
                assert x % 3 == 0
                a, b = x + y, -x // 3
        terminating.update(seen)
    assert len(terminating) == len(states)
    return {"status": "terminates", "radius": radius,
            "small_states": len(states), "max_digit_norm": max_digit_norm}


def main():
    fixture_bytes = FIXTURE.read_bytes()
    fixture = json.loads(fixture_bytes)
    previous = json.loads((HERE / "mixed-radix-scalar-result.json").read_bytes())
    old = previous["panels"][0]["rows"]
    assert len(fixture["cases"]) == len(old) == 64
    table = digit_table(SEEDS[0])
    policies = (
        "greedy", "skip_zero_tau", "skip_zero_or_mixed_tau",
        "skip_zero_or_low_tau", "double_only_v2ge2",
        "double_only_v2ge2_nonzero_tau", "double_only_a1_mod3",
        "double_only_a2_mod3",
    )
    panels = []
    for policy in policies:
        audit = termination_audit(table, policy)
        rows = []
        for case, reference in zip(fixture["cases"], old):
            assert case["index"] == reference["index"]
            short = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
            actions, status = recode(short, table, policy)
            cost = None if actions is None else source_cost(actions)
            chosen = min(reference["selected_M_plus_S"], cost["total_M_plus_S"]) if cost else reference["selected_M_plus_S"]
            rows.append({"index": case["index"], "status": status,
                         "policy_M_plus_S": cost["total_M_plus_S"] if cost else None,
                         "selected_M_plus_S": chosen,
                         "saving_M_plus_S": reference["selected_M_plus_S"] - chosen,
                         "doubles": cost["doubles"] if cost else None,
                         "tau_pairs": cost["tau_pairs"] if cost else None})
        panels.append({"policy": policy,
                       "termination": audit,
                       "source_total": sum(row["policy_M_plus_S"] for row in rows
                                           if row["policy_M_plus_S"] is not None),
                       "selected_total": sum(row["selected_M_plus_S"] for row in rows),
                       "wins": sum(row["saving_M_plus_S"] > 0 for row in rows),
                       "failures": sum(row["status"] != "verified" for row in rows),
                       "rows": rows})
    result = {"scope": "retrospective_design_only", "cases": 64,
              "previous_selector_total": sum(row["selected_M_plus_S"] for row in old),
              "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "panels": panels, "cpu_speedup_claim": None,
              "academic_novelty_claim": None}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
