#!/usr/bin/env python3
"""Exact bounded-carry translation between three width-four tau atlases."""

import hashlib
import json
from collections import deque
from pathlib import Path

from alternate_digit_atlas import (BASE_SEEDS, HERE, digit_table, planned_pairs,
                                   termination_audit)
from seed_chain_bound import norm, tau


JOINT = BASE_SEEDS.copy()
JOINT[5], JOINT[6] = (2, -4), (4, -8)
LINKED = JOINT.copy()
LINKED[7] = (4, 4)
SEEDS = [BASE_SEEDS, JOINT, LINKED]
PREP = [83, 79, 75]
NAMES = ["original", "two_orbit", "three_orbit"]
FIXTURES = [HERE / "fixture.json", HERE / "linked-fresh-fixture.json",
            HERE / "portfolio-fixture.json"]


def direct_recode(original, table):
    a, b = original
    digits = []
    while a or b:
        assert len(digits) < 512
        selected = table[a % 9, b % 9] if a % 3 else None
        digits.append(selected)
        if selected is not None:
            a -= selected[0][0]
            b -= selected[0][1]
        assert a % 3 == 0
        a, b = a + b, -a // 3
    return digits


def baseline_scan(original, table):
    a, b = original
    states = []
    while a or b:
        assert len(states) < 512
        residue = a % 9, b % 9
        selected = table[residue] if a % 3 else None
        states.append((residue, selected))
        if selected is not None:
            a -= selected[0][0]
            b -= selected[0][1]
        assert a % 3 == 0
        a, b = a + b, -a // 3
    return states


def translate(states, table, changed_slots):
    carry = (0, 0)
    digits = []
    active = 0
    nonzero_carry = 0
    peak_norm = 0
    for residue, old in states:
        if carry == (0, 0) and (old is None or old[1] not in changed_slots):
            digits.append(old)
            continue
        active += 1
        nonzero_carry += carry != (0, 0)
        shifted = (residue[0] + carry[0]) % 9, (residue[1] + carry[1]) % 9
        new = table[shifted] if shifted[0] % 3 else None
        digits.append(new)
        d = old[0] if old is not None else (0, 0)
        e = new[0] if new is not None else (0, 0)
        delta_a = d[0] + carry[0] - e[0]
        delta_b = d[1] + carry[1] - e[1]
        assert delta_a % 3 == 0
        carry = delta_a + delta_b, -delta_a // 3
        peak_norm = max(peak_norm, norm(carry))
        assert peak_norm <= 896
    tail = 0
    while carry != (0, 0):
        assert tail < 64
        a, b = carry
        new = table[a % 9, b % 9] if a % 3 else None
        digits.append(new)
        if new is not None:
            a -= new[0][0]
            b -= new[0][1]
        assert a % 3 == 0
        carry = a + b, -a // 3
        peak_norm = max(peak_norm, norm(carry))
        assert peak_norm <= 896
        tail += 1
    while digits and digits[-1] is None:
        digits.pop()
    return digits, {"active_steps": active, "nonzero_carry_steps": nonzero_carry,
                    "tail_steps": tail, "peak_carry_norm": peak_norm}


def reconstruct(digits):
    rebuilt = (0, 0)
    for digit in reversed(digits):
        rebuilt = tau(rebuilt)
        if digit is not None:
            rebuilt = rebuilt[0] + digit[0][0], rebuilt[1] + digit[0][1]
    return rebuilt


def source_cost(digits, prep):
    if not digits:
        return prep
    positions = [digit[1] if digit is not None else None for digit in digits]
    pairs = planned_pairs(positions)
    steps = len(digits) - 1
    adds = [index for index in positions if index is not None][:-1]
    mixed = sum(index == 0 for index in adds)
    general = len(adds) - mixed
    cache = len({index for index in adds if index > 0})
    charged = (10 * pairs + 6 * (steps - 2 * pairs) + 11 * mixed
               + 14 * general + 2 * cache)
    return prep + charged


def automaton_audit(base, alternate):
    """Close carry transitions over all 81 possible baseline residues."""
    seen = {(0, 0)}
    queue = deque([(0, 0)])
    edges = 0
    max_norm = 0
    while queue:
        carry = queue.popleft()
        max_norm = max(max_norm, norm(carry))
        for ra in range(9):
            for rb in range(9):
                old = base[ra, rb] if ra % 3 else None
                shifted = (ra + carry[0]) % 9, (rb + carry[1]) % 9
                new = alternate[shifted] if shifted[0] % 3 else None
                d = old[0] if old is not None else (0, 0)
                e = new[0] if new is not None else (0, 0)
                delta_a = d[0] + carry[0] - e[0]
                delta_b = d[1] + carry[1] - e[1]
                assert delta_a % 3 == 0
                successor = delta_a + delta_b, -delta_a // 3
                assert norm(successor) <= 896
                edges += 1
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
    assert edges == 81 * len(seen)
    return {"reachable_states": len(seen), "transitions": edges,
            "max_reachable_carry_norm": max_norm}


def score_fixture(path, tables, changed):
    raw = path.read_bytes()
    fixture = json.loads(raw)
    rows = []
    for case in fixture["cases"]:
        original = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
        states = baseline_scan(original, tables[0])
        streams = [[old for _, old in states]]
        work = [{"active_steps": 0, "nonzero_carry_steps": 0,
                 "tail_steps": 0, "peak_carry_norm": 0}]
        for table, slots in zip(tables[1:], changed):
            digits, stats = translate(states, table, slots)
            streams.append(digits)
            work.append(stats)
        for stream, table in zip(streams, tables):
            assert stream == direct_recode(original, table)
            assert reconstruct(stream) == original
        costs = [source_cost(stream, prep) for stream, prep in zip(streams, PREP)]
        selected = min(range(3), key=lambda index: costs[index])
        rows.append({"index": case["index"], "costs": costs,
                     "selected": NAMES[selected], "selected_cost": costs[selected],
                     "work": work})
    return {"fixture": path.name,
            "fixture_sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(rows), "totals": [sum(r["costs"][i] for r in rows)
                                          for i in range(3)],
            "selected_total": sum(r["selected_cost"] for r in rows),
            "choice_counts": {name: sum(r["selected"] == name for r in rows)
                              for name in NAMES},
            "max_peak_carry_norm": max(w["peak_carry_norm"] for r in rows
                                       for w in r["work"]),
            "active_steps": sum(w["active_steps"] for r in rows
                                for w in r["work"]),
            "rows": rows}


def main():
    tables = [digit_table(seeds) for seeds in SEEDS]
    audits = [termination_audit(seeds, table) for seeds, table in zip(SEEDS, tables)]
    assert all(audit["status"] == "terminates" for audit in audits)
    changed = [{index for index in range(9) if SEEDS[0][index] != seeds[index]}
               for seeds in SEEDS[1:]]
    automata = [automaton_audit(tables[0], table) for table in tables[1:]]
    panels = [score_fixture(path, tables, changed) for path in FIXTURES]
    assert [panel["cases"] for panel in panels] == [64, 256, 256]
    assert panels[0]["totals"][0] == 88656
    result = {"schema": 1,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_dependency_sha256": hashlib.sha256(
                  (HERE / "alternate_digit_atlas.py").read_bytes()).hexdigest(),
              "tables": NAMES, "preparation_M_plus_S": PREP,
              "changed_slots": [sorted(x) for x in changed],
              "termination": audits, "carry_norm_bound": 896,
              "carry_automata": automata,
              "panels": panels, "cpu_speedup_claim": None,
              "academic_novelty_claim": None}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
