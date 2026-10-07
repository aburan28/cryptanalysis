#!/usr/bin/env python3
"""Exhaustive carry closure for the fixed selective mixed τ alphabet.

This explores every residue of the original width-four digit table at
every reachable carry. It therefore permits input-residue sequences that
may not arise from an actual scalar and proves a conservative bound.
"""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS, norm
from mixed_atlas_screen import make_options


HERE = Path(__file__).resolve().parent


def closure():
    tables = [digit_table(seeds) for seeds in SEEDS]
    options = make_options(tables, True)
    reached = {(0, 0)}
    generations = []
    transitions = 0
    while True:
        following = set(reached)
        for ca, cb in sorted(reached):
            for ra in range(9):
                for rb in range(9):
                    old = tables[0].get((ra, rb))
                    da, db = old[0] if old is not None else (0, 0)
                    for offered, _ in options[((ra + ca) % 9, (rb + cb) % 9)]:
                        ea, eb = offered if offered is not None else (0, 0)
                        x = da + ca - ea
                        y = db + cb - eb
                        assert x % 3 == 0
                        following.add((x + y, -x // 3))
                        transitions += 1
        if following == reached:
            break
        reached = following
        generations.append({"generation": len(generations) + 1,
                            "states": len(reached),
                            "max_norm": max(map(norm, reached))})
    assert len(reached) == 715
    assert max(map(norm, reached)) == 432
    assert max(max(abs(a), abs(b)) for a, b in reached) == 36
    encoded = json.dumps(sorted(reached), separators=(",", ":")).encode()
    return {"schema": 1, "states": len(reached),
            "max_norm": max(map(norm, reached)),
            "max_absolute_coordinate": 36,
            "generations": generations,
            "transition_evaluations": transitions,
            "state_set_sha256": hashlib.sha256(encoded).hexdigest(),
            "sources": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                        for name in ("carry_closure.py", "alternate_digit_atlas.py",
                                     "atlas_portfolio.py", "mixed_atlas_screen.py",
                                     "seed_chain_bound.py")},
            "cpu_speedup_claim": None,
            "academic_novelty_claim": None}


if __name__ == "__main__":
    print(json.dumps(closure(), sort_keys=True, separators=(",", ":")))
