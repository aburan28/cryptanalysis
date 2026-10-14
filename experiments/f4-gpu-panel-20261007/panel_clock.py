#!/usr/bin/env python3
"""Sum the panel step's per-phase cycles from F4E_CLK lines.

Each line is one panel, as thread 0 of the block saw it: candidates,
rounds, pivots, then six phases' cycles.  variants/clock.cuh (the staged
panel) reports setup, copy-in, first pass, rounds, copy-out and history
expansion; variants/clock-lazy.cuh (the lazy panel, with --lazy) reports
chunks instead of rounds, then nothing, compaction, setup, chunk scans,
final pass and expansion.  Prints each phase's share overall and by
candidate count, so the cost can be put on the step that has it.
"""

import sys

PHASES = ["setup", "copy-in", "first pass", "rounds", "copy-out", "expand"]
LAZY_PHASES = ["-", "compaction", "setup", "chunks", "final pass", "expand"]
BANDS = [(0, 512), (512, 1520), (1520, 1921), (1921, 4096), (4096, 1 << 32)]


def main(path, phases):
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith("F4E_CLK "):
                rows.append([int(v) for v in line.split()[1:]])
    if not rows:
        sys.exit(f"{path}: no F4E_CLK lines")
    total = [sum(r[3 + i] for r in rows) for i in range(len(phases))]
    grand = sum(total)
    rounds = sum(r[1] for r in rows)
    print(f"{path}: {len(rows)} panels, {rounds} rounds, {grand:.3e} cycles")
    for name, t in zip(phases, total):
        print(f"  {name:10s} {t:.3e} cycles  {100 * t / grand:5.1f}%")
    print(f"  cycles per round: {total[3] / max(rounds, 1):.0f}")
    print("  candidates      panels  cycles/panel  rounds%  expand%  cycles/round")
    for lo, hi in BANDS:
        band = [r for r in rows if lo <= r[0] < hi]
        if not band:
            continue
        cyc = sum(sum(r[3:]) for r in band)
        rd = sum(r[6] for r in band)
        ex = sum(r[8] for r in band)
        n_rounds = sum(r[1] for r in band)
        print(f"  [{lo:5d}, {hi:5d})  {len(band):6d}  {cyc / len(band):12.0f}"
              f"  {100 * rd / cyc:6.1f}  {100 * ex / cyc:6.1f}  {rd / max(n_rounds, 1):12.0f}")


if __name__ == "__main__":
    args = sys.argv[1:]
    lazy = "--lazy" in args
    for p in args:
        if p != "--lazy":
            main(p, LAZY_PHASES if lazy else PHASES)
