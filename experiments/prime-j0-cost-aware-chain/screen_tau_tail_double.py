#!/usr/bin/env python3
"""Screen the two-digit tail policy on previously used design scalars."""

import hashlib
import json
from pathlib import Path
import struct

from make_tau_tail_double import BOUND, PHASES, generate as double_generate
from make_tau_tail_double import index, step
from make_tau_tail_gate import canonical_cost
from make_tau_tail_oracle import generate as restricted_generate
from run import representatives, recode


ROOT = Path(__file__).resolve().parent
ENDO_LAMBDA = {"glv-j0-32": 16027563, "j0-56": 1212946466324730}


def sample_tail(k, order, omega_lambda):
    _, a, b = min(representatives(order, omega_lambda, k), key=lambda row: row[0])
    digits = recode(a, b)
    position = 0
    while max(abs(a), abs(b)) > BOUND:
        for _ in range(2):
            digit = digits[position] if position < len(digits) else None
            position += 1
            if digit:
                a -= digit[0]
                b -= digit[1]
            if a % 3:
                raise AssertionError("canonical prefix is not tau-divisible")
            a, b = a + b, -(a // 3)
    return a, b, (position // 2) % PHASES


def main():
    old_costs, _old_actions = restricted_generate()
    costs, actions = double_generate()
    if not all(new <= old for new, old in zip(costs, old_costs)):
        raise AssertionError("double policy must include restricted actions")
    fixture_path = ROOT / "tail-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    rows = []
    source_paths = [Path(__file__).resolve(), ROOT / "make_tau_tail_double.py",
                    ROOT / "make_tau_tail_oracle.py", ROOT / "make_tau_tail_gate.py",
                    ROOT / "run.py", fixture_path]
    for case in (fixture["cases"][0], fixture["cases"][4]):
        scalar_path = ROOT / case["scalar_file"]
        raw = scalar_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != case["scalar_file_sha256"]:
            raise ValueError(f"design scalar file changed: {scalar_path}")
        source_paths.append(scalar_path)
        scalars = struct.unpack(f"<{len(raw) // 8}Q", raw)
        curve = case["curve"]["name"]
        order = case["curve"]["order"]
        omega_lambda = order - ENDO_LAMBDA[curve]
        old_total = new_total = canonical_total = extra_wins = double_used = 0
        for scalar in scalars:
            a, b, phase = sample_tail(scalar, order, omega_lambda)
            pos = index(a, b, phase)
            canonical = canonical_cost(a, b, phase)
            old = min(canonical, old_costs[pos])
            new = min(canonical, costs[pos])
            canonical_total += canonical
            old_total += old
            new_total += new
            extra_wins += new < old
            if new < old:
                x, y, p = a, b, phase
                while (x, y) != (0, 0):
                    even, odd = actions[index(x, y, p)]
                    double_used += even != 255 and odd != 255
                    x, y, _edge = step(x, y, p, even, odd)
                    p = (p + 1) % PHASES
        rows.append({"curve": curve, "scalars": len(scalars),
                     "omega_lambda": omega_lambda,
                     "extra_wins": extra_wins,
                     "double_pairs_on_extra_wins": double_used,
                     "canonical_tail_cost": canonical_total,
                     "restricted_tail_cost": old_total,
                     "double_digit_tail_cost": new_total,
                     "extra_saved_weight": old_total - new_total})
    report = {"schema": 1, "status": "design_data_operation_screen_only",
              "cpu_timing_claim": None,
              "raw_actions": 1 + 54 + 54 + 54 * 54,
              "unique_contributions_per_phase": 727,
              "bounded_states": len(costs),
              "reachable_states": sum(action is not None for action in actions),
              "states_better_than_restricted": sum(a < b for a, b in zip(costs, old_costs)),
              "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in source_paths},
              "results": rows}
    output = ROOT / "tail-double-screen.json"
    data = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text() != data:
        raise ValueError(f"design screen changed: {output}")
    output.write_text(data)
    print(json.dumps({"status": report["status"], "rows": len(rows),
                      "extra_saved_weight": sum(row["extra_saved_weight"] for row in rows)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
