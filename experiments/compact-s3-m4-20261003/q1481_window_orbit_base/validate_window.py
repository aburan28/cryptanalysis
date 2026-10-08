#!/usr/bin/env python3
"""Exhaustively check the long-zero-gap representative claim at small n."""

from __future__ import annotations

import json
from pathlib import Path

from enumerate_base import representatives

HERE = Path(__file__).resolve().parent


def rotations(mask: int, n: int) -> set[int]:
    result = set()
    full = (1 << n) - 1
    for _ in range(n):
        result.add(mask)
        mask = ((mask << 1) | (mask >> (n - 1))) & full
    return result


def has_window(mask: int, n: int, d: int) -> bool:
    for start in range(n):
        window = ((1 << d) - 1) << start
        window = (window | (window >> n)) & ((1 << n) - 1)
        if mask & ~window == 0:
            return True
    return False


def run() -> dict:
    rows = []
    for n, d in ((11, 3), (11, 4), (13, 3), (13, 5)):
        assert 2 * d < n
        reps = [mask for mask, _ in representatives(d)]
        assert len(reps) == len(set(reps)) == 1 << (d - 1)
        covered = set()
        for rep in reps:
            orbit = rotations(rep, n)
            assert len(orbit) == n
            assert not covered.intersection(orbit)
            covered.update(orbit)
        exhaustive = {mask for mask in range(1, 1 << n)
                      if has_window(mask, n, d)}
        assert covered == exhaustive
        rows.append({"n": n, "d": d, "orbits": len(reps),
                     "raw_x_masks": len(covered), "status": "PASS"})
    return {"kind": "q1481_exhaustive_small_normal_basis_window_check",
            "proposal_id": "Q1481", "rows": rows, "status": "PASS"}


def main():
    result = run()
    path = HERE / "window_validation.json"
    if path.exists():
        assert json.loads(path.read_text()) == result
        print("Q1481 small-window validation PASS (archived)")
    else:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("Q1481 small-window validation PASS")


if __name__ == "__main__":
    main()
