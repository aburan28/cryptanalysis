#!/usr/bin/env python3
"""Search alternative width-four tau digit orbits on frozen design data.

One nonbase seed orbit changes at a time.  Termination is proved for all
integer coefficient states by an exhaustive closed small-norm graph plus
strict norm descent outside it.  No point arithmetic or timing occurs.
"""

import hashlib
import json
from math import isqrt
from pathlib import Path

from seed_chain_bound import SEEDS, norm, orbit, tau


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixture.json"
MAX_CANDIDATE_NORM = 400
BASE_SEEDS = list(SEEDS.values())


def residue_signature(seed):
    return tuple(sorted((a % 9, b % 9) for a, b in orbit(seed)))


def catalog():
    old_signatures = [residue_signature(seed) for seed in BASE_SEEDS]
    assert len(set(old_signatures)) == 9
    candidates = {i: {} for i in range(1, 9)}
    bound = isqrt(4 * MAX_CANDIDATE_NORM) + 2
    for a in range(-bound, bound + 1):
        for b in range(-bound, bound + 1):
            seed = (a, b)
            n = norm(seed)
            if not 0 < n <= MAX_CANDIDATE_NORM:
                continue
            signature = residue_signature(seed)
            if signature not in old_signatures[1:]:
                continue
            slot = old_signatures.index(signature)
            canonical = min(orbit(seed))
            if canonical != min(orbit(BASE_SEEDS[slot])):
                candidates[slot][canonical] = n
    return candidates


def digit_table(seeds):
    table = {}
    for index, seed in enumerate(seeds):
        for coefficient in orbit(seed):
            key = coefficient[0] % 9, coefficient[1] % 9
            assert key[0] % 3 != 0
            assert key not in table
            table[key] = (coefficient, index)
    assert len(table) == 54
    return table


def next_state(state, table):
    a, b = state
    if a % 3:
        digit, _ = table[a % 9, b % 9]
        a -= digit[0]
        b -= digit[1]
    assert a % 3 == 0
    return a + b, -a // 3


def termination_audit(seeds, table):
    max_norm = max(norm(seed) for seed in seeds)
    # For N(z)>2D with D=max N(d), the triangle inequality gives
    # N((z-d)/tau) <= (sqrt(N(z))+sqrt(D))^2/3 < N(z).
    # For N(z)<=2D the same bound stays <=2D, so the ball is closed.
    radius = 2 * max_norm
    coordinate_bound = 3 * isqrt(radius) + 4
    states = {
        (a, b) for a in range(-coordinate_bound, coordinate_bound + 1)
        for b in range(-coordinate_bound, coordinate_bound + 1)
        if norm((a, b)) <= radius
    }
    assert (0, 0) in states
    terminating = {(0, 0)}
    for start in sorted(states):
        state = start
        path = []
        seen = {}
        while state not in terminating:
            if state not in states:
                raise AssertionError("small-norm transition escaped closed ball")
            if state in seen:
                return {"status": "cycle", "cycle": path[seen[state]:],
                        "small_states": len(states), "radius": radius}
            seen[state] = len(path)
            path.append(state)
            state = next_state(state, table)
        terminating.update(path)
    assert len(terminating) == len(states)
    return {"status": "terminates", "small_states": len(states),
            "radius": radius}


def planned_pairs(digits):
    if not digits:
        return 0
    assert digits[-1] is not None
    index = len(digits) - 1
    started = False
    pairs = 0
    while index >= 0:
        if started and digits[index] is None and index > 0:
            pairs += 1
            index -= 2
        else:
            started |= digits[index] is not None
            index -= 1
    return pairs


def score_case(case, table):
    a = int(case["short_a_hex"], 16)
    b = int(case["short_b_hex"], 16)
    original = (a, b)
    digits = []
    chosen = []
    while a or b:
        assert len(digits) < 512
        if a % 3:
            digit, index = table[a % 9, b % 9]
            digits.append(index)
            chosen.append(digit)
            a -= digit[0]
            b -= digit[1]
        else:
            digits.append(None)
            chosen.append(None)
        assert a % 3 == 0
        a, b = a + b, -a // 3
    rebuilt = (0, 0)
    for digit in reversed(chosen):
        rebuilt = tau(rebuilt)
        if digit is not None:
            rebuilt = rebuilt[0] + digit[0], rebuilt[1] + digit[1]
    assert rebuilt == original
    if not digits:
        return {"positions": 0, "pairs": 0, "mixed_adds": 0,
                "general_adds": 0, "cache_entries": 0, "charged": 0}
    pairs = planned_pairs(digits)
    steps = len(digits) - 1
    assert steps >= 2 * pairs
    nonzero = [index for index in digits if index is not None]
    assert nonzero
    additions = nonzero[:-1]  # Highest digit initializes the accumulator.
    mixed = sum(index == 0 for index in additions)
    general = len(additions) - mixed
    cache_entries = len({index for index in additions if index > 0})
    charged = (10 * pairs + 6 * (steps - 2 * pairs)
               + 11 * mixed + 14 * general + 2 * cache_entries)
    return {"positions": len(digits), "pairs": pairs,
            "mixed_adds": mixed, "general_adds": general,
            "cache_entries": cache_entries, "charged": charged}


def score_panel(cases, table):
    rows = [score_case(case, table) for case in cases]
    return {key: sum(row[key] for row in rows) for key in rows[0]}


def main():
    fixture_bytes = FIXTURE.read_bytes()
    fixture = json.loads(fixture_bytes)
    cases = fixture["cases"]
    assert len(cases) == 64
    base_table = digit_table(BASE_SEEDS)
    base_audit = termination_audit(BASE_SEEDS, base_table)
    assert base_audit["status"] == "terminates"
    baseline = score_panel(cases, base_table)
    assert baseline["charged"] + 83 * 64 == 88656
    for case in cases:
        row = score_case(case, base_table)
        expected = case["expected_counts"]
        assert row["pairs"] == expected["tau_pairs"]
        assert row["mixed_adds"] == expected["mixed_adds"]
        assert row["general_adds"] == expected["general_adds"]
        assert row["cache_entries"] == expected["cache_entries"]

    rows = []
    for slot, alternatives in catalog().items():
        for candidate, candidate_norm in sorted(alternatives.items()):
            seeds = BASE_SEEDS.copy()
            seeds[slot] = candidate
            table = digit_table(seeds)
            audit = termination_audit(seeds, table)
            row = {"slot": slot, "candidate": candidate,
                   "candidate_norm": candidate_norm, "termination": audit}
            if audit["status"] == "terminates":
                totals = score_panel(cases, table)
                row["totals"] = totals
                row["charged_saving_before_unknown_seed_prep"] = (
                    baseline["charged"] - totals["charged"]
                )
            else:
                row["totals"] = None
                row["charged_saving_before_unknown_seed_prep"] = None
            rows.append(row)
    valid = [row for row in rows if row["totals"] is not None]
    ranked = sorted(valid, key=lambda row: (
        -row["charged_saving_before_unknown_seed_prep"],
        row["slot"], row["candidate"],
    ))
    result = {
        "schema": 1,
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_dependency_sha256": hashlib.sha256(
            (HERE / "seed_chain_bound.py").read_bytes()
        ).hexdigest(),
        "candidate_norm_limit": MAX_CANDIDATE_NORM,
        "termination_proof": "strict Eisenstein norm descent above 2*max_digit_norm; exhaustive closed finite-state check below or at that bound",
        "baseline_termination": base_audit,
        "baseline": baseline,
        "rows": rows,
        "candidate_count": len(rows),
        "valid_count": len(valid),
        "cycle_count": len(rows) - len(valid),
        "top_five": ranked[:5],
        "cpu_speedup_claim": None,
        "academic_novelty_claim": None,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
