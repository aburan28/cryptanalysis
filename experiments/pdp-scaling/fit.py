"""Fit the measured PDP solve times and extrapolate to ECC2K-130.

    python3 fit.py results/*.csv                  # print the tables
    python3 fit.py --update-readme results/*.csv  # and splice them into README.md

For every (engine, m) with enough solved rows the model

    log2(seconds) = a + c*l + d*n

is fitted by least squares (c is the exponent that matters: bits of work
per extra dimension of the factor base; the combinatorial meet-in-the-
middle baseline has c = ceil(m/2) exactly).  The fit is then evaluated at
the ECC2K-130 parameters n = 131 with the l that the cost model of the
analysis picked for each m, and compared with

  * the per-PDP budget that ties Pollard rho on the <-1, tau> orbits
    (2^60.8 iterations in total), and
  * the meet-in-the-middle baseline 2^(l*ceil(m/2)) group operations.

Seconds are turned into rho iterations with STEP_SECONDS per iteration on
one core; the conversion is stated because it is an assumption, and a
factor of ten in it moves every gap by 3.3 bits, which is small against
the gaps reported.
"""

from __future__ import annotations

import csv
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

RHO_LOG2 = 60.81  # sqrt(pi r / (2 * 2 * 131)), r the 129-bit prime of ECC2K-130
STEP_SECONDS = 1e-7  # one rho iteration on one CPU core (assumed; see README)
N_TARGET = 131
N_MAX_MEASURED = 61

# (l, log2 PDP calls, log2 linear algebra, log2 budget per PDP in rho iterations), from the analysis
TARGETS = {
    3: [
        (44, None, None, None)
    ],  # m = 3 cannot tie rho even with a free PDP; l = n/3 shown for scale
    4: [(29, 48.6, 60.0, 12.2), (33, 36.6, 68.0, None)],
    5: [(28, 28.0, 58.3, 32.8)],
    6: [(24, 24.0, 50.6, 36.8)],
}


def load(paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for p in paths:
        with open(p) as fh:
            rows.extend(csv.DictReader(fh))
    return rows


def fit(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, int]:
    """Least squares for log2 t = a + c l + d n; returns (coef, stderr, count)."""
    X = np.array([[1.0, float(r["l"]), float(r["n"])] for r in rows])
    y = np.array([math.log2(max(float(r["seconds"]), 1e-4)) for r in rows])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = max(len(rows) - X.shape[1], 1)
    cov = np.linalg.pinv(X.T @ X) * (resid @ resid / dof)
    return coef, np.sqrt(np.maximum(np.diag(cov), 0)), len(rows)


def measured_tables(rows: list[dict], groups: dict) -> str:
    out: list[str] = []
    for (engine, m), rs in sorted(groups.items()):
        cells: dict[tuple[int, int], list[float]] = defaultdict(list)
        attempted: dict[tuple[int, int], int] = defaultdict(int)
        for r in rows:
            if (
                r["engine"] == engine
                and int(r["m"]) == m
                and r["curve"] == "koblitz"
                and r["status"] not in ("unsupported", "error")
            ):
                attempted[(int(r["n"]), int(r["l"]))] += 1
        for r in rs:
            cells[(int(r["n"]), int(r["l"]))].append(float(r["seconds"]))
        ns = sorted({k[0] for k in attempted})
        ls = sorted({k[1] for k in attempted})
        out.append(f"**{engine}, m = {m}**\n")
        out.append("| n \\ l | " + " | ".join(str(l) for l in ls) + " |")
        out.append("|---|" + "---|" * len(ls))
        for n in ns:
            line = []
            for l in ls:
                if (n, l) not in attempted:
                    line.append("")
                elif (n, l) in cells:
                    v = sorted(cells[(n, l)])
                    med = v[len(v) // 2]
                    line.append(f"{med:.3g} ({len(v)}/{attempted[(n, l)]})")
                else:
                    line.append(f"timeout (0/{attempted[(n, l)]})")
            out.append(f"| {n} | " + " | ".join(line) + " |")
        out.append("")
        if engine == "wdsat":
            import json

            conflicts: dict[tuple[int, int], list[int]] = defaultdict(list)
            for r in rs:
                d = json.loads(r["detail"]) if r["detail"].startswith("{") else {}
                if "conflicts" in d:
                    conflicts[(int(r["n"]), int(r["l"]))].append(int(d["conflicts"]))
            out.append(
                f"**{engine}, m = {m}: median conflicts** (the search-tree leaves; the paper's bound is `2^(3l)/3!`)\n"
            )
            out.append("| n \\ l | " + " | ".join(str(l) for l in ls) + " |")
            out.append("|---|" + "---|" * len(ls))
            for n in ns:
                line = []
                for l in ls:
                    v = sorted(conflicts.get((n, l), []))
                    line.append(f"{v[len(v) // 2]:,}" if v else "")
                out.append(f"| {n} | " + " | ".join(line) + " |")
            out.append(
                "| `2^(3l)/6` | "
                + " | ".join(f"{2 ** (3 * l) // 6:,}" for l in ls)
                + " |"
            )
            out.append("")
    return "\n".join(out)


def fit_table(groups: dict) -> tuple[str, dict[tuple[str, int], np.ndarray]]:
    out = [
        "| engine | m | rows | a | c (bits per l) | d (bits per n) | MITM c |",
        "|---|--:|--:|--:|--:|--:|--:|",
    ]
    fits: dict[tuple[str, int], np.ndarray] = {}
    for (engine, m), rs in sorted(groups.items()):
        if len({(r["l"], r["n"]) for r in rs}) < 4:
            continue
        coef, se, cnt = fit(rs)
        fits[(engine, m)] = coef
        out.append(
            f"| {engine} | {m} | {cnt} | {coef[0]:.1f} | {coef[1]:.2f} ± {se[1]:.2f} | "
            f"{coef[2]:.3f} ± {se[2]:.3f} | {math.ceil(m / 2)} |"
        )
    return "\n".join(out), fits


def extrapolation_table(fits: dict[tuple[str, int], np.ndarray]) -> str:
    engines = sorted({e for (e, _) in fits if e != "mitm"})
    out = [
        "| m | l | PDP calls | budget per PDP | MITM (exact) | "
        + " | ".join(f"{e} (fit) | {e} (fit, n = {N_MAX_MEASURED})" for e in engines)
        + " |",
        "|--:|--:|--:|--:|--:|" + "--:|--:|" * len(engines),
    ]
    for m, targets in sorted(TARGETS.items()):
        for l, calls, la, budget in targets:
            mitm = l * math.ceil(m / 2)

            def cell(log2_steps: float, budget: float | None = budget) -> str:
                if budget is None:
                    return f"2^{log2_steps:.0f}"
                return f"2^{log2_steps:.0f} (gap {log2_steps - budget:+.0f})"

            cells = [cell(mitm)]
            for e in engines:
                coef = fits.get((e, m))
                if coef is None:
                    cells += ["—", "—"]
                    continue
                full = (
                    coef[0] + coef[1] * l + coef[2] * N_TARGET - math.log2(STEP_SECONDS)
                )
                flat = (
                    coef[0]
                    + coef[1] * l
                    + coef[2] * N_MAX_MEASURED
                    - math.log2(STEP_SECONDS)
                )
                cells += [cell(full), cell(flat)]
            out.append(
                f"| {m} | {l} | "
                + (f"2^{calls}" if calls is not None else "—")
                + " | "
                + (
                    f"2^{budget}"
                    if budget is not None
                    else "none: LA alone exceeds rho"
                )
                + " | "
                + " | ".join(cells)
                + " |"
            )
    out.append("")
    out.append(
        f"Pollard rho on the `<-1, tau>` orbits: `2^{RHO_LOG2}` iterations, about "
        f"{2**RHO_LOG2 * STEP_SECONDS / 3.15e7:,.0f} core-years at the assumed rate.  "
        f"The budget for `m = 4, l = 29` is `2^12.2` iterations, about "
        f"{2**12.2 * STEP_SECONDS * 1e3:.1f} ms; for `m = 5, l = 28` it is `2^32.8`, about "
        f"{2**32.8 * STEP_SECONDS / 60:.0f} minutes."
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
    rows = load(paths)
    ok = [
        r
        for r in rows
        if r["status"] in ("sat", "solved")
        and r["verified"] == "True"
        and r["curve"] == "koblitz"
    ]
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in ok:
        groups[(r["engine"], int(r["m"]))].append(r)

    measured = measured_tables(rows, groups)
    fits_md, fits = fit_table(groups)
    extra = extrapolation_table(fits)

    print("## Measured: median solve seconds (solved / attempted)\n")
    print(measured)
    print("## Fits: log2(seconds) = a + c*l + d*n\n")
    print(fits_md)
    print(
        f"\n## Extrapolation to ECC2K-130 (n = {N_TARGET}), one PDP, log2 of rho iterations\n"
    )
    print(extra)

    if update:
        readme = Path(__file__).with_name("README.md")
        splice(readme, "MEASURED", measured)
        splice(readme, "FITS", fits_md)
        splice(readme, "EXTRAPOLATION", extra)
        print(f"\nupdated {readme}")


if __name__ == "__main__":
    main()
