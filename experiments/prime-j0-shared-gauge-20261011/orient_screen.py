#!/usr/bin/env python3
"""Screen offline unit orientations on disjoint design/validation halves."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import random


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUOTIENT = ROOT / "prime-j0-orbit-quotient-20261011"
SPEC = importlib.util.spec_from_file_location("quotient_orient", QUOTIENT / "verify_group.py")
q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def costs_for_masks(masks):
    size = sum(mask.bit_count() - 1 for mask in masks if mask)
    costs = [size + sum(bool(mask) and not (mask & (1 << frame))
                        for mask in masks) + (frame != 0)
             for frame in range(3)]
    return costs[0], min(costs)


COSTS = [costs_for_masks((key & 7, (key >> 3) & 7, (key >> 6) & 7))
         for key in range(512)]


def choices(scalars, atlas, terminal):
    rows = []
    for scalar in scalars:
        a, b = q.parent.screen.representative(scalar % q.parent.screen.ORDER)
        row = []
        for _ in range(12):
            digit, seed, exponent, unit = atlas.decode(a, b)
            row.append(None if seed == 0 else (exponent, unit // 2))
            a, b = (a - digit[0]) >> 10, (b - digit[1]) >> 10
        digit, seed, exponent, unit = terminal.decode(a, b)
        assert digit == (a, b)
        row.append(None if seed == 0 else (exponent, unit // 2))
        rows.append(row)
    return rows


def evaluate(rows, orientations):
    fixed = shared = 0
    for row in rows:
        masks = [0, 0, 0]
        for entry, orientation in zip(row, orientations):
            if entry is not None:
                exponent, power = entry
                masks[exponent] |= 1 << ((power + 3 - orientation) % 3)
        count0, count_shared = COSTS[masks[0] | masks[1] << 3 | masks[2] << 6]
        fixed += count0
        shared += count_shared
    return fixed, shared


def optimize(training):
    rng = random.Random(20261011)
    best = None
    starts = [(0,) * 13] + [tuple(rng.randrange(3) for _ in range(13))
                               for _ in range(11)]
    for start in starts:
        state = list(start)
        for _ in range(12):
            changed = False
            for window in range(13):
                previous = state[window]
                trials = []
                for orientation in range(3):
                    state[window] = orientation
                    trials.append(evaluate(training, state)[1])
                selected = min(range(3), key=lambda value: (trials[value], value))
                changed |= previous != selected
                state[window] = selected
            if not changed:
                break
        score = evaluate(training, state)[1]
        candidate = score, tuple(state)
        if best is None or candidate < best:
            best = candidate
    return best


def main():
    panel = QUOTIENT / "fresh-inputs.json"
    scalars = [int(raw, 16) for raw in json.loads(panel.read_bytes())["scalars_hex"]]
    assert len(scalars) == 4096
    full_path = QUOTIENT / "atlas-r1024-full-orbit-quotient.bin"
    terminal_path = QUOTIENT / "atlas-r1024-terminal-orbit-quotient.bin"
    atlas = q.QuotientFullAtlas(full_path)
    terminal = q.parent.TerminalAtlas(terminal_path)
    rows = choices(scalars, atlas, terminal)
    training, validation = rows[:2048], rows[2048:]
    baseline = [0] * 13
    train_score, orientations = optimize(training)
    assert train_score == evaluate(training, orientations)[1]
    scores = {
        part: {"cases": len(section),
               "baseline_fixed": evaluate(section, baseline)[0],
               "baseline_shared": evaluate(section, baseline)[1],
               "oriented_fixed": evaluate(section, orientations)[0],
               "oriented_shared": evaluate(section, orientations)[1]}
        for part, section in (("training", training), ("validation", validation),
                              ("all", rows))
    }
    receipt = {"schema": 1, "status": "screened",
               "timing_class": "operation_count_only",
               "source_sha256": digest(Path(__file__)),
               "panel_sha256": digest(panel),
               "full_atlas_sha256": digest(full_path),
               "terminal_atlas_sha256": digest(terminal_path),
               "training_cases": 2048,
               "optimizer": "12 deterministic coordinate-descent starts; training half only",
               "orientations": orientations,
               "scores": scores}
    (HERE / "orient-screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"orientations": orientations, "scores": scores}, sort_keys=True))


if __name__ == "__main__":
    main()
