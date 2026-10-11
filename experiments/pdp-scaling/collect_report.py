"""Turn relation-collection JSONL (from collect.py / collect_sweep.sh) into tables.

    python3 collect_report.py results/collect_*.jsonl                  # print
    python3 collect_report.py --update-readme results/collect_*.jsonl  # and splice into README.md

Every configuration in a cell ran on the same targets (same seed), so the
speedups are paired.  The baseline is upstream WDSat, default branching order,
no trace constraint.  "rel/CPU-s" uses the oracle's exact decomposability count
"rel / CPU-s" counts verified relations only, so a configuration that misses
oracle-confirmed relations is charged for them (and flagged UNSOUND); the
unsatisfiable searches' conflicts are the hardware-independent cost that
dominates relation collection.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE = ("wdsat", "default", False)


def label(cfg: tuple) -> str:
    engine, order, trace = cfg
    s = engine
    if order != "default":
        s += "+" + order
    if trace:
        s += "+trace"
    return s


def load(paths: list[str]) -> dict[tuple, dict[tuple, dict]]:
    cells: dict[tuple, dict[tuple, dict]] = defaultdict(dict)
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            cfg = (d["engine"], d["order"], bool(d.get("trace", False)))
            cells[(d["n"], d["l"])][cfg] = d  # the last run of a (cell, config) wins
    return cells


def table(cells: dict) -> str:
    out = [
        "| n | l | configuration | attempts | relations (verified / oracle, missed) | UNSAT conflicts | UNSAT CPU ms | CPU ms / attempt | rel / CPU-s | speedup vs baseline (CPU) | UNSAT conflicts vs baseline |",
        "|--:|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for n, l in sorted(cells):
        runs = cells[(n, l)]
        base = runs.get(BASE)
        for cfg in sorted(runs, key=lambda c: (c != BASE, label(c))):
            d = runs[cfg]
            oracle = d.get("oracle_decomposable")
            rel_cpu = (
                d["verified"] / d["attempts"] / d["cpu_per_call"]
                if d["cpu_per_call"]
                else 0.0
            )
            unsound = bool(d.get("oracle_missed"))
            if base and cfg != BASE:
                sp = f"{base['cpu_per_call'] / d['cpu_per_call']:.2f}x"
                cr = (
                    f"{base['conf_unsat_mean'] / d['conf_unsat_mean']:.2f}x"
                    if d["conf_unsat_mean"]
                    else ""
                )
            else:
                sp = cr = "1.00x" if cfg == BASE else ""
            if unsound:
                sp += " (UNSOUND: misses relations)"
            out.append(
                f"| {n} | {l} | {label(cfg)} | {d['attempts']} | {d['verified']} / {oracle}, {d.get('oracle_missed')} "
                f"| {d['conf_unsat_mean']:,.0f} | {1000 * d['cpu_unsat_mean']:.1f} | {1000 * d['cpu_per_call']:.1f} "
                f"| {rel_cpu:.2f} | {sp} | {cr} |"
            )
    return "\n".join(out)


def scaling(cells: dict) -> str:
    """log2(UNSAT conflicts) = a + c*l per configuration, and the paired gain per cell."""
    series: dict[tuple, list[tuple[int, int, float]]] = defaultdict(list)
    for (n, l), runs in cells.items():
        for cfg, d in runs.items():
            if d["conf_unsat_mean"] > 0:
                series[cfg].append((n, l, math.log2(d["conf_unsat_mean"])))
    out = [
        "| configuration | cells | c = d log2(UNSAT conflicts) / d l | d log2 / d n | mean paired gain over baseline (bits) | spread (bits) |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    for cfg in sorted(series, key=lambda c: (c != BASE, label(c))):
        pts = series[cfg]
        if len({p[1] for p in pts}) < 2:
            continue
        X = np.array([[1.0, p[1], p[0]] for p in pts])
        y = np.array([p[2] for p in pts])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        gains = []
        for (n, l), runs in cells.items():
            if (
                cfg in runs
                and BASE in runs
                and runs[cfg]["conf_unsat_mean"]
                and runs[BASE]["conf_unsat_mean"]
            ):
                gains.append(
                    math.log2(
                        runs[BASE]["conf_unsat_mean"] / runs[cfg]["conf_unsat_mean"]
                    )
                )
        g = (
            f"{np.mean(gains):+.2f}"
            if gains and cfg != BASE
            else ("0" if cfg == BASE else "")
        )
        s = f"{(max(gains) - min(gains)):.2f}" if len(gains) > 1 and cfg != BASE else ""
        out.append(
            f"| {label(cfg)} | {len(pts)} | {coef[1]:.2f} | {coef[2]:+.3f} | {g} | {s} |"
        )
    return "\n".join(out)


def splice(readme: Path, name: str, body: str) -> None:
    text = readme.read_text()
    pat = re.compile(rf"(<!-- BEGIN {name} -->\n).*?(<!-- END {name} -->)", re.DOTALL)
    if not pat.search(text):
        raise SystemExit(f"marker {name} not found in {readme}")
    readme.write_text(pat.sub(lambda mo: mo.group(1) + body + "\n" + mo.group(2), text))


def main() -> None:
    args = sys.argv[1:]
    update = "--update-readme" in args
    paths = [a for a in args if a != "--update-readme"]
    cells = load(paths)
    t, s = table(cells), scaling(cells)
    print(t)
    print()
    print(s)
    if update:
        readme = Path(__file__).with_name("README.md")
        splice(readme, "COLLECT", t)
        splice(readme, "COLLECT_SCALING", s)
        print(f"\nupdated {readme}")


if __name__ == "__main__":
    main()
