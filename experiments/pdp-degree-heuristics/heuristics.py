#!/usr/bin/env python3
"""Calibrate and validate the factor-base heuristics against the measured receipts,
and carry the structure-only predictors to the ECC2K-130 field (n = 131).

    python3 heuristics.py results/*.jsonl --report REPORT.md --update-readme README.md

Measured rows come from profile.py receipts.  Everything computed for n = 131 is a
prediction from structure alone (product profiles, the linearization rank, the psi-free
yield formula) and is labelled as such.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "pdp-scaling"))

import gf2n  # noqa: E402

import macaulay  # noqa: E402
from factor_base import minimal_profile, product_profile, rank  # noqa: E402
from profile import predictions  # noqa: E402

FAMILY_ORDER = ["prefix", "geometric", "invariant", "normal", "kertrace", "random"]
STRUCTURED = ("prefix", "geometric")


def load(paths: list[Path]) -> list[dict]:
    cards = []
    for p in paths:
        for line in p.read_text().splitlines():
            if line.strip():
                cards.append(json.loads(line))
    return [c for c in cards if c.get("schema") == "pdp-degree-profile/1"]


def fmt(x, digits: int = 3) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        if x == 0:
            return "0"
        if abs(x) >= 1e4 or abs(x) < 1e-2:
            return f"{x:.{digits - 1}e}"
        return f"{x:.{digits}g}"
    return str(x)


def geomean(xs):
    xs = [x for x in xs if x]
    return math.exp(statistics.fmean(math.log(x) for x in xs)) if xs else None


def spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3 or len(set(a)) < 2 or len(set(b)) < 2:
        return None

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r

    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else None


# ---------------------------------------------------------------- per-card features
def features(c: dict, mode: str) -> dict:
    cell, st, pr, dg = c["cell"], c["structure"], c["predictions"], c["degrees"][mode]
    cost = c["cost"][mode]
    y = c["yield"]
    n = cell["n"]
    omega = st["omega"]
    return {
        "n": n, "m": cell["m"], "l": cell["l"], "N": cell["N"], "family": cell["family"], "seed": cell["seed"],
        "profile": st["product_profile"], "omega": omega, "omega_top": st["omega_top"],
        "excess": n - (omega - 1),
        "sym_unknowns": sum(st["product_profile"][: cell["m"]]),
        "semi_regular": pr["semi_regular_dreg"], "fall_adjusted": pr["fall_adjusted_dreg"],
        "p_base_pred": pr["p_base_refutation"], "expected": pr["expected_D_solve"],
        "D": dg["D_solve_mean"], "D_hist": dg["D_solve_hist"], "censored": dg["censored"],
        "base_rate": dg["base_refutations"] / c["counts"]["ordinary_queries"],
        "FFD": dg["FFD_mean"], "planted_D": dg["planted_D_solve_hist"],
        "ops": cost["ops_per_attempt_mean"], "ops_ci": cost["ops_per_attempt_ci95"],
        "ops_rel": cost["derived_ops_per_relation"], "best_abort": cost["best_abort"],
        "p_exact": (y["exact"] or {}).get("p_decomposable"), "p_pred": y["predicted"]["p_decomposable"],
        "e_exact": (y["exact"] or {}).get("expected_ordered"), "e_pred": y["predicted"]["expected_ordered"],
        "e_basic": y["predicted"]["basic_expected_ordered"],
        "B": c["factor_base"]["actual_usable_point_count"], "cols": c["factor_base"]["effective_columns"],
        "dreg_emp": (c["degrees"].get("homogeneous") or {}).get("D_reg_emp_mean"),
        "sat_cpu": (c.get("sat_engine") or {}).get("cpu_s_mean"),
        "workload": c["workload_id"],
    }


def by_cell(rows: list[dict]) -> dict[tuple, dict[str, list[dict]]]:
    out: dict[tuple, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        out[(r["m"], r["n"], r["l"])][r["family"]].append(r)
    return out


# ---------------------------------------------------------------- calibrated rule
def fit_threshold_rule(rows: list[dict]) -> dict:
    """Per m: D_solve ~ base + [excess < t1] + [excess < t2] + ..., thresholds fitted by
    least squares on the measured mean degree, with leave-one-n-out error."""
    out = {}
    for m in sorted({r["m"] for r in rows}):
        sub = [r for r in rows if r["m"] == m and r["D"] is not None and not r["censored"]]
        if len(sub) < 5:
            continue
        base = min(r["D"] for r in sub)
        cand = sorted({r["excess"] for r in sub})
        grid = [c + 0.5 for c in cand]

        def predict(rule, e):
            return rule["base"] + sum(1 for t in rule["thresholds"] if e < t)

        def fit(data):
            best = None
            for k in range(0, 4):
                for ts in _increasing(grid, k):
                    rule = {"base": base, "thresholds": list(ts)}
                    err = sum((predict(rule, r["excess"]) - r["D"]) ** 2 for r in data)
                    if best is None or err < best[0] - 1e-12:
                        best = (err, rule)
            return best[1]

        rule = fit(sub)
        loo = []
        for n in sorted({r["n"] for r in sub}):
            train = [r for r in sub if r["n"] != n]
            test = [r for r in sub if r["n"] == n]
            if not train or not test:
                continue
            rr = fit(train)
            loo += [abs(predict(rr, r["excess"]) - r["D"]) for r in test]
        fitted = [abs(predict(rule, r["excess"]) - r["D"]) for r in sub]
        out[m] = {"rule": rule, "mae_fit": statistics.fmean(fitted), "mae_leave_one_n_out": statistics.fmean(loo) if loo else None,
                  "cells": len(sub)}
    return out


def _increasing(grid, k):
    if k == 0:
        yield ()
        return
    if k > 3 or len(grid) > 40:
        grid = grid[:: max(1, len(grid) // 40)]
    import itertools

    for ts in itertools.combinations(sorted(grid, reverse=True), k):
        yield ts


# ---------------------------------------------------------------- n = 131 predictions
def n131_bases(F, family: str, l: int, seed: int) -> list[int]:
    n = F.n
    rng = random.Random(f"{family}|{n}|{l}|{seed}")
    if family == "prefix":
        return [1 << j for j in range(l)]
    if family == "geometric":
        c, g = rng.randrange(1, 1 << n), rng.randrange(2, 1 << n)
        return [F.mul(c, F.pow(g, j)) for j in range(l)]
    pred = (lambda x: F.trace(x) == 0) if family == "kertrace" else (lambda x: True)
    if family == "normal":
        while True:
            beta = rng.getrandbits(n)
            conj = [F.frob(beta, j) for j in range(n)]
            if rank(conj) == n:
                return conj[:l]
    while True:
        cand = []
        while len(cand) < l:
            x = rng.getrandbits(n)
            if x and pred(x):
                cand.append(x)
        if rank(cand) == l:
            return cand


def n131_predictions(ls=(8, 12, 16, 20, 24, 28), ms=(2, 3, 4, 5), families=("prefix", "geometric", "normal", "random")) -> list[dict]:
    """Structure-only cards for ECC2K-130's field (#E = 4r, r prime of 130 bits)."""
    F = gf2n.GF2n(131)
    order = 4 * 680564733841876926932320129493409985129
    out = []
    for fam in families:
        for l in ls:
            basis = n131_bases(F, fam, l, 1)
            prof = product_profile(F, basis, max(ms))
            for m in ms:
                N = m * l
                d = m * (m - 1)
                e_ord = (2.0**l) ** m / order
                row = {
                    "family": fam, "l": l, "m": m, "N": N,
                    "profile": prof[:m], "minimal": minimal_profile(131, l, m),
                    "sym_unknowns": sum(prof[:m]),
                    "semi_regular_direct": macaulay.semi_regular_dreg(N, [d] * 131) if N <= 200 else None,
                    "log2_expected_decompositions": math.log2(e_ord / math.factorial(m)),
                }
                if m == 2:
                    # omega = 1 + dim V + dim V^(2) for two summands (test_linearization_rank_for_two_summands)
                    struct = {"omega": 1 + prof[0] + prof[1], "omega_top": prof[1], "fallen_degree": 1, "system_degree": 2}
                    pred = predictions(131, 2, l, struct)
                    row["omega"] = struct["omega"]
                    row["excess"] = pred["linearization_excess"]
                    row["p_base_refutation"] = pred["p_base_refutation"]
                    row["expected_D_solve"] = pred["expected_D_solve"]
                out.append(row)
    return out


# ---------------------------------------------------------------- report
def matched_table(cells, m: int, mode: str, ns=None) -> list[str]:
    lines = [
        f"| n | l | N | family | dims V^(k) | ω | excess | P(dec) exact | D_solve {mode} | base refuted | ops/attempt | ops/relation |",
        "|--:|--:|--:|---|---|--:|--:|--:|---|--:|--:|--:|",
    ]
    for (mm, n, l), fams in sorted(cells.items()):
        if mm != m or (ns and n not in ns):
            continue
        for fam in FAMILY_ORDER:
            rows = fams.get(fam)
            if not rows:
                continue
            hist: dict[str, int] = defaultdict(int)
            for r in rows:
                for k, v in r["D_hist"].items():
                    hist[k] += v
            hs = " ".join(f"{k}:{v}" for k, v in sorted(hist.items(), key=lambda kv: (kv[0] == "None", kv[0])))
            lines.append(
                f"| {n} | {l} | {m * l} | {fam}{' ×' + str(len(rows)) if len(rows) > 1 else ''} | {rows[0]['profile'][:m + 1]} "
                f"| {fmt(statistics.fmean(r['omega'] for r in rows))} | {fmt(statistics.fmean(r['excess'] for r in rows))} "
                f"| {fmt(statistics.fmean(r['p_exact'] for r in rows if r['p_exact'] is not None)) if any(r['p_exact'] is not None for r in rows) else '—'} "
                f"| {hs} | {fmt(statistics.fmean(r['base_rate'] for r in rows), 2)} "
                f"| {fmt(geomean(r['ops'] for r in rows))} | {fmt(geomean(r['ops_rel'] for r in rows))} |"
            )
    return lines


def paired_summary(cells, mode: str) -> list[str]:
    """Structured (prefix, geometric) vs random on the same workload, per m."""
    lines = [
        "| m | cells | mean ΔD (random − structured) | cells with ΔD > 0 | cells with ΔD < 0 | geo-mean ops ratio random/structured | geo-mean yield ratio random/structured |",
        "|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for m in sorted({k[0] for k in cells}):
        dD, ratio, yratio = [], [], []
        for (mm, n, l), fams in cells.items():
            if mm != m or "random" not in fams:
                continue
            s = [r for f in STRUCTURED for r in fams.get(f, []) if r["D"] is not None and not r["censored"]]
            rnd = [r for r in fams["random"] if r["D"] is not None and not r["censored"]]
            if not s or not rnd:
                continue
            dD.append(statistics.fmean(r["D"] for r in rnd) - statistics.fmean(r["D"] for r in s))
            ratio.append(geomean(r["ops"] for r in rnd) / geomean(r["ops"] for r in s))
            ys, yr = [r["p_exact"] for r in s if r["p_exact"]], [r["p_exact"] for r in rnd if r["p_exact"]]
            if ys and yr:
                yratio.append(statistics.fmean(yr) / statistics.fmean(ys))
        if dD:
            lines.append(
                f"| {m} | {len(dD)} | {statistics.fmean(dD):+.2f} | {sum(1 for x in dD if x > 1e-9)} | {sum(1 for x in dD if x < -1e-9)} "
                f"| {fmt(geomean(ratio))} | {fmt(geomean(yratio))} |"
            )
    return lines


def predictor_table(rows_by_mode: dict[str, list[dict]]) -> list[str]:
    lines = [
        "| m | mode | cells | semi-regular D_reg MAE | fall-adjusted MAE | structure-only expected MAE | Spearman (expected vs measured, within cell) |",
        "|--:|---|--:|--:|--:|--:|--:|",
    ]
    for mode, rows in rows_by_mode.items():
        for m in sorted({r["m"] for r in rows}):
            sub = [r for r in rows if r["m"] == m and r["D"] is not None and not r["censored"]]
            if not sub:
                continue

            def mae(key):
                v = [abs(r[key] - r["D"]) for r in sub if r[key] is not None]
                return statistics.fmean(v) if v else None

            rhos = []
            for key, grp in _cells(sub).items():
                a = [r["expected"] for r in grp if r["expected"] is not None]
                b = [r["D"] for r in grp if r["expected"] is not None]
                rho = spearman(a, b)
                if rho is not None:
                    rhos.append(rho)
            lines.append(
                f"| {m} | {mode} | {len(sub)} | {fmt(mae('semi_regular'))} | {fmt(mae('fall_adjusted'))} | {fmt(mae('expected'))} "
                f"| {fmt(statistics.fmean(rhos)) if rhos else '—'} ({len(rhos)} cells) |"
            )
    return lines


def _cells(rows):
    out = defaultdict(list)
    for r in rows:
        out[(r["m"], r["n"], r["l"])].append(r)
    return out


def base_calibration(rows: list[dict], mode: str) -> list[str]:
    """Predicted base-degree refutation probability (from omega) against the measured rate."""
    bins = [(0.0, 0.05), (0.05, 0.3), (0.3, 0.7), (0.7, 0.95), (0.95, 1.01)]
    lines = [f"| predicted p (ω) | factor bases | mean predicted | mean measured ({mode}) |", "|---|--:|--:|--:|"]
    for lo, hi in bins:
        sub = [r for r in rows if lo <= r["p_base_pred"] < hi]
        if sub:
            lines.append(f"| [{lo:.2f}, {min(hi, 1):.2f}) | {len(sub)} | {statistics.fmean(r['p_base_pred'] for r in sub):.3f} | {statistics.fmean(r['base_rate'] for r in sub):.3f} |")
    return lines


def yield_table(rows: list[dict]) -> list[str]:
    lines = [
        "| m | factor bases | median exact/pred E[ordered] | 90% range | median exact/basic E[ordered] | 90% range |",
        "|--:|--:|--:|---|--:|---|",
    ]
    for m in sorted({r["m"] for r in rows}):
        sub = [r for r in rows if r["m"] == m and r["e_exact"] and r["e_pred"] and r["e_basic"]]
        if not sub:
            continue
        a = sorted(r["e_exact"] / r["e_pred"] for r in sub)
        b = sorted(r["e_exact"] / r["e_basic"] for r in sub)
        q = lambda v, p: v[min(len(v) - 1, int(p * len(v)))]  # noqa: E731
        lines.append(f"| {m} | {len(sub)} | {q(a, 0.5):.3f} | {q(a, 0.05):.2f}–{q(a, 0.95):.2f} | {q(b, 0.5):.3f} | {q(b, 0.05):.2f}–{q(b, 0.95):.2f} |")
    return lines


def n131_table(rows: list[dict]) -> list[str]:
    lines = [
        "| family | l | dims V^(k), k ≤ 5 | minimum | Σ_{k≤3} dim V^(k) | m = 2: ω | m = 2: excess | log2 E[decompositions], m = 2 / 3 / 4 / 5 |",
        "|---|--:|---|---|--:|--:|--:|---|",
    ]
    grouped = defaultdict(dict)
    for r in rows:
        grouped[(r["family"], r["l"])][r["m"]] = r
    for (fam, l), ms in grouped.items():
        top = ms[max(ms)]
        lines.append(
            f"| {fam} | {l} | {top['profile']} | {top['minimal']} | {sum(top['profile'][:3])} | {ms[2]['omega']} | {ms[2]['excess']} "
            f"| {' / '.join(f'{ms[m]['log2_expected_decompositions']:.1f}' for m in sorted(ms))} |"
        )
    return lines


def build_report(cards: list[dict]) -> dict[str, list[str]]:
    modes = sorted({m for c in cards for m in c["point_decomposition"].get("modes", ["xl"])})
    rows_by_mode = {mode: [features(c, mode) for c in cards if mode in c["degrees"]] for mode in modes}
    cells = {mode: by_cell(rows) for mode, rows in rows_by_mode.items()}
    sections: dict[str, list[str]] = {}
    sections["PAIRED"] = []
    for mode in modes:
        sections["PAIRED"] += [f"**{mode}**", "", *paired_summary(cells[mode], mode), ""]
    sections["PREDICTORS"] = predictor_table(rows_by_mode)
    rules = {mode: fit_threshold_rule(rows) for mode, rows in rows_by_mode.items()}
    rl = ["| m | mode | cells | fitted rule on excess e = n − (ω − 1) | MAE (fit) | MAE (leave one n out) |", "|--:|---|--:|---|--:|--:|"]
    for mode, per_m in rules.items():
        for m, res in per_m.items():
            ts = res["rule"]["thresholds"]
            rule = f"D = {res['rule']['base']}" + "".join(f" + [e < {t:g}]" for t in ts)
            rl.append(f"| {m} | {mode} | {res['cells']} | {rule} | {res['mae_fit']:.3f} | {fmt(res['mae_leave_one_n_out'])} |")
    sections["RULES"] = rl
    sections["BASE"] = base_calibration([r for r in rows_by_mode[modes[0]] if r["m"] == 2], modes[0])
    sections["YIELD"] = yield_table(rows_by_mode[modes[0]])
    for mode in modes:
        for m in sorted({r["m"] for r in rows_by_mode[mode]}):
            sections[f"MATCHED_M{m}_{mode.upper()}"] = matched_table(cells[mode], m, mode)
    dregs = [r for r in rows_by_mode[modes[0]] if r["dreg_emp"] is not None]
    dl = ["| m | l | factor bases | homogeneous D_reg (measured) | D_solve xl | D_solve mxl | semi-regular D_reg |", "|--:|--:|--:|--:|--:|--:|--:|"]
    for (m, l) in sorted({(r["m"], r["l"]) for r in dregs}):
        sub = [r for r in dregs if r["m"] == m and r["l"] == l]
        mx = [features(c, "mxl")["D"] for c in cards if c["cell"]["m"] == m and c["cell"]["l"] == l and "mxl" in c["degrees"]
              and (c["degrees"].get("homogeneous") or {}).get("D_reg_emp_mean") is not None]
        dl.append(f"| {m} | {l} | {len(sub)} | {fmt(statistics.fmean(r['dreg_emp'] for r in sub))} | {fmt(statistics.fmean(r['D'] for r in sub if r['D']))} "
                  f"| {fmt(statistics.fmean(v for v in mx if v)) if any(mx) else '—'} | {fmt(statistics.fmean(r['semi_regular'] for r in sub if r['semi_regular']))} |")
    sections["DREG"] = dl
    return sections


def update_markers(text: str, sections: dict[str, list[str]]) -> str:
    for name, lines in sections.items():
        pat = re.compile(rf"(<!-- BEGIN {name} -->\n).*?(<!-- END {name} -->)", re.S)
        text = pat.sub(lambda mt: mt.group(1) + "\n".join(lines) + "\n" + mt.group(2), text)
    return text


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="*", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--update-readme", type=Path)
    ap.add_argument("--n131", action="store_true", help="also compute the n = 131 structure-only table")
    ap.add_argument("--n131-out", type=Path, default=HERE / "results" / "n131_structure.json")
    args = ap.parse_args()
    cards = load(args.results)
    sections = build_report(cards) if cards else {}
    if args.n131:
        rows = n131_predictions()
        args.n131_out.write_text(json.dumps(rows, indent=1) + "\n")
    if args.n131_out.exists():
        sections["N131"] = n131_table(json.loads(args.n131_out.read_text()))
    if args.report:
        body = ["# Measured factor-base profiles", "", "Generated by `heuristics.py`; see README.md for definitions.", ""]
        for name, lines in sections.items():
            body += [f"## {name}", "", *lines, ""]
        args.report.write_text("\n".join(body))
    if args.update_readme:
        args.update_readme.write_text(update_markers(args.update_readme.read_text(), sections))
    if not args.report and not args.update_readme:
        for name, lines in sections.items():
            print(f"## {name}\n")
            print("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
