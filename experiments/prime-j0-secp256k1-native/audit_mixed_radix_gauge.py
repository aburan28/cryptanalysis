#!/usr/bin/env python3
"""Exact Eisenstein replay of cheap paired τ steps across radix-two exits."""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
from mixed_atlas_screen import make_options
from mixed_radix_scalar import FIXTURES, recode, source_cost
from selective_mixed_atlas import recode as selective_recode


HERE = Path(__file__).resolve().parent


def omega(value):
    a, b = value
    return (a + 3 * b, -a - 2 * b)


def add(left, right):
    return (left[0] + right[0], left[1] + right[1])


def pair_count(actions):
    count = 0
    index = len(actions) - 2
    while index >= 0:
        if (index > 0 and actions[index][0] == "tau"
                and actions[index][1] is None
                and actions[index - 1][0] == "tau"):
            count += 1
            index -= 2
        else:
            index -= 1
    return count


def evaluate(actions):
    pairs = pair_count(actions)
    gauge = (-2 * pairs) % 3
    accumulator = (0, 0)
    used_pairs = 0
    index = len(actions) - 1
    while index >= 0:
        radix, digit, _ = actions[index]
        pair = (accumulator != (0, 0) and radix == "tau" and
                digit is None and index > 0 and actions[index - 1][0] == "tau")
        if pair:
            accumulator = (-3 * accumulator[0], -3 * accumulator[1])
            gauge = (gauge + 2) % 3
            used_pairs += 1
            index -= 1
            digit = actions[index][1]
        elif accumulator != (0, 0):
            a, b = accumulator
            accumulator = (2 * a, 2 * b) if radix == "two" else (-3 * b, a + 3 * b)
        if digit is not None:
            rotated = digit
            for _ in range(gauge):
                rotated = omega(rotated)
            accumulator = add(accumulator, rotated)
        index -= 1
    assert gauge == 0 and used_pairs == pairs
    return accumulator, pairs


def main():
    tables = [digit_table(seeds) for seeds in SEEDS]
    options = make_options(tables, True)
    panels = []
    for path in FIXTURES:
        raw = path.read_bytes()
        cases = json.loads(raw)["cases"]
        choices = {"radix_two": 0, "selective": 0}
        pairs = 0
        for case in cases:
            short = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
            old_digits, old_score = selective_recode(short, tables, options)
            actions, status = recode(short, tables[0])
            assert status["status"] == "verified" and actions is not None
            if source_cost(actions)["total_M_plus_S"] < old_score["total_M_plus_S"]:
                selected = "radix_two"
            else:
                selected = "selective"
                actions = [("tau", (digit[0], digit[1]) if digit else None,
                            digit[2] if digit else None) for digit in old_digits]
            output, used_pairs = evaluate(actions)
            assert output == short, (path.name, case["index"])
            if selected == "radix_two":
                assert used_pairs == source_cost(actions)["tau_pairs"]
            choices[selected] += 1
            pairs += used_pairs
        panels.append({"fixture": path.name,
                       "fixture_sha256": hashlib.sha256(raw).hexdigest(),
                       "cases": len(cases), "choices": choices,
                       "charged_pairs_replayed": pairs,
                       "verified": True})
    result = {"schema": 1, "verified": True, "panels": panels,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "recoder_sha256": hashlib.sha256((HERE / "mixed_radix_scalar.py").read_bytes()).hexdigest(),
              "cpu_speedup_claim": None}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
