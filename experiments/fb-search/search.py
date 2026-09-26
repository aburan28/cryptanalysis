#!/usr/bin/env python3
"""Predict the end-to-end cost of an index-calculus candidate from its factor base, and search
factor bases (family, dimension, seed) by that prediction.

    python3 search.py scan --n 19 --l 5 --families geometric geomtraceu prefix random kertrace --seeds 1-64
    python3 search.py select results/scan-n19m2.jsonl --per-family 3 --out selected.json
    python3 search.py check selected.json ../ic-bench/out/search.jsonl

The model (m = 2).  A collection run draws ordinary queries R = [k]G, k uniform, and adds every
verified two-point decomposition of R to an echelon form mod r until the achievable rank.  The
decompositions of every subgroup point are enumerable from the factor base (pair sums whose
psi-component vanishes), so the collection's query count has an exact law:

  * a query is decomposable with probability p_dec = |D| / (r - 1), D the decomposable points;
  * a decomposable query is uniform on D and contributes all of its rows.

`rank_process` samples that law directly (Monte Carlo over draws from D with geometric gaps) and
returns the mean and sd of the queries to the achievable rank.  Coverage of every column (the
coupon bound in ../pdp-degree-heuristics/monitor.py) is necessary but not sufficient: a row joins
two columns, and a component of the column graph is determined only once it carries a cycle.
Descent of each target is geometric with success probability p_dec.

Cost.  The per-query price is measured, not modelled: `probe` runs monitor.collect on an
independent probe query stream under opcount and prices the counters with the ic-bench
calibration.  Setup, factor-base and precompute costs come from the same probe.  The predicted
cold total for T targets is

    fixed + c_query * (E[collection queries] + T / p_dec)

in reference picoseconds (rps).  Each scored base is labelled with the AGENTS.md IC1 candidate ID
ic-bench assigns it (same manifest, same hash), so predictions and measured runs share a key.
Every predicted field is a prediction (`kind: prediction`); `check` sets measured runs beside it.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent / "ic-bench"
PDP = HERE.parent / "pdp-degree-heuristics"
sys.path.insert(0, str(PDP))
sys.path.insert(0, str(BENCH))

import bench  # noqa: E402
import kernel  # noqa: E402
import opcount  # noqa: E402
from calibrate import weights_for  # noqa: E402
from factor_base import FactorBase, minimal_profile, product_profile  # noqa: E402
from monitor import RankTracker, achievable_rank, column_hit_rates, coupon_time  # noqa: E402
from toycurve import ToyCurve, canonical, sha256_hex  # noqa: E402

SCHEMA = "fb-search-score/1"
RESULTS = HERE / "results"
SELECTED = HERE / "selected.json"


# ------------------------------------------------------------------ exact decomposition table
def decomposition_lookup(fb: FactorBase) -> dict[tuple[int, int], list[dict[int, int]]]:
    """Every decomposable nonidentity subgroup point -> the distinct relation rows (folded column ->
    coefficient mod r) of its two-point decompositions, exactly as the collector adds them.  A row
    that folds to zero (P and its own image) still makes the point decomposable, so its list may
    be empty."""
    C, K = fb.curve, fb.curve.K
    px, py = C.psi(fb.xs, fb.ys)
    sx, sy = K.pair_sums(fb.xs, fb.ys)
    qx, _ = K.pair_sums(px, py)
    ok = (qx == np.uint64(kernel.INF_X)) & (sx != np.uint64(kernel.INF_X))
    i, j = np.triu_indices(len(fb.xs))
    table: dict[tuple[int, int], set] = {}
    r = C.r
    for a, b, x, y in zip(i[ok].tolist(), j[ok].tolist(), sx[ok].tolist(), sy[ok].tolist()):
        row: dict[int, int] = {}
        for k in (a, b):
            if fb.col_of[k] >= 0:
                col = int(fb.col_of[k])
                row[col] = (row.get(col, 0) + int(fb.col_coeff[k])) % r
        rows = table.setdefault((x, y), set())
        row = {c: v for c, v in row.items() if v}
        if row:
            rows.add(tuple(sorted(row.items())))
    return {pt: [dict(t) for t in sorted(s)] for pt, s in table.items()}


def decomposition_table(fb: FactorBase) -> tuple[int, list[list[dict[int, int]]]]:
    """(|D|, rows of each decomposable point)."""
    table = decomposition_lookup(fb)
    return len(table), list(table.values())


def replay_workload(fb: FactorBase, workload: dict, target_rank: int | None = None,
                    max_attempts: int = 200_000) -> dict:
    """The exact query counts monitor.collect makes on an ic-bench workload, assuming a complete PDP
    solver (every decomposition of every query found; the Macaulay closure has no budget failures at
    these sizes).  Replays the workload's query and rerandomization streams through the lookup."""
    C = fb.curve
    table = decomposition_lookup(fb)
    if target_rank is None:
        target_rank = achievable_rank(fb, 2)
    saved, opcount.COUNTS = opcount.COUNTS, None
    try:
        rng = random.Random(workload["query_stream"])
        t = RankTracker(fb.effective_columns, C.r)
        q = d = 0
        while t.rank < target_rank and q < max_attempts:
            q += 1
            k, R = C.random_subgroup_point(rng)
            if R in table:
                d += 1
                for row in table[R]:
                    t.add(row, k)
        descents = []
        if t.rank >= target_rank:
            for i, (_, qx, qy) in enumerate(workload["targets"]):
                arng = random.Random(f"{workload['rerandomization_stream']}|{i}")
                tries = 0
                while tries < max_attempts:
                    tries += 1
                    a = arng.randrange(1, C.r)
                    Qa = C.K.add((qx, qy), C.K.smul(C.G, a))
                    if Qa[0] != kernel.INF_X and table.get(Qa):
                        break
                descents.append(tries)
    finally:
        opcount.COUNTS = saved
    return {"collection_queries": q, "decomposable_queries": d, "final_rank": t.rank,
            "descent_attempts": descents, "complete": t.rank >= target_rank}


def rank_process(fb: FactorBase, target_rank: int, runs: int = 400, seed: str = "") -> dict:
    """Queries to reach target_rank under the exact collection law (see module docstring)."""
    C = fb.curve
    n_dec, rows = decomposition_table(fb)
    p = n_dec / (C.r - 1)
    if p == 0 or target_rank == 0:
        return {"p_decomposable": p, "decomposable_targets": n_dec, "mean": None if target_rank else 0.0,
                "sd": None, "runs": 0}
    rng = random.Random(f"fbsearch-rank|{fb.digest}|{target_rank}|{seed}")
    log1p = math.log1p(-p)
    queries, draws = [], []
    saved, opcount.COUNTS = opcount.COUNTS, None
    try:
        for _ in range(runs):
            t = RankTracker(fb.effective_columns, C.r)
            q = d = 0
            while t.rank < target_rank:
                q += 1 + int(math.log(1.0 - rng.random()) / log1p)
                d += 1
                for row in rows[rng.randrange(n_dec)]:
                    t.add(row, 0)
            queries.append(q)
            draws.append(d)
    finally:
        opcount.COUNTS = saved
    queries.sort()
    return {
        "p_decomposable": p,
        "decomposable_targets": n_dec,
        "rows_per_decomposable_target": statistics.fmean(len(r) for r in rows),
        "mean": statistics.fmean(queries),
        "sd": statistics.stdev(queries) if runs > 1 else 0.0,
        "quantiles": {"p10": queries[runs // 10], "p50": queries[runs // 2], "p90": queries[9 * runs // 10]},
        "decomposable_draws_mean": statistics.fmean(draws),
        "runs": runs,
    }


# ------------------------------------------------------------------ measured per-query price
def probe_workload(curve: ToyCurve, index: int) -> tuple[str, dict]:
    """A probe query stream disjoint from every ic-bench workload (no targets)."""
    record = {
        "schema": "fb-search-probe-workload/1",
        "curve_id": curve.curve_id,
        "subgroup_order": str(curve.r),
        "prng": "CPython random.Random seeded with the string (version-2 seeding)",
        "query_law": "R = [k]G with k uniform on [1, r-1], drawn in order from query_stream",
        "query_stream": f"fbsearch-probe|{curve.curve_id}|{index}",
        "targets": [],
        "target_count": 0,
        "rerandomization_stream": f"fbsearch-probe-descent|{curve.curve_id}|{index}",
        "cache_state": "cold",
        "seed": index,
    }
    return sha256_hex(record)[:12], record


def probe(curve: ToyCurve, family: str, l: int, seed: int, m: int, queries: int, weights: dict,
          mode: str = "mxl") -> dict:
    """Priced cost per ordinary query and fixed setup cost from `queries` metered collection attempts."""
    import monitor

    wid, wrec = probe_workload(curve, 1)
    args = SimpleNamespace(n=curve.n, m=m, l=l, family=family, seed=seed, mode=mode, abort_degree=0,
                           max_attempts=queries, workload_seed=0, descent_targets=0, report_every=0,
                           out="", trace="", **bench.LIMITS)
    meter = opcount.Meter()
    res = monitor.collect(args, workload=wrec, meter=meter)
    priced = meter.priced(weights)
    per_query = ("queries", "pdp", "relation_check", "matrix_build")
    attempts = res["monitor"]["attempts"]
    return {
        "probe_workload_id": wid,
        "queries": attempts,
        "ops_per_query": sum(priced.get(p, 0) for p in per_query) / attempts if attempts else None,
        "pdp_ops_per_query": priced.get("pdp", 0) / attempts if attempts else None,
        "fixed_ops": sum(priced.get(p, 0) for p in ("setup", "factor_base", "precompute")),
        "verified_in_probe": res["monitor"]["status"].get("verified_decomposition", 0),
        "wall_ns": sum(v for k, v in meter.wall_ns.items() if k != "instrument"),
    }


# ------------------------------------------------------------------ one scored base
def score(curve: ToyCurve, family: str, l: int, seed: int, m: int = 2, targets: int = 3,
          runs: int = 400, probe_queries: int = 0, weights: dict | None = None, mode: str = "mxl") -> dict:
    if m != 2:
        raise ValueError("the exact rank-process law is implemented for m = 2")
    t0 = time.perf_counter_ns()
    fb = FactorBase(curve, family, l, seed)
    cid, _ = bench.candidate_manifest(curve, fb, {"m": m, "mode": mode})
    achievable = achievable_rank(fb, m)
    target_rank = fb.effective_columns if achievable is None else achievable
    rp = rank_process(fb, target_rank, runs)
    p = rp["p_decomposable"]
    rates = column_hit_rates(fb)
    cover = coupon_time(rates) if rates else None
    prof = product_profile(curve.K, fb.basis, 3)
    z4 = curve.z4_labels(fb.xs, fb.ys)
    out = {
        "schema": SCHEMA,
        "kind": "prediction",
        "candidate_id": cid,
        "curve_id": curve.curve_id,
        "cell": {"n": curve.n, "m": m, "l": l, "family": family, "seed": seed, "mode": mode, "targets": targets},
        "factor_base_sha256": fb.digest,
        "params": fb.params,
        "stage": {
            "fb_points": fb.usable_points,
            "geometric_points": fb.geometric_points,
            "strict_points": fb.strict_points,
            "effective_columns": fb.effective_columns,
            "achievable_rank": achievable,
            "product_profile": prof,
            "product_excess": [a - b for a, b in zip(prof, minimal_profile(curve.n, l, 3))],
            "trace_zero": all(curve.K.trace(b) == 0 for b in fb.basis),
            "linearization_excess": curve.n - prof[0] - prof[1],
            "z4_class_counts": None if z4 is None else [z4.count(k) for k in range(4)],
            "p_decomposable": p,
            "decomposable_targets": rp["decomposable_targets"],
            "rows_per_decomposable_target": rp.get("rows_per_decomposable_target"),
            "min_column_rate": min(rates) if rates else None,
            "column_rate_cv": (statistics.pstdev(rates) / statistics.fmean(rates)) if rates and sum(rates) else None,
        },
        "predicted": {
            "collection_queries_mean": rp["mean"],
            "collection_queries_sd": rp["sd"],
            "collection_queries_quantiles": rp.get("quantiles"),
            "coverage_queries_mean": cover[0] if cover else None,
            "descent_attempts_mean": targets / p if p else None,
            "descent_attempts_sd": math.sqrt(targets * (1 - p)) / p if p else None,
            "rank_process_runs": rp["runs"],
        },
    }
    pr = out["predicted"]
    if pr["collection_queries_mean"] is not None and pr["descent_attempts_mean"] is not None:
        pr["queries_mean"] = pr["collection_queries_mean"] + pr["descent_attempts_mean"]
        pr["queries_sd"] = math.hypot(pr["collection_queries_sd"], pr["descent_attempts_sd"])
    else:
        pr["queries_mean"] = pr["queries_sd"] = None
    if probe_queries and weights is not None:
        pb = probe(curve, family, l, seed, m, probe_queries, weights, mode)
        out["probe"] = pb
        if pr["queries_mean"] is not None and pb["ops_per_query"]:
            pr["total_operations_mean"] = pb["fixed_ops"] + pb["ops_per_query"] * pr["queries_mean"]
            pr["total_operations_sd"] = pb["ops_per_query"] * pr["queries_sd"]
            rho = round(math.sqrt(math.pi * curve.r / 2)) * weights["ec_add"]
            pr["ratio_to_rho"] = pr["total_operations_mean"] / rho
    out["score_wall_ns"] = time.perf_counter_ns() - t0
    return out


def implementation_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


# ------------------------------------------------------------------ commands
def parse_seeds(text: str) -> list[int]:
    out: list[int] = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def _score_job(job: tuple) -> dict:
    n, family, l, seed, kw = job
    calibration = json.loads(bench.CALIBRATION.read_text())
    weights = weights_for(calibration, n) if kw["probe_queries"] else None
    rec = score(ToyCurve(n), family, l, seed, weights=weights, **kw)
    rec["calibration_id"] = calibration["calibration_id"] if weights else None
    rec["implementation_sha256"] = implementation_sha256()
    rec["bench_implementation_sha256"] = bench.implementation_sha256()
    return rec


def cmd_scan(args) -> None:
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing

    seeds = parse_seeds(args.seeds)
    kw = {"m": 2, "targets": args.targets, "runs": args.runs, "probe_queries": args.probe_queries}
    jobs = [(args.n, f, l, s, kw) for l in args.l for f in args.families
            for s in ([1] if f == "prefix" else seeds)]
    out = Path(args.out or RESULTS / f"scan-n{args.n}m2.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=args.jobs, mp_context=ctx, initializer=bench._warm_process) as pool, \
            out.open("a") as fh:
        for rec in pool.map(_score_job, jobs):
            fh.write(canonical(rec) + "\n")
            fh.flush()
            c, st, pr = rec["cell"], rec["stage"], rec["predicted"]
            tot = pr.get("total_operations_mean")
            print(f"n{c['n']} l{c['l']} {c['family']:10s} s{c['seed']:<4d} B={st['fb_points']:3d} "
                  f"C={st['effective_columns']:3d}/{st['achievable_rank']} p={st['p_decomposable']:.5f} "
                  f"Q={pr['queries_mean'] or float('nan'):9.0f} ±{pr['queries_sd'] or float('nan'):7.0f}"
                  + (f" ops={tot:.3e}" if tot else ""), flush=True)


def load_jsonl(paths: list[str]) -> list[dict]:
    import gzip

    out = []
    for p in paths:
        with (gzip.open(p, "rt") if str(p).endswith(".gz") else open(p)) as fh:
            out += [json.loads(line) for line in fh if line.strip()]
    return out


def _key(rec: dict) -> float:
    pr = rec["predicted"]
    v = pr.get("total_operations_mean") or pr.get("queries_mean")
    return math.inf if v is None else v


def cmd_select(args) -> None:
    """Best, median and worst seed per (n, l, family) by predicted cost, plus every prefix base."""
    recs = load_jsonl(args.scans)
    impls = {(r["implementation_sha256"], r["bench_implementation_sha256"]) for r in recs}
    if len(impls) > 1:
        print(f"warning: scans from {len(impls)} implementations; candidate IDs may not match one bench snapshot",
              file=sys.stderr)
    want = {tuple(int(v) for v in s.split(":")) for s in args.cells} if args.cells else None
    groups: dict[tuple, list[dict]] = {}
    for r in recs:
        c = r["cell"]
        if want is not None and (c["n"], c["l"]) not in want:
            continue
        if args.families and c["family"] not in args.families:
            continue
        groups.setdefault((c["n"], c["l"], c["family"]), []).append(r)
    picks = []
    for (n, l, fam), rs in sorted(groups.items()):
        rs.sort(key=_key)
        chosen = {"best": rs[0], "median": rs[len(rs) // 2], "worst": rs[-1]} if len(rs) > 2 else {"only": rs[0]}
        if len(rs) > 2 and args.per_family > 3:
            chosen.update({f"rank{i}": rs[i] for i in range(1, args.per_family - 2)})
        seen = set()
        for role, r in chosen.items():
            if r["cell"]["seed"] in seen:
                continue
            seen.add(r["cell"]["seed"])
            picks.append({"role": role, "rank": rs.index(r), "of": len(rs), "cell": r["cell"],
                          "candidate_id": r["candidate_id"], "factor_base_sha256": r["factor_base_sha256"],
                          "predicted": r["predicted"], "stage": r["stage"], "probe": r.get("probe")})
    doc = {"schema": "fb-search-selection/1", "selected_by": "predicted total_operations_mean (rps), else queries_mean",
           "search_implementation_sha256": implementation_sha256(), "picks": picks}
    Path(args.out).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(f"{len(picks)} picks -> {args.out}")


def spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2
            i = j + 1
        return out

    ra, rb = ranks(a), ranks(b)
    return statistics.correlation(ra, rb)


def cmd_check(args) -> None:
    """Predicted versus measured, joined on candidate_id (one row per measured run)."""
    preds = {}
    for r in load_jsonl(args.predictions):
        preds[r["candidate_id"]] = r
    if args.selection:
        for p in json.loads(Path(args.selection).read_text())["picks"]:
            preds.setdefault(p["candidate_id"], p)
    runs = load_jsonl(args.receipts)
    rows = []
    curves: dict[int, ToyCurve] = {}
    for rec in runs:
        c, cnt = rec["cell"], rec["counts"]
        if c["m"] != 2:
            continue
        p = preds.get(rec["candidate_id"]) or {}
        pr, pb = p.get("predicted") or {}, p.get("probe")
        curve = curves.setdefault(c["n"], ToyCurve(c["n"]))
        wid, wrec = bench.workload(curve, c["workload_seed"], c["targets"])
        assert wid == rec["workload_id"], "workload record drifted"
        fb = FactorBase(curve, c["family"], c["l"], c["seed"])
        rp = replay_workload(fb, wrec)
        coll, desc = cnt["ordinary_queries"], cnt["descent_attempts"]
        z = ((coll - pr["collection_queries_mean"]) / pr["collection_queries_sd"]
             if pr.get("collection_queries_sd") else None)
        rows.append({
            "candidate_id": rec["candidate_id"], "workload_id": rec["workload_id"], "run_id": rec["run_id"],
            "family": c["family"], "l": c["l"], "seed": c["seed"], "status": rec["status"],
            "pred_collection": round(pr["collection_queries_mean"]) if pr else None, "meas_collection": coll,
            "replay_collection": rp["collection_queries"],
            "z_collection": None if z is None else round(z, 2),
            "pred_descent": round(pr["descent_attempts_mean"]) if pr else None, "meas_descent": desc,
            "replay_descent": sum(rp["descent_attempts"]),
            "replay_exact": rp["collection_queries"] == coll and sum(rp["descent_attempts"]) == desc,
            "pred_total_ops": pr.get("total_operations_mean"), "meas_total_ops": rec["total_operations"],
            "replay_total_ops": pb["fixed_ops"] + pb["ops_per_query"] * (rp["collection_queries"]
                                                                        + sum(rp["descent_attempts"]))
            if pb else None,
        })
    out = Path(args.out) if args.out else None
    fields = list(rows[0]) if rows else []
    if out:
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    if args.verbose:
        for r in rows:
            print(r)
    zs = [r["z_collection"] for r in rows if r["z_collection"] is not None]
    within = sum(1 for z in zs if abs(z) <= 1)
    if not rows:
        print("no joined runs")
        return
    if zs:
        print(f"{len(rows)} runs; collection within 1 sd of the expectation: {within}/{len(zs)}; mean z = "
              f"{statistics.fmean(zs):+.2f}")
    exact = sum(r["replay_exact"] for r in rows)
    print(f"exact replay of collection and descent query counts: {exact}/{len(rows)}")
    if args.require_exact and exact < len(rows):
        bad = [r["run_id"] for r in rows if not r["replay_exact"]]
        print(f"replay mismatch (the PDP solver missed decompositions or the pipeline changed): {bad}",
              file=sys.stderr)
        sys.exit(1)
    rep = [r["meas_total_ops"] / r["replay_total_ops"] for r in rows if r["replay_total_ops"] and r["meas_total_ops"]]
    if rep:
        print(f"measured total / (probe price x replayed queries + fixed): median {statistics.median(rep):.4f} "
              f"[{min(rep):.4f}, {max(rep):.4f}]")
    paired = [(r["pred_total_ops"], r["meas_total_ops"]) for r in rows if r["pred_total_ops"] and r["meas_total_ops"]]
    if paired:
        rho = spearman([a for a, _ in paired], [b for _, b in paired])
        ratio = [b / a for a, b in paired]
        print(f"total ops: spearman {rho:.3f}, measured/predicted median {statistics.median(ratio):.3f} "
              f"[{min(ratio):.3f}, {max(ratio):.3f}]")


def cmd_expect(args) -> None:
    """Replay estimate: the pipeline's exact query counts on many ic-bench workloads (complete solver
    assumed; checked by `check`) priced with the probe.  Not an end-to-end measurement."""
    calibration = json.loads(bench.CALIBRATION.read_text())
    weights = weights_for(calibration, args.n)
    curve = ToyCurve(args.n)
    bench._warm_process()
    out = Path(args.out) if args.out else None
    for spec in args.bases:
        family, l, seed = spec.split(":")
        l, seed = int(l), int(seed)
        rec = score(curve, family, l, seed, targets=args.targets, runs=args.runs, probe_queries=args.probe_queries,
                    weights=weights)
        fb = FactorBase(curve, family, l, seed)
        target = achievable_rank(fb, 2)
        wids, qs = [], []
        for w in parse_seeds(args.workloads):
            wid, wrec = bench.workload(curve, w, args.targets)
            rp = replay_workload(fb, wrec, target)
            wids.append(wid)
            qs.append(rp["collection_queries"] + sum(rp["descent_attempts"]))
        price, fixed = rec["probe"]["ops_per_query"], rec["probe"]["fixed_ops"]
        totals = [fixed + price * q for q in qs]
        rng = random.Random(f"fbsearch-expect|{rec['candidate_id']}")
        boot = sorted(statistics.fmean(rng.choices(totals, k=len(totals))) for _ in range(2000))
        row = {
            "schema": "fb-search-replay-estimate/1", "kind": "replay_estimate", "candidate_id": rec["candidate_id"],
            "curve_id": curve.curve_id, "cell": rec["cell"], "workload_ids": wids,
            "workload_seeds": args.workloads, "queries_mean": statistics.fmean(qs),
            "total_operations_mean": statistics.fmean(totals),
            "total_operations_ci95": [boot[50], boot[1949]],
            "predicted_total_operations_mean": rec["predicted"]["total_operations_mean"],
            "probe": rec["probe"], "calibration_id": calibration["calibration_id"],
            "note": "query counts replayed exactly through the factor base's decomposition table on each workload's "
            "streams; phase costs priced by the probe (per query) and probed fixed costs; not a measured run",
            "implementation_sha256": implementation_sha256(),
        }
        print(f"{spec:18s} {rec['candidate_id']} replay mean {row['total_operations_mean']:.3e} "
              f"[{boot[50]:.3e}, {boot[1949]:.3e}] predicted {row['predicted_total_operations_mean']:.3e}", flush=True)
        if out:
            with out.open("a") as fh:
                fh.write(canonical(row) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="score factor bases by predicted end-to-end cost")
    s.add_argument("--n", type=int, required=True)
    s.add_argument("--l", type=int, nargs="+", required=True)
    s.add_argument("--families", nargs="+", default=["geometric", "geomtraceu", "prefix", "random", "kertrace"])
    s.add_argument("--seeds", default="1-32", help="e.g. 1-64 or 1,5,9 (prefix uses seed 1 only)")
    s.add_argument("--targets", type=int, default=3)
    s.add_argument("--runs", type=int, default=400, help="Monte Carlo runs of the rank process")
    s.add_argument("--probe-queries", type=int, default=200, help="metered queries for the per-query price (0 = none)")
    s.add_argument("--jobs", type=int, default=4)
    s.add_argument("--out", default="")
    sel = sub.add_parser("select", help="best/median/worst seed per family")
    sel.add_argument("scans", nargs="+")
    sel.add_argument("--per-family", type=int, default=3)
    sel.add_argument("--out", default=str(SELECTED))
    sel.add_argument("--cells", nargs="*", default=[], help="n:l pairs to keep, e.g. 19:5 19:6")
    sel.add_argument("--families", nargs="*", default=[])
    ch = sub.add_parser("check", help="join predictions with measured ic-bench receipts on candidate_id")
    ch.add_argument("receipts", nargs="+")
    ch.add_argument("--predictions", nargs="*", default=[])
    ch.add_argument("--selection", default=str(SELECTED))
    ch.add_argument("--out", default="")
    ch.add_argument("--require-exact", action="store_true", help="exit 1 unless every m = 2 run replays exactly")
    ch.add_argument("--verbose", action="store_true", help="print every joined row")
    ex = sub.add_parser("expect", help="replay estimate of the expected cost over many workloads")
    ex.add_argument("--n", type=int, required=True)
    ex.add_argument("bases", nargs="+", help="family:l:seed")
    ex.add_argument("--workloads", default="1-200")
    ex.add_argument("--targets", type=int, default=3)
    ex.add_argument("--runs", type=int, default=400)
    ex.add_argument("--probe-queries", type=int, default=200)
    ex.add_argument("--out", default="")
    args = ap.parse_args()
    {"scan": cmd_scan, "select": cmd_select, "check": cmd_check, "expect": cmd_expect}[args.cmd](args)


if __name__ == "__main__":
    main()
