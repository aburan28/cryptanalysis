#!/usr/bin/env python3
"""Count optimal shared unit frames on an existing design panel."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUOTIENT = ROOT / "prime-j0-orbit-quotient-20261011"
DIRECT = ROOT / "prime-j0-power2-cache-budget-20261011"
PARENT = ROOT / "prime-j0-power2-tau2-20261011"
SPEC = importlib.util.spec_from_file_location("quotient_design", QUOTIENT / "verify_group.py")
q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def frame_cost(sets, frame):
    return sum(len(powers) - 1 + (frame not in powers)
               for powers in sets if powers) + (frame != 0)


def evaluate(scalars, atlas, terminal):
    totals = Counter()
    selected = Counter()
    saving = Counter()
    failures = 0
    for scalar in scalars:
        a, b = q.parent.screen.representative(scalar % q.parent.screen.ORDER)
        sets = [set(), set(), set()]
        for _ in range(12):
            digit, seed, exponent, unit = atlas.decode(a, b)
            if seed:
                sets[exponent].add(unit // 2)
            a, b = (a - digit[0]) >> 10, (b - digit[1]) >> 10
        digit, seed, exponent, unit = terminal.decode(a, b)
        assert digit == (a, b)
        if seed:
            sets[exponent].add(unit // 2)
        costs = [frame_cost(sets, frame) for frame in range(3)]
        frame = min(range(3), key=lambda candidate: (costs[candidate], candidate))
        assert costs[frame] <= costs[0]
        totals["current_rotations"] += costs[0]
        totals["shared_rotations"] += costs[frame]
        totals["saved_rotations"] += costs[0] - costs[frame]
        selected[frame] += 1
        saving[costs[0] - costs[frame]] += 1
        failures += int(any(not powers for powers in sets))
    return {"cases": len(scalars), "rotations": dict(totals),
            "selected_frames": dict(selected),
            "saving_histogram": dict(saving),
            "cases_with_empty_bucket": failures}


def main():
    panel = QUOTIENT / "fresh-inputs.json"
    scalars = [int(raw, 16) for raw in json.loads(panel.read_bytes())["scalars_hex"]]
    assert len(scalars) == 4096
    terminal = q.parent.TerminalAtlas(
        QUOTIENT / "atlas-r1024-terminal-orbit-quotient.bin")
    variants = {
        "quotient": q.QuotientFullAtlas(
            QUOTIENT / "atlas-r1024-full-orbit-quotient.bin"),
        "budgeted_direct": q.parent.FullAtlas(
            DIRECT / "atlas-r1024-full-cache-budget.bin"),
        "minimum_direct": q.parent.FullAtlas(
            PARENT / "atlas-r1024-full-tau2.bin"),
    }
    results = {name: evaluate(scalars, atlas, terminal)
               for name, atlas in variants.items()}
    expected = json.loads((QUOTIENT / "group-check.json").read_bytes())["results"]
    for name, result in results.items():
        assert result["rotations"]["current_rotations"] == \
            expected[name]["gauge_rotations"]
    receipt = {"schema": 1, "status": "screened",
               "timing_class": "operation_count_only",
               "source_sha256": digest(Path(__file__)),
               "panel_sha256": digest(panel),
               "atlas_sha256": {name: atlas.digest
                                for name, atlas in variants.items()},
               "terminal_sha256": terminal.digest,
               "results": results}
    (HERE / "screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()
