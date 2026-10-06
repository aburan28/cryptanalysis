#!/usr/bin/env python3
"""The single-target online cost of an index-calculus candidate, predicted from its factor base.

AGENTS.md makes one previously unseen target the default IC objective: the clock starts when
target-dependent work begins (after the factor base, relation collection and relation LA are
ready) and stops when the target's log is recovered and verified.  For the ic-bench pipeline
(`TDpdp`, m = 2) that interval is a run of rerandomized attempts Q + [a]G, each decomposed by the
same PDP solver, until one has a verified relation, followed by scalar replay:

    T_online,1 = T_target_query + T_target_PDP + T_target_relation_check + T_target_descent
                 + T_target_recovery_check.

Q + [a]G is uniform on the nonidentity subgroup points, so the attempt count is exactly geometric
with success probability p_dec = |D| / (r - 1), D the decomposable points (complete solver; the
search replay checks this on every recorded run).  The online cost is therefore

    E[ops] = (1 / p_dec - 1) * c_fail + c_success + c_recovery,

with c_fail, c_success and c_recovery measured by `probe` under opcount on the exact code path of
monitor.collect: failed attempts on rerandomized probe targets, successful attempts on points
drawn uniformly from D (the law of the attempt that succeeds), and one scalar replay.  Each
target attempt is charged its full solution enumeration (monitor.collect meters it in
target_pdp whether or not S = 0), which collection queries are not.

Target-independent preparation (factor base, collection to the achievable rank, relation LA) is
reported separately as setup and excluded from the online figure.  Wall times measured here are
exploratory: they come from an ordinary, shared host, not the isolated benchmark service.

    python3 online.py scan --n 19 --l 5 6 7 8 9 10 --families geometric geomtraceu prefix --seeds 1-8
    python3 online.py check ../ic-bench/baseline/search.jsonl     # per-target costs, predicted vs measured
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from search import (FactorBase, ToyCurve, bench, implementation_sha256 as search_sha256, kernel,  # noqa: E402
                    load_jsonl, opcount, parse_seeds, replay_workload, weights_for)
from toycurve import canonical, sha256_hex  # noqa: E402

SCHEMA = "fb-search-online/1"
RESULTS = HERE / "results"


def decomposable_points(fb: FactorBase) -> np.ndarray:
    """Every nonidentity subgroup point with a two-point decomposition over the base, as (x, y) rows."""
    C, K = fb.curve, fb.curve.K
    px, py = C.psi(fb.xs, fb.ys)
    sx, sy = K.pair_sums(fb.xs, fb.ys)
    qx, _ = K.pair_sums(px, py)
    ok = (qx == np.uint64(kernel.INF_X)) & (sx != np.uint64(kernel.INF_X))
    if not ok.any():
        return np.zeros((0, 2), dtype=np.uint64)
    return np.unique(np.stack([sx[ok], sy[ok]], axis=1), axis=0)


def probe(fb: FactorBase, weights: dict, fails: int = 120, successes: int = 40, mode: str = "mxl",
          D: np.ndarray | None = None, lazy: bool = True, planted: bool = False) -> dict:
    """Priced cost and wall time of failed and successful target attempts, and of scalar replay.

    lazy=True is the monitor.collect path (the solution count is enumerated only when the scan reads
    it); lazy=False replays the earlier path that enumerated before every target scan.

    planted=True is for bases too large to enumerate D: failures are rerandomized probe targets that
    did not decompose, and successes are P_i + P_j for uniform pairs of base points whose psi
    components cancel (weighted by decomposition count rather than uniform on D)."""
    import macaulay
    from descent import Pieces
    from relations import classify_solution, relation_row

    C, K = fb.curve, fb.curve.K
    m = 2
    P = Pieces(fb, m)
    limits = macaulay.Limits(**bench.LIMITS)
    if D is None and not planted:
        D = decomposable_points(fb)
    rng = random.Random(f"fbsearch-online|{C.curve_id}|{fb.digest}")

    def attempt(Qa) -> tuple[bool, int, int]:
        meter = opcount.Meter()
        t0 = time.perf_counter_ns()
        with meter.phase("target_query"):
            s = P.system(Qa[0])
        enumerated: dict = {}

        def count() -> int:
            enumerated["S"], enumerated["sols"] = s.solutions()
            return enumerated["S"]

        with meter.phase("target_pdp") as ops:
            if not lazy:
                count()
            scan = macaulay.degree_scan(s, count if lazy else enumerated["S"], limits, mode=mode)
            ops["mac_op"] += scan["xors"] + scan["build_ops"]
        rows = set()
        if scan["status"] == "solved":
            sols = enumerated["sols"]
            with meter.phase("target_relation_check"):
                for v in sols.tolist():
                    c = classify_solution(fb, m, Qa, v)
                    if c["status"] in ("verified", "improper"):
                        rows.add(tuple(sorted(relation_row(fb, c["points"]).items())))
        if rows:
            with meter.phase("target_descent") as ops:
                ops["modr_mul"] += len(next(iter(rows)))
        wall = time.perf_counter_ns() - t0
        return bool(rows), sum(meter.priced(weights).values()), wall

    def rerandomize(Q) -> tuple[tuple[int, int], int, int]:
        meter = opcount.Meter()
        t0 = time.perf_counter_ns()
        with meter.phase("target_descent"):
            a = rng.randrange(1, C.r)
            Qa = K.add(Q, K.smul(C.G, a))
        return Qa, sum(meter.priced(weights).values()), time.perf_counter_ns() - t0

    dset = None if planted else {(int(x), int(y)) for x, y in D.tolist()}
    fail_ops, fail_wall, rr_ops, rr_wall = [], [], [], []
    _, Q = C.random_subgroup_point(rng)
    while len(fail_ops) < fails:
        Qa, o, w = rerandomize(Q)
        rr_ops.append(o)
        rr_wall.append(w)
        if Qa[0] == kernel.INF_X or (dset is not None and Qa in dset):
            continue
        ok, o, w = attempt(Qa)
        if planted and ok:
            continue
        assert not ok, "a point outside D decomposed: the decomposition table is incomplete"
        fail_ops.append(o)
        fail_wall.append(w)
    succ_ops, succ_wall = [], []
    if planted:
        px, py = C.psi(fb.xs, fb.ys)
        psi = list(zip(px.tolist(), py.tolist()))

    def success_point() -> tuple[int, int]:
        if not planted:
            x, y = D[rng.randrange(len(D))].tolist()
            return int(x), int(y)
        while True:
            i, j = rng.randrange(len(fb.xs)), rng.randrange(len(fb.xs))
            if K.add(psi[i], psi[j])[0] != kernel.INF_X:
                continue
            R = K.add((int(fb.xs[i]), int(fb.ys[i])), (int(fb.xs[j]), int(fb.ys[j])))
            if R[0] != kernel.INF_X:
                return R

    for _ in range(successes if planted or len(D) else 0):
        ok, o, w = attempt(success_point())
        assert ok, "a point in D did not decompose: the PDP solver missed a decomposition"
        succ_ops.append(o)
        succ_wall.append(w)
    meter = opcount.Meter()
    t0 = time.perf_counter_ns()
    s_true, Q = C.random_subgroup_point(rng)
    with meter.phase("target_recovery_check"):
        assert K.smul(C.G, s_true) == Q
    rec_wall = time.perf_counter_ns() - t0
    mean = statistics.fmean
    return {
        "fail_attempts": len(fail_ops),
        "success_attempts": len(succ_ops),
        "c_rerandomize_ops": mean(rr_ops),
        "c_fail_ops": mean(rr_ops) + mean(fail_ops),
        "c_success_ops": mean(rr_ops) + mean(succ_ops) if succ_ops else None,
        "c_recovery_ops": sum(meter.priced(weights).values()),
        "c_fail_wall_ns": mean(rr_wall) + mean(fail_wall),
        "c_success_wall_ns": mean(rr_wall) + mean(succ_wall) if succ_wall else None,
        "c_recovery_wall_ns": rec_wall,
        "wall_note": "exploratory: ordinary shared host, not the isolated benchmark service",
    }


def probe_ht(fb: FactorBase, weights: dict, fails: int = 200, successes: int = 60,
             D: np.ndarray | None = None, rerandomize: str = "walk") -> dict:
    """Target-attempt prices on the monitor.collect `ht` path (PDP2ht).  With rerandomize="walk" an
    attempt is one group addition plus one half-trace decomposition; the step [a0]G (one scalar
    multiplication per target) is folded into c_recovery with the scalar replay."""
    from htsolver import HalfTraceSolver
    from relations import relation_row

    C, K = fb.curve, fb.curve.K
    rng = random.Random(f"fbsearch-online-ht|{C.curve_id}|{fb.digest}")
    with opcount.Meter().phase("precompute"):
        sv = HalfTraceSolver(fb)

    def priced(fn):
        m = opcount.Meter()
        t0 = time.perf_counter_ns()
        with m.phase("x"):
            out = fn()
        return out, sum(m.priced(weights).values()), time.perf_counter_ns() - t0

    def attempt(Qa):
        def run():
            pairs = sv.decompose(Qa)
            rows = {tuple(sorted(relation_row(fb, list(pts)).items())) for pts in pairs}
            if rows:
                opcount.charge("modr_mul", len(next(iter(rows))))
            return bool(rows)
        return priced(run)

    dset = None if D is None else {(int(x), int(y)) for x, y in D.tolist()}
    step, c_init, w_init = priced(lambda: K.smul(C.G, rng.randrange(1, C.r)))
    _, Q = C.random_subgroup_point(rng)
    Qa = Q
    rr_ops, rr_wall, fail_ops, fail_wall = [], [], [], []
    while len(fail_ops) < fails:
        if rerandomize == "walk":
            Qa, o, w = priced(lambda: K.add(Qa, step))
        else:
            Qa, o, w = priced(lambda: K.add(Q, K.smul(C.G, rng.randrange(1, C.r))))
        rr_ops.append(o)
        rr_wall.append(w)
        if Qa[0] == kernel.INF_X or (dset is not None and Qa in dset):
            continue
        ok, o, w = attempt(Qa)
        if ok:
            assert dset is None, "a point outside D decomposed: the decomposition table is incomplete"
            continue
        fail_ops.append(o)
        fail_wall.append(w)
    px, py = C.psi(fb.xs, fb.ys)
    psi = list(zip(px.tolist(), py.tolist()))
    succ_ops, succ_wall = [], []
    while len(succ_ops) < successes:
        if D is not None and len(D):
            x, y = D[rng.randrange(len(D))].tolist()
            R = (int(x), int(y))
        else:
            i, j = rng.randrange(len(fb.xs)), rng.randrange(len(fb.xs))
            if K.add(psi[i], psi[j])[0] != kernel.INF_X:
                continue
            R = K.add((int(fb.xs[i]), int(fb.ys[i])), (int(fb.xs[j]), int(fb.ys[j])))
            if R[0] == kernel.INF_X:
                continue
        ok, o, w = attempt(R)
        assert ok, "a point in D did not decompose: the half-trace solver missed a decomposition"
        succ_ops.append(o)
        succ_wall.append(w)
    s_true, Qr = C.random_subgroup_point(rng)
    _, c_rec, w_rec = priced(lambda: K.smul(C.G, s_true) == Qr)
    mean = statistics.fmean
    walk_init = (c_init, w_init) if rerandomize == "walk" else (0, 0)
    return {
        "solver": "PDP2ht", "rerandomize": rerandomize, "fail_attempts": len(fail_ops),
        "success_attempts": len(succ_ops), "c_rerandomize_ops": mean(rr_ops),
        "c_fail_ops": mean(rr_ops) + mean(fail_ops), "c_success_ops": mean(rr_ops) + mean(succ_ops),
        "c_recovery_ops": c_rec + walk_init[0],
        "c_fail_wall_ns": mean(rr_wall) + mean(fail_wall), "c_success_wall_ns": mean(rr_wall) + mean(succ_wall),
        "c_recovery_wall_ns": w_rec + walk_init[1],
        "residual_search_dimension": max(0, fb.l + sv.dim_V2 - C.n - 1 + int(all(K.trace(b) == 0 for b in fb.basis))),
        "dim_V2": sv.dim_V2,
        "wall_note": "exploratory: ordinary shared host, not the isolated benchmark service",
    }


def online_prediction(p: float, pb: dict, key: str = "ops") -> dict:
    """Mean and sd of the one-target online cost from the geometric attempt law."""
    if not p or pb["c_success_" + key] is None:
        return {"mean": None, "sd": None}
    cf, cs, cr = pb["c_fail_" + key], pb["c_success_" + key], pb["c_recovery_" + key]
    return {"mean": (1 / p - 1) * cf + cs + cr, "sd": cf * math.sqrt(1 - p) / p}


def score(curve: ToyCurve, family: str, l: int, seed: int, weights: dict, fails: int = 120,
          successes: int = 40, mode: str = "mxl", setup: bool = True, lazy: bool = True,
          max_pairs: int = 12_000_000, rerandomize: str = "uniform") -> dict:
    """max_pairs bounds the exact pair table; above it p_dec is the psi-class prediction
    (relations.predicted_yield) and successful attempts are planted."""
    from relations import predicted_yield

    t0 = time.perf_counter_ns()
    fb = FactorBase(curve, family, l, seed)
    cell = {"m": 2, "mode": mode}
    if rerandomize != "uniform":
        cell["rerandomize"] = rerandomize
    cid, _ = bench.candidate_manifest(curve, fb, cell)
    pred_y = predicted_yield(fb, 2)["p_decomposable"]
    exact = len(fb.xs) * (len(fb.xs) + 1) // 2 <= max_pairs
    if exact:
        D = decomposable_points(fb)
        p = len(D) / (curve.r - 1)
    else:
        D, p = None, pred_y
    if mode == "ht":
        pb = probe_ht(fb, weights, fails, successes, D, rerandomize)
    else:
        pb = probe(fb, weights, fails, successes, mode, D, lazy, planted=not exact)
    ops, wall = online_prediction(p, pb, "ops"), online_prediction(p, pb, "wall_ns")
    rho_ops = round(math.sqrt(math.pi * curve.r / 2)) * weights["ec_add"]
    floor_ops = round(math.sqrt(math.pi * curve.r / (4 * curve.n))) * weights["ec_add"]
    out = {
        "schema": SCHEMA,
        "kind": "prediction",
        "objective": "single-target online (AGENTS.md T_online,1)",
        "solution_count": "lazy" if lazy else "eager",
        "candidate_id": cid,
        "curve_id": curve.curve_id,
        "cell": {"n": curve.n, "m": 2, "l": l, "family": family, "seed": seed, "mode": mode, "targets": 1,
                 **({"rerandomize": rerandomize} if rerandomize != "uniform" else {})},
        "factor_base_sha256": fb.digest,
        "stage": {"fb_points": fb.usable_points, "effective_columns": fb.effective_columns,
                  "trace_zero": all(curve.K.trace(b) == 0 for b in fb.basis),
                  "p_decomposable": p, "p_decomposable_source": "exact" if exact else "psi_class_prediction",
                  "p_decomposable_predicted": pred_y, "decomposable_targets": int(len(D)) if exact else None},
        "probe": pb,
        "predicted": {
            "online_attempts_mean": 1 / p if p else None,
            "online_operations_mean": ops["mean"], "online_operations_sd": ops["sd"],
            "online_wall_ns_mean": wall["mean"],
            "rho_operations": rho_ops, "rho_floor_operations": floor_ops,
            "online_ratio_to_rho": ops["mean"] / rho_ops if ops["mean"] else None,
            "online_ratio_to_floor": ops["mean"] / floor_ops if ops["mean"] else None,
        },
    }
    if setup:
        from search import score as cold_score

        cs = cold_score(curve, family, l, seed, targets=1, runs=200, probe_queries=100, weights=weights,
                        mode="mxl" if mode == "ht" else mode)
        cp = cs["predicted"]
        out["setup"] = {
            "note": "target-independent preparation, excluded from the online figure",
            "collection_queries_mean": cp["collection_queries_mean"],
            "setup_operations_mean": (cs["probe"]["fixed_ops"] + cs["probe"]["ops_per_query"]
                                      * cp["collection_queries_mean"]) if cp["collection_queries_mean"] else None,
        }
    out["score_wall_ns"] = time.perf_counter_ns() - t0
    return out


def _job(job) -> dict:
    n, family, l, seed, kw, cal_path = job
    calibration = json.loads(Path(cal_path or bench.CALIBRATION).read_text())
    rec = score(ToyCurve(n), family, l, seed, weights_for(calibration, n), **kw)
    rec["calibration_id"] = calibration["calibration_id"]
    rec["implementation_sha256"] = sha256_hex({"online": implementation_sha256(), "search": search_sha256()})
    rec["bench_implementation_sha256"] = bench.implementation_sha256()
    return rec


def implementation_sha256() -> str:
    import hashlib

    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def cmd_scan(args) -> None:
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing

    kw = {"fails": args.fails, "successes": args.successes, "setup": not args.no_setup, "lazy": not args.eager,
          "mode": args.mode, "rerandomize": args.rerandomize}
    jobs = [(args.n, f, l, s, kw, args.calibration) for l in args.l for f in args.families
            for s in ([1] if f == "prefix" else parse_seeds(args.seeds))]
    out = Path(args.out or RESULTS / f"online-n{args.n}m2.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=args.jobs, mp_context=ctx, initializer=bench._warm_process) as pool, \
            out.open("a") as fh:
        for rec in pool.map(_job, jobs):
            fh.write(canonical(rec) + "\n")
            fh.flush()
            c, st, pr = rec["cell"], rec["stage"], rec["predicted"]
            su = (rec.get("setup") or {}).get("setup_operations_mean")
            print(f"n{c['n']} l{c['l']:<2d} {c['family']:10s} s{c['seed']:<3d} B={st['fb_points']:5d} "
                  f"p={st['p_decomposable']:.4f} attempts={pr['online_attempts_mean'] or float('nan'):8.1f} "
                  f"online={pr['online_operations_mean'] or float('nan'):.3e} "
                  f"x rho={pr['online_ratio_to_rho'] or float('nan'):8.2f}"
                  + (f" setup={su:.2e}" if su else ""), flush=True)


def cmd_check(args) -> None:
    """Per-target online cost: (A - 1) c_fail + c_success + c_recovery with the replayed attempt count A,
    against the measured per-target operations in ic-bench receipts."""
    calibration = json.loads(bench.CALIBRATION.read_text())
    bench._warm_process()
    curves: dict[int, ToyCurve] = {}
    probes: dict[str, dict] = {}
    ratios, rows = [], []
    for rec in load_jsonl(args.receipts):
        c = rec["cell"]
        if c["m"] != 2 or rec["status"] != "complete":
            continue
        curve = curves.setdefault(c["n"], ToyCurve(c["n"]))
        fb = FactorBase(curve, c["family"], c["l"], c["seed"])
        key = (fb.digest, c["mode"], c.get("rerandomize", "uniform"))
        if key not in probes:
            if c["mode"] == "ht":
                probes[key] = probe_ht(fb, weights_for(calibration, c["n"]), args.fails, args.successes,
                                       decomposable_points(fb), c.get("rerandomize", "uniform"))
            else:
                probes[key] = probe(fb, weights_for(calibration, c["n"]), args.fails, args.successes, c["mode"],
                                    lazy=not args.eager)
        pb = probes[key]
        _, wrec = bench.workload(curve, c["workload_seed"], c["targets"])
        attempts = replay_workload(fb, wrec, rerandomize=c.get("rerandomize", "uniform"))["descent_attempts"]
        measured = rec["warm"]["per_target_operations"]
        for a, mt in zip(attempts, measured):
            pred = (a - 1) * pb["c_fail_ops"] + pb["c_success_ops"] + pb["c_recovery_ops"]
            ratios.append(mt / pred)
            rows.append({"run_id": rec["run_id"], "attempts": a, "measured_ops": mt, "predicted_ops": pred})
    if not ratios:
        print("no m = 2 receipts")
        return
    ratios.sort()
    agg_m = sum(r["measured_ops"] for r in rows)
    agg_p = sum(r["predicted_ops"] for r in rows)
    print(f"{len(rows)} targets in {len({r['run_id'] for r in rows})} runs; measured / predicted per target: "
          f"median {statistics.median(ratios):.3f}, p10 {ratios[len(ratios) // 10]:.3f}, "
          f"p90 {ratios[9 * len(ratios) // 10]:.3f}; pooled {agg_m / agg_p:.4f}")
    if args.out:
        with open(args.out, "w") as fh:
            for r in rows:
                fh.write(canonical(r) + "\n")


def cmd_select(args) -> None:
    """Per (n, family): the (l, seed) with the least predicted online cost; prefix at its best l."""
    recs = [r for r in load_jsonl(args.scans) if r["predicted"]["online_operations_mean"]]
    if args.n:
        recs = [r for r in recs if r["cell"]["n"] in args.n]
    best: dict[tuple, dict] = {}
    for r in recs:
        k = (r["cell"]["n"], r["cell"]["family"])
        if k not in best or r["predicted"]["online_operations_mean"] < best[k]["predicted"]["online_operations_mean"]:
            best[k] = r
    picks = [{"role": "online_best", "cell": r["cell"], "candidate_id": r["candidate_id"],
              "factor_base_sha256": r["factor_base_sha256"], "predicted": r["predicted"], "stage": r["stage"],
              "setup": r.get("setup")} for _, r in sorted(best.items())]
    doc = {"schema": "fb-search-online-selection/1", "objective": "single-target online (T_online,1)",
           "selected_by": "least predicted online_operations_mean per (n, family) over the scanned l and seeds",
           "picks": picks}
    Path(args.out).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    for p in picks:
        c = p["cell"]
        print(f"n{c['n']} {c['family']:10s} l{c['l']} s{c['seed']} {p['candidate_id']} "
              f"online={p['predicted']['online_operations_mean']:.3e} x rho={p['predicted']['online_ratio_to_rho']:.1f}")


def cmd_report(args) -> None:
    """The AGENTS.md one-target table from ic-bench receipts of one-target suites."""
    sel = {p["candidate_id"]: p for p in json.loads(Path(args.selection).read_text())["picks"]}
    by: dict[str, list] = {}
    for r in load_jsonl(args.receipts):
        by.setdefault(r["candidate_id"], []).append(r)
    print("| candidate | n | base | targets verified (IC / rho) | IC online ms, mean [min, max] | "
          "rho online ms, mean | online_speedup = rho/IC, geo-mean [min, max] | measured online ops | "
          "predicted online ops | online ops / rho ops | setup ops (excluded) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    order = sorted(by, key=lambda c: (by[c][0]["cell"]["n"], -statistics.geometric_mean(
        [x["online"]["speedup"] for x in by[c] if x["online"]["speedup"]] or [1e-9])))
    for cid in order:
        rs = by[cid]
        c = rs[0]["cell"]
        ok_ic = sum(1 for x in rs if x["status"] == "complete" and x["verified_scalar"])
        ok_rho = sum(1 for x in rs if x["rho_measured"]["verified"])
        ic = [x["online"]["ic_online_ns"] / 1e6 for x in rs]
        rho = [x["online"]["rho_online_ns"] / 1e6 for x in rs]
        sp = [x["online"]["speedup"] for x in rs if x["online"]["speedup"]]
        ops = statistics.fmean(x["warm"]["per_target_operations"][0] for x in rs)
        rho_ops = rs[0]["rho_operations"]
        shared = statistics.fmean(x["warm"]["shared_operations"] for x in rs)
        pred = (sel.get(cid) or {}).get("predicted", {}).get("online_operations_mean")
        print(f"| `{cid}` | {c['n']} | {c['family']} l{c['l']} s{c['seed']} | {ok_ic}/{len(rs)} / {ok_rho}/{len(rs)} "
              f"| {statistics.fmean(ic):.1f} [{min(ic):.1f}, {max(ic):.1f}] | {statistics.fmean(rho):.2f} "
              f"| {statistics.geometric_mean(sp):.3f} [{min(sp):.3f}, {max(sp):.3f}] | {ops:.3e} "
              f"| {pred:.3e} | {ops / rho_ops:.1f} | {shared:.2e} |" if pred else
              f"| `{cid}` | {c['n']} | {c['family']} l{c['l']} s{c['seed']} | {ok_ic}/{len(rs)} / {ok_rho}/{len(rs)} "
              f"| {statistics.fmean(ic):.1f} | {statistics.fmean(rho):.2f} | {statistics.geometric_mean(sp):.3f} "
              f"| {ops:.3e} | - | {ops / rho_ops:.1f} | {shared:.2e} |")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="score factor bases by predicted single-target online cost")
    s.add_argument("--n", type=int, required=True)
    s.add_argument("--l", type=int, nargs="+", required=True)
    s.add_argument("--families", nargs="+", default=["geometric", "geomtraceu", "prefix"])
    s.add_argument("--seeds", default="1-8")
    s.add_argument("--fails", type=int, default=120)
    s.add_argument("--successes", type=int, default=40)
    s.add_argument("--no-setup", action="store_true", help="skip the setup (collection) prediction")
    s.add_argument("--eager", action="store_true", help="price the earlier always-enumerate target path")
    s.add_argument("--mode", default="mxl", choices=("xl", "mxl", "ht"), help="PDP solver (ht = PDP2ht)")
    s.add_argument("--rerandomize", default="uniform", choices=("uniform", "walk"))
    s.add_argument("--jobs", type=int, default=4)
    s.add_argument("--out", default="")
    s.add_argument("--calibration", default="", help="calibration file (default: ../ic-bench/calibration.json)")
    ch = sub.add_parser("check", help="per-target online cost, predicted vs measured receipts")
    ch.add_argument("receipts", nargs="+")
    ch.add_argument("--fails", type=int, default=120)
    ch.add_argument("--successes", type=int, default=40)
    ch.add_argument("--out", default="")
    ch.add_argument("--eager", action="store_true", help="receipts from the earlier always-enumerate target path")
    se = sub.add_parser("select", help="best (l, seed) per (n, family) for the ic-bench online suite")
    se.add_argument("scans", nargs="+")
    se.add_argument("--n", type=int, nargs="*", default=[])
    se.add_argument("--out", default=str(HERE / "online-selected.json"))
    rp = sub.add_parser("report", help="one-target table from ic-bench receipts")
    rp.add_argument("receipts", nargs="+")
    rp.add_argument("--selection", default=str(HERE / "online-selected.json"))
    args = ap.parse_args()
    {"scan": cmd_scan, "check": cmd_check, "select": cmd_select, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
