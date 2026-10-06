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

FAMILY_ORDER = ["prefix", "geometric", "geomtrace", "invariant", "normal", "kertrace", "random"]
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
def corrected_prediction(c: dict) -> dict:
    """The psi yield prediction without the tuples that sum to O.  Receipts written before
    relations.zero_sum_tuples existed counted the |F| pairs (P, -P) for m = 2; for m = 3 the
    zero-sum triples are a 1/r fraction and are left in."""
    pred = dict(c["yield"]["predicted"])
    if "zero_sum_tuples" not in pred and c["cell"]["m"] == 2:
        T = pred["psi_tuples"] - c["factor_base"]["geometric_point_count"]
        r = c["curve"]["subgroup_order"]
        pred["psi_tuples"] = T
        pred["expected_ordered"] = T / r
        pred["expected_unordered"] = T / (2 * r)
        pred["p_decomposable"] = 1 - math.exp(-T / (2 * r))
    return pred


def features(c: dict, mode: str) -> dict:
    cell, st, pr, dg = c["cell"], c["structure"], c["predictions"], c["degrees"][mode]
    cost = c["cost"][mode]
    y = {**c["yield"], "predicted": corrected_prediction(c)}
    n = cell["n"]
    omega = st["omega"]
    return {
        "form": "sym" if cell.get("formulation", "direct") != "direct" else "direct",
        "split_checks": c["counts"].get("split_checks_mean"),
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
        "decomposable_targets": (y["exact"] or {}).get("decomposable_targets"),
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
        out[(r["form"], r["m"], r["n"], r["l"])][r["family"]].append(r)
    return out


# ---------------------------------------------------------------- calibrated rule
_RULE_CACHE: dict = {}


def fit_threshold_rule(rows: list[dict]) -> dict:
    """Per m: D_solve ~ base + [excess < t1] + [excess < t2] + ..., thresholds fitted by
    least squares on the measured mean degree, with leave-one-n-out error."""
    key = tuple(sorted((r["form"], r["m"], r["n"], r["l"], r["family"], r["seed"], r["D"], r["excess"]) for r in rows if r["D"] is not None))
    if key in _RULE_CACHE:
        return _RULE_CACHE[key]
    _RULE_CACHE[key] = out = {}
    for m in sorted({r["m"] for r in rows}):
        sub = [r for r in rows if r["m"] == m and r["D"] is not None and not r["censored"]]
        if len(sub) < 5:
            continue
        bases = sorted({math.floor(min(r["D"] for r in sub)), math.ceil(min(r["D"] for r in sub))})
        cand = sorted({r["excess"] for r in sub})
        grid = [c + 0.5 for c in cand]

        def predict(rule, e):
            return rule["base"] + sum(1 for t in rule["thresholds"] if e < t)

        def fit(data):
            import itertools

            import numpy as np

            e = np.array([r["excess"] for r in data], dtype=float)
            d = np.array([r["D"] for r in data], dtype=float)
            ts = np.array(sorted(grid, reverse=True) if len(grid) <= 40 else sorted(grid, reverse=True)[:: max(1, len(grid) // 40)])
            ind = (e[None, :] < ts[:, None]).astype(float)
            best = None
            for k in range(0, 4):
                combos = list(itertools.combinations(range(len(ts)), k))
                if not combos:
                    continue
                if k == 0:
                    sums = np.zeros((1, len(e)))
                else:
                    sums = np.stack([ind[list(c)].sum(axis=0) for c in combos])
                for base in bases:
                    err = ((base + sums - d[None, :]) ** 2).sum(axis=1)
                    i = int(np.argmin(err))
                    if best is None or err[i] < best[0] - 1e-12:
                        best = (float(err[i]), {"base": base, "thresholds": [float(ts[j]) for j in combos[i]]})
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
def _hist_str(rows: list[dict]) -> str:
    hist: dict[str, int] = defaultdict(int)
    for r in rows:
        for k, v in r["D_hist"].items():
            hist[k] += v
    return " ".join(f"{k}:{v}" for k, v in sorted(hist.items(), key=lambda kv: (kv[0] == "None", kv[0])))


def matched_table(cells, form: str, m: int, mode: str, ns=None, ls=None) -> list[str]:
    extra = " splits/query |" if form == "sym" else ""
    lines = [
        f"| n | l | unknowns | family | dims V^(k) | ω | excess | P(dec) exact | D_solve {mode} | base refuted | ops/attempt |{extra} ops/relation |",
        "|--:|--:|--:|---|---|--:|--:|--:|---|--:|--:|" + ("--:|" if form == "sym" else "") + "--:|",
    ]
    for (ff, mm, n, l), fams in sorted(cells.items()):
        if ff != form or mm != m or (ns and n not in ns) or (ls and l not in ls):
            continue
        for fam in FAMILY_ORDER:
            rows = fams.get(fam)
            if not rows:
                continue
            p_ex = [r["p_exact"] for r in rows if r["p_exact"] is not None]
            split = f" {fmt(statistics.fmean(r['split_checks'] for r in rows if r['split_checks'] is not None))} |" if form == "sym" else ""
            lines.append(
                f"| {n} | {l} | {rows[0]['N']} | {fam}{' ×' + str(len(rows)) if len(rows) > 1 else ''} | {rows[0]['profile'][:m + 1]} "
                f"| {fmt(statistics.fmean(r['omega'] for r in rows))} | {fmt(statistics.fmean(r['excess'] for r in rows))} "
                f"| {fmt(statistics.fmean(p_ex)) if p_ex else '—'} | {_hist_str(rows)} | {fmt(statistics.fmean(r['base_rate'] for r in rows), 2)} "
                f"| {fmt(geomean(r['ops'] for r in rows))} |{split} {fmt(geomean(r['ops_rel'] for r in rows))} |"
            )
    return lines


def paired_summary(cells, form: str, mode: str) -> list[str]:
    """Structured (prefix, geometric) against random bases on the same workload."""
    split_head = " cells where random needs more / fewer splits per query |" if form == "sym" else ""
    lines = [
        f"| m | cells | mean ΔD (random − structured) | ΔD > 0 | ΔD < 0 | ops/attempt ratio | ops/relation ratio | P(dec) ratio |{split_head}",
        "|--:|--:|--:|--:|--:|--:|--:|--:|" + ("---|" if form == "sym" else ""),
    ]
    for m in sorted({k[1] for k in cells if k[0] == form}):
        dD, ratio, rel, yratio, ss, sr = [], [], [], [], [], []
        for (ff, mm, n, l), fams in cells.items():
            if ff != form or mm != m or "random" not in fams:
                continue
            s = [r for f in STRUCTURED for r in fams.get(f, []) if r["D"] is not None and not r["censored"]]
            rnd = [r for r in fams["random"] if r["D"] is not None and not r["censored"]]
            if not s or not rnd:
                continue
            dD.append(statistics.fmean(r["D"] for r in rnd) - statistics.fmean(r["D"] for r in s))
            ratio.append(geomean(r["ops"] for r in rnd) / geomean(r["ops"] for r in s))
            a, b = geomean(r["ops_rel"] for r in rnd), geomean(r["ops_rel"] for r in s)
            if a and b:
                rel.append(a / b)
            ys, yr = [r["p_exact"] for r in s if r["p_exact"]], [r["p_exact"] for r in rnd if r["p_exact"]]
            if ys and yr:
                yratio.append(statistics.fmean(yr) / statistics.fmean(ys))
            if form == "sym":
                ss.append(statistics.fmean(r["split_checks"] or 0 for r in s))
                sr.append(statistics.fmean(r["split_checks"] or 0 for r in rnd))
        if dD:
            more = sum(1 for a, b in zip(ss, sr) if b > a + 1e-9)
            fewer = sum(1 for a, b in zip(ss, sr) if b < a - 1e-9)
            split = f" {more} / {fewer} |" if form == "sym" else ""
            lines.append(
                f"| {m} | {len(dD)} | {statistics.fmean(dD):+.2f} | {sum(1 for x in dD if x > 1e-9)} | {sum(1 for x in dD if x < -1e-9)} "
                f"| {fmt(geomean(ratio))} | {fmt(geomean(rel))} | {fmt(geomean(yratio))} |{split}"
            )
    return lines


def regime_summary(cells, rows_by_mode, form: str, mode: str, m: int = 2) -> list[str]:
    """Structured against random bases, grouped by how many degrees apart the fitted
    excess rule places them (0: same side of every threshold)."""
    rules = fit_threshold_rule([r for r in rows_by_mode[mode] if r["form"] == form])
    if m not in rules:
        return []
    rule = rules[m]["rule"]
    pred = lambda e: rule["base"] + sum(1 for t in rule["thresholds"] if e < t)  # noqa: E731
    groups: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for (ff, mm, n, l), fams in cells.items():
        if ff != form or mm != m or "random" not in fams:
            continue
        s = [r for f in STRUCTURED for r in fams.get(f, []) if r["D"] is not None and not r["censored"]]
        rnd = [r for r in fams["random"] if r["D"] is not None and not r["censored"]]
        if not s or not rnd:
            continue
        gap = round(statistics.fmean(pred(r["excess"]) for r in rnd) - statistics.fmean(pred(r["excess"]) for r in s))
        g = groups[gap]
        g["cells"].append((n, l))
        g["dD"].append(statistics.fmean(r["D"] for r in rnd) - statistics.fmean(r["D"] for r in s))
        g["ops"].append(geomean(r["ops"] for r in rnd) / geomean(r["ops"] for r in s))
        a, b = geomean(r["ops_rel"] for r in rnd), geomean(r["ops_rel"] for r in s)
        if a and b:
            g["rel"].append(a / b)
    lines = [
        f"| predicted degree gap | cells | measured mean ΔD | ops/attempt ratio: geo-mean (min–max) | ops/relation ratio: geo-mean (min–max) |",
        "|--:|--:|--:|---|---|",
    ]
    for gap in sorted(groups):
        g = groups[gap]
        rel = f"{fmt(geomean(g['rel']))} ({fmt(min(g['rel']))}–{fmt(max(g['rel']))})" if g["rel"] else "—"
        lines.append(
            f"| {gap} | {len(g['cells'])} | {statistics.fmean(g['dD']):+.2f} | {fmt(geomean(g['ops']))} ({fmt(min(g['ops']))}–{fmt(max(g['ops']))}) | {rel} |"
        )
    return lines


def predictor_table(rows_by_mode: dict[str, list[dict]]) -> list[str]:
    lines = [
        "| formulation | m | mode | factor bases | semi-regular D_reg MAE | fall-adjusted MAE | structure-only expected MAE | within-cell Spearman |",
        "|---|--:|---|--:|--:|--:|--:|--:|",
    ]
    for mode, rows in rows_by_mode.items():
        for form, m in sorted({(r["form"], r["m"]) for r in rows}):
            sub = [r for r in rows if r["form"] == form and r["m"] == m and r["D"] is not None and not r["censored"]]
            if not sub:
                continue

            def mae(key):
                v = [abs(r[key] - r["D"]) for r in sub if r[key] is not None]
                return statistics.fmean(v) if v else None

            rhos = []
            for grp in _cells(sub).values():
                a = [r["expected"] for r in grp if r["expected"] is not None]
                b = [r["D"] for r in grp if r["expected"] is not None]
                rho = spearman(a, b)
                if rho is not None:
                    rhos.append(rho)
            lines.append(
                f"| {form} | {m} | {mode} | {len(sub)} | {fmt(mae('semi_regular'))} | {fmt(mae('fall_adjusted'))} | {fmt(mae('expected'))} "
                f"| {fmt(statistics.fmean(rhos)) if rhos else '—'} ({len(rhos)} cells) |"
            )
    return lines


def _cells(rows):
    out = defaultdict(list)
    for r in rows:
        out[(r["form"], r["m"], r["n"], r["l"])].append(r)
    return out


def base_calibration(rows_by_mode: dict[str, list[dict]], m: int = 2) -> list[str]:
    """Predicted base-degree refutation probability (from omega) against the measured rates."""
    modes = list(rows_by_mode)
    bins = [(0.0, 0.05), (0.05, 0.3), (0.3, 0.7), (0.7, 0.95), (0.95, 1.01)]
    lines = [
        "| predicted p (from ω) | factor bases | mean predicted | " + " | ".join(f"measured {mode}" for mode in modes) + " |",
        "|---|--:|--:|" + "--:|" * len(modes),
    ]
    keyed = {mode: {(r["n"], r["l"], r["family"], r["seed"]): r for r in rows if r["m"] == m and r["form"] == "direct"} for mode, rows in rows_by_mode.items()}
    first = keyed[modes[0]]
    for lo, hi in bins:
        keys = [k for k, r in first.items() if lo <= r["p_base_pred"] < hi]
        if keys:
            meas = " | ".join(f"{statistics.fmean(keyed[mode][k]['base_rate'] for k in keys if k in keyed[mode]):.3f}" for mode in modes)
            lines.append(f"| [{lo:.2f}, {min(hi, 1):.2f}) | {len(keys)} | {statistics.fmean(first[k]['p_base_pred'] for k in keys):.3f} | {meas} |")
    return lines


def rules_table(rows_by_mode: dict[str, list[dict]]) -> list[str]:
    lines = ["| formulation | m | mode | factor bases | fitted rule on excess e = n − (ω − 1) | MAE (fit) | MAE (leave one n out) |",
             "|---|--:|---|--:|---|--:|--:|"]
    for mode, rows in rows_by_mode.items():
        for form in sorted({r["form"] for r in rows}):
            for m, res in fit_threshold_rule([r for r in rows if r["form"] == form]).items():
                rule = f"D = {res['rule']['base']}" + "".join(f" + [e < {t:g}]" for t in res["rule"]["thresholds"])
                lines.append(f"| {form} | {m} | {mode} | {res['cells']} | {rule} | {res['mae_fit']:.3f} | {fmt(res['mae_leave_one_n_out'])} |")
    return lines


def yield_table(rows: list[dict], min_decomposable: int = 30) -> list[str]:
    """Ratios exact/prediction as median (5%–95%) over factor bases with enough decomposable
    targets for the realized yield to mean something."""
    lines = [
        f"| m | factor bases (≥ {min_decomposable} decomposable targets) | E[#decomp]: exact / ψ-class count | E[#decomp]: exact / naive |F|^m/#E | P(decomposable): exact / Poisson from ψ count |",
        "|--:|--:|---|---|---|",
    ]
    seen = {}
    for r in rows:
        seen[(r["m"], r["n"], r["l"], r["family"], r["seed"])] = r
    rows = [r for r in seen.values() if (r["decomposable_targets"] or 0) >= min_decomposable]
    q = lambda v, p: v[min(len(v) - 1, int(p * len(v)))]  # noqa: E731
    span = lambda v: f"{q(v, 0.5):.3f} ({q(v, 0.05):.2f}–{q(v, 0.95):.2f})"  # noqa: E731
    for m in sorted({r["m"] for r in rows}):
        sub = [r for r in rows if r["m"] == m and r["e_exact"] and r["e_pred"] and r["e_basic"] and r["p_pred"]]
        if not sub:
            continue
        a = sorted(r["e_exact"] / r["e_pred"] for r in sub)
        b = sorted(r["e_exact"] / r["e_basic"] for r in sub)
        c = sorted(r["p_exact"] / r["p_pred"] for r in sub)
        lines.append(f"| {m} | {len(sub)} | {span(a)} | {span(b)} | {span(c)} |")
    return lines


def dreg_table(cards: list[dict]) -> list[str]:
    lines = ["| m | l | factor bases | homogeneous D_reg (measured) | D_solve xl | D_solve mxl | semi-regular D_reg |",
             "|--:|--:|--:|--:|--:|--:|--:|"]
    groups = defaultdict(list)
    for c in cards:
        h = (c["degrees"].get("homogeneous") or {}).get("D_reg_emp_mean")
        if h is not None and c["cell"].get("formulation", "direct") == "direct":
            groups[(c["cell"]["m"], c["cell"]["l"])].append(c)
    for (m, l), cs in sorted(groups.items()):
        x = [c["degrees"]["xl"]["D_solve_mean"] for c in cs if c["degrees"]["xl"]["D_solve_mean"]]
        mx = [c["degrees"]["mxl"]["D_solve_mean"] for c in cs if c["degrees"].get("mxl", {}).get("D_solve_mean")]
        lines.append(
            f"| {m} | {l} | {len(cs)} | {fmt(statistics.fmean(c['degrees']['homogeneous']['D_reg_emp_mean'] for c in cs))} "
            f"| {fmt(statistics.fmean(x)) if x else '—'} | {fmt(statistics.fmean(mx)) if mx else '—'} "
            f"| {fmt(statistics.fmean(c['predictions']['semi_regular_dreg'] for c in cs if c['predictions']['semi_regular_dreg']))} |"
        )
    return lines


def sat_table(rows: list[dict]) -> list[str]:
    lines = ["| m | cells | geo-mean CryptoMiniSat CPU ratio random/structured | cells where random is slower |", "|--:|--:|--:|--:|"]
    for m in sorted({r["m"] for r in rows}):
        ratios = []
        for grp in _cells([r for r in rows if r["m"] == m and r["form"] == "direct" and r["sat_cpu"]]).values():
            s = [r["sat_cpu"] for r in grp if r["family"] in STRUCTURED]
            rnd = [r["sat_cpu"] for r in grp if r["family"] == "random"]
            if s and rnd:
                ratios.append(geomean(rnd) / geomean(s))
        if ratios:
            lines.append(f"| {m} | {len(ratios)} | {fmt(geomean(ratios))} | {sum(1 for x in ratios if x > 1)} |")
    return lines


def collection_table(runs: list[dict]) -> list[str]:
    lines = ["| n | m | l | family | seed | columns / achievable rank | attempts | yield observed (exact) | ops/novel row | at 50% rank: projected ± sd | actual remaining | descents verified (attempts) |",
             "|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|--:|---|"]
    for r in sorted(runs, key=lambda r: (r["cell"]["m"], r["cell"]["n"], r["cell"]["l"], r["cell"]["family"], r["cell"].get("workload_seed", 1))):
        c, mon = r["cell"], r["monitor"]
        target = r.get("achievable_rank") or r["effective_columns"]
        snaps = r.get("snapshots", [])
        half = next((s for s in snaps if s["rank"] >= target / 2 and s["projected_attempts"]), None)
        proj = "—"
        if half:
            proj = fmt(half["projected_attempts"]) + (f" ± {fmt(half['projected_sd'])}" if half.get("projected_sd") else "")
        ds = r.get("descents", [])
        desc = f"{sum(1 for d in ds if d['verified'])}/{len(ds)} ({', '.join(str(d['attempts']) for d in ds)})" if ds else "—"
        if not r.get("collection_complete", True):
            desc = f"incomplete at rank {r['final_rank']}"
        lines.append(
            f"| {c['n']} | {c['m']} | {c['l']} | {c['family']} | {c.get('workload_seed', 1)} | {r['effective_columns']} / {target} | {mon['attempts']} "
            f"| {fmt(mon['yield_per_attempt'])} ({fmt((r['exact_yield'] or {}).get('p_decomposable'))}) "
            f"| {fmt(mon['ops_per_novel_row'])} | {proj} | {mon['attempts'] - half['attempt'] if half else '—'} | {desc} |"
        )
    return lines


def projection_calibration(runs: list[dict]) -> list[str]:
    """z = (actual remaining - projected) / sd for the projection made at half the target rank."""
    zs = []
    for r in runs:
        target = r.get("achievable_rank") or r["effective_columns"]
        half = next((s for s in r.get("snapshots", []) if s["rank"] >= target / 2 and s["projected_attempts"] and s.get("projected_sd")), None)
        if half and r.get("collection_complete", True):
            zs.append((r["monitor"]["attempts"] - half["attempt"] - half["projected_attempts"]) / half["projected_sd"])
    if not zs:
        return []
    return [
        "| runs with a projection sd | mean z | median z | abs(z) < 1 | abs(z) < 2 |",
        "|--:|--:|--:|--:|--:|",
        f"| {len(zs)} | {statistics.fmean(zs):+.2f} | {statistics.median(zs):+.2f} | {sum(1 for z in zs if abs(z) < 1)} | {sum(1 for z in zs if abs(z) < 2)} |",
    ]


def n131_table(rows: list[dict]) -> list[str]:
    lines = [
        "| family | l | dims V^(k), k ≤ 5 | minimum possible | Σ_{k≤3} dim V^(k) | m = 2: ω | m = 2: excess | log2 E[decompositions], m = 2 / 3 / 4 / 5 |",
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


def build_report(cards: list[dict], runs: list[dict] | None = None) -> dict[str, list[str]]:
    modes = sorted({m for c in cards for m in c["point_decomposition"].get("modes", ["xl"])})
    rows_by_mode = {mode: [features(c, mode) for c in cards if mode in c["degrees"]] for mode in modes}
    cells = {mode: by_cell(rows) for mode, rows in rows_by_mode.items()}
    forms = sorted({r["form"] for rows in rows_by_mode.values() for r in rows})
    sections: dict[str, list[str]] = {}
    for form in forms:
        key = "PAIRED" if form == "direct" else "PAIRED_SYM"
        sections[key] = []
        for mode in modes:
            sections[key] += [f"**{mode}**", "", *paired_summary(cells[mode], form, mode), ""]
    sections["REGIME"] = []
    for mode in modes:
        sections["REGIME"] += [f"**{mode}**, two summands", "", *regime_summary(cells[mode], rows_by_mode, "direct", mode), ""]
    sections["PREDICTORS"] = predictor_table(rows_by_mode)
    sections["RULES"] = rules_table(rows_by_mode)
    sections["BASE"] = base_calibration(rows_by_mode)
    sections["YIELD"] = yield_table(rows_by_mode[modes[0]])
    sections["DREG"] = dreg_table(cards)
    sections["SAT"] = sat_table(rows_by_mode[modes[0]])
    for form in forms:
        for mode in modes:
            for m in sorted({r["m"] for r in rows_by_mode[mode] if r["form"] == form}):
                sections[f"MATCHED_{form.upper()}_M{m}_{mode.upper()}"] = matched_table(cells[mode], form, m, mode)
    if "mxl" in cells:
        sections["SEL_M2"] = matched_table(cells["mxl"], "direct", 2, "mxl", ns=[23, 41], ls=[6, 7, 8])
        sections["SEL_M3"] = matched_table(cells["mxl"], "direct", 3, "mxl", ns=[31, 47], ls=[3, 4])
        if "sym" in forms:
            sections["SEL_SYM_M2"] = matched_table(cells["mxl"], "sym", 2, "mxl", ns=[19, 23], ls=[5, 6, 7])
            sections["SEL_SYM_M3"] = matched_table(cells["mxl"], "sym", 3, "mxl", ns=[23, 31, 47], ls=[3, 4])
    if runs:
        sections["COLLECT"] = collection_table(runs)
        sections["COLLECT_CAL"] = projection_calibration(runs)
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
    runs = [json.loads(line) for p in args.results for line in p.read_text().splitlines()
            if line.strip() and json.loads(line).get("schema") == "pdp-collection-run/1"]
    sections = build_report(cards, runs) if cards else {}
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
