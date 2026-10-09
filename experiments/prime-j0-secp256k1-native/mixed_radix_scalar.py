#!/usr/bin/env python3
"""Greedy 2/τ scalar chain and a complete-cost selective portfolio."""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
from mixed_atlas_screen import make_options
from selective_mixed_atlas import recode as selective_recode


HERE = Path(__file__).resolve().parent
FIXTURES = (HERE / "fixture.json", HERE / "mixed-radix-fixture.json")
MAX_ACTIONS = 512


def reconstruct(actions):
    value = (0, 0)
    for radix, digit, _ in reversed(actions):
        a, b = value
        value = (2 * a, 2 * b) if radix == "two" else (-3 * b, a + 3 * b)
        if digit is not None:
            value = (value[0] + digit[0], value[1] + digit[1])
    return value


def recode(short, table):
    a, b = short
    actions = []
    seen = set()
    while a or b:
        if (a, b) in seen:
            return None, {"status": "cycle", "state": [a, b], "actions": len(actions)}
        if len(actions) >= MAX_ACTIONS:
            return None, {"status": "limit", "actions": len(actions)}
        seen.add((a, b))
        if a % 2 == 0 and b % 2 == 0:
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
    return actions, {"status": "verified"}


def source_cost(actions):
    assert actions and actions[-1][1] is not None
    charged = [seed for _, _, seed in actions if seed is not None][:-1]
    mixed = sum(seed == 0 for seed in charged)
    general = len(charged) - mixed
    cache = len({seed for seed in charged if seed > 0})
    tau_steps = sum(radix == "tau" for radix, _, _ in actions[:-1])
    doubles = sum(radix == "two" for radix, _, _ in actions[:-1])
    pairs = 0
    index = len(actions) - 2
    while index >= 0:
        if (index > 0 and actions[index][0] == "tau"
                and actions[index][1] is None
                and actions[index - 1][0] == "tau"):
            pairs += 1
            index -= 2
        else:
            index -= 1
    total = (83 + 6 * tau_steps + 7 * doubles - 2 * pairs
             + 11 * mixed + 14 * general + 2 * cache)
    return {"total_M_plus_S": total, "preparation_M_plus_S": 83,
            "tau_steps": tau_steps, "tau_pairs": pairs,
            "doubles": doubles, "mixed_adds": mixed,
            "general_adds": general, "cache_entries": cache}


def score_fixture(path, tables, options):
    raw = path.read_bytes()
    fixture = json.loads(raw)
    rows = []
    for case in fixture["cases"]:
        short = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
        tau_digits, selective = selective_recode(short, tables, options)
        actions, status = recode(short, tables[0])
        if actions is None:
            rows.append({"index": case["index"], "greedy_status": status,
                         "selected": "selective", "selective_M_plus_S": selective["total_M_plus_S"],
                         "greedy_M_plus_S": None, "selected_M_plus_S": selective["total_M_plus_S"]})
            continue
        greedy = source_cost(actions)
        selected = "radix_two" if greedy["total_M_plus_S"] < selective["total_M_plus_S"] else "selective"
        encoded = json.dumps(actions, separators=(",", ":")).encode()
        rows.append({"index": case["index"], "greedy_status": status,
                     "selected": selected,
                     "selective_M_plus_S": selective["total_M_plus_S"],
                     "greedy_M_plus_S": greedy["total_M_plus_S"],
                     "selected_M_plus_S": min(greedy["total_M_plus_S"], selective["total_M_plus_S"]),
                     "greedy_action_sha256": hashlib.sha256(encoded).hexdigest(),
                     "selective_digit_sha256": hashlib.sha256(
                         json.dumps(tau_digits, separators=(",", ":")).encode()).hexdigest(),
                     "greedy_actions": len(actions), **greedy})
    return {"fixture": path.name,
            "fixture_sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(rows),
            "selective_total": sum(row["selective_M_plus_S"] for row in rows),
            "greedy_total": sum(row["greedy_M_plus_S"] for row in rows
                                if row["greedy_M_plus_S"] is not None),
            "selected_total": sum(row["selected_M_plus_S"] for row in rows),
            "radix_two_choices": sum(row["selected"] == "radix_two" for row in rows),
            "failures": sum(row["greedy_status"]["status"] != "verified" for row in rows),
            "rows": rows}


def main():
    tables = [digit_table(seeds) for seeds in SEEDS]
    options = make_options(tables, True)
    panels = [score_fixture(path, tables, options) for path in FIXTURES]
    assert panels[0]["cases"] == 64 and panels[1]["cases"] == 256
    assert panels[0]["selective_total"] == 87298
    result = {"schema": 1, "panels": panels,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_dependency_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                           for name in ("selective_mixed_atlas.py", "alternate_digit_atlas.py",
                                                        "mixed_atlas_screen.py", "atlas_portfolio.py")},
              "cpu_speedup_claim": None,
              "academic_novelty_claim": None}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
