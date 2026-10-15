#!/usr/bin/env python3
"""Exact point-payload screen for fourteen prime-norm T-tau windows."""

from functools import lru_cache
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from math import isqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-fifteen-position-radix-20261015" / "frontier15.py"
POSITIONS = 14


def parent_module():
    spec = spec_from_file_location("frontier15", PARENT)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    base = parent_module()
    base.STEPS = POSITIONS
    fixed = [base.screen(t) for t in range(300, 601)
             if base.prime(t*t - 3*t + 3)]
    by_t = {row["t"]: row for row in fixed}
    choices = [row["t"] for row in fixed if 330 <= row["t"] <= 430]

    @lru_cache(None)
    def terminal_seeds(radius):
        return (base.terminal_full_count(radius)-1)//6+1

    def evaluate(schedule):
        radii = [base.INITIAL_RADIUS]
        for t in schedule:
            row = by_t[t]
            radius = isqrt((radii[-1]+row["digit_radius"])**2//row["norm"])+1
            assert (radii[-1]+row["digit_radius"])**2 < row["norm"]*radius*radius
            radii.append(radius)
        seeds = sum(by_t[t]["digit_orbit_seeds"] for t in schedule)
        terminal = terminal_seeds(radii[-1])
        return {
            "schedule": schedule,
            "radius_sequence": radii,
            "digit_orbit_seeds": seeds,
            "terminal_orbit_seeds": terminal,
            "terminal_full_count": 6*(terminal-1)+1,
            "point_payload_bytes": 64*(seeds+terminal),
        }

    def coordinate_descent(start):
        schedule = start[:]
        for _ in range(20):
            changed = False
            for i in range(POSITIONS):
                winner = evaluate(schedule)
                best_t = schedule[i]
                for t in choices:
                    candidate = schedule[:]
                    candidate[i] = t
                    row = evaluate(candidate)
                    if row["point_payload_bytes"] < winner["point_payload_bytes"]:
                        winner, best_t = row, t
                if best_t != schedule[i]:
                    schedule[i] = best_t
                    changed = True
            if not changed:
                return evaluate(schedule)
        raise RuntimeError("coordinate descent did not settle")

    starts = [371, 380, 394, 400]
    local = [coordinate_descent([t]*POSITIONS) for t in starts]
    best_fixed = min(fixed, key=lambda row: row["point_payload_bytes"])
    best_local = min(local, key=lambda row: row["point_payload_bytes"])
    assert len(best_local["schedule"]) == POSITIONS
    assert best_local["point_payload_bytes"] <= best_fixed["point_payload_bytes"]
    return {
        "schema": 1,
        "positions": POSITIONS,
        "radix_family": "ordered-prime-norm-T-tau",
        "fixed_t_range_inclusive": [300, 600],
        "fixed_prime_norm_rows": len(fixed),
        "fixed_rows": fixed,
        "fixed_payload_minimum": best_fixed,
        "local_choice_t_range_inclusive": [330, 430],
        "local_starts": starts,
        "local_rows": local,
        "local_payload_minimum": best_local,
        "parent_source_sha256": sha256(PARENT.read_bytes()).hexdigest(),
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True, indent=2))
