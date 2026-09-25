#!/usr/bin/env python3
"""Online heuristics for relation collection, and a collection run that uses them.

`CollectionMonitor` takes one record per PDP attempt and keeps the numbers a collection
run is steered by: yield per attempt, novel rows per attempt at the current rank, the
solving-degree mix by outcome, cost per attempt, per verified relation and per novel row,
the projected work to the target rank, and the abort degree that minimizes cost per
relation.  It is independent of the solver: any collector that can report status, the
degree it stopped at and its per-degree cost can feed it.

    python3 monitor.py collect --n 19 --m 2 --l 6 --family prefix --mode mxl

runs a complete collection with the Macaulay solver on ordinary subgroup targets, tracks
the rank of the relation matrix mod r, solves it, and verifies every factor-base log
against [log]G.  Every phase is metered (opcount.py); ../ic-bench prices the counters in
one calibrated unit and names each run as an IC1 candidate.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from collections import Counter, deque
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import kernel  # noqa: E402
import macaulay  # noqa: E402
import opcount  # noqa: E402
from descent import Pieces  # noqa: E402
from factor_base import FactorBase  # noqa: E402
from profile import bootstrap_mean_ci, implementation_sha256, predictions, wilson95  # noqa: E402
from relations import classify_solution, exact_subgroup_yield, predicted_yield, relation_row  # noqa: E402
from toycurve import ToyCurve, canonical  # noqa: E402


class RankTracker:
    """Incremental row echelon form mod a prime r over `columns` columns (with a RHS)."""

    def __init__(self, columns: int, r: int):
        self.columns, self.r = columns, r
        self.rows: dict[int, tuple[dict[int, int], int]] = {}

    @property
    def rank(self) -> int:
        return len(self.rows)

    def add(self, row: dict[int, int], rhs: int) -> bool:
        r = self.r
        row = {j: c % r for j, c in row.items() if c % r}
        rhs %= r
        while row:
            p = min(row)
            if p not in self.rows:
                inv = pow(row[p], -1, r)
                opcount.charge("modr_inv")
                opcount.charge("modr_mul", len(row) + 1)
                self.rows[p] = ({j: c * inv % r for j, c in row.items()}, rhs * inv % r)
                return True
            prow, prhs = self.rows[p]
            f = row[p]
            opcount.charge("modr_mul", len(prow) + 1)
            for j, c in prow.items():
                v = (row.get(j, 0) - f * c) % r
                if v:
                    row[j] = v
                else:
                    row.pop(j, None)
            rhs = (rhs - f * prhs) % r
        return False

    def solve(self) -> dict[int, int]:
        """A solution with every non-pivot column set to 0 (unique when rank = columns)."""
        sol: dict[int, int] = {j: 0 for j in range(self.columns) if j not in self.rows}
        for p in sorted(self.rows, reverse=True):
            row, rhs = self.rows[p]
            v = rhs
            opcount.charge("modr_mul", len(row) - 1)
            for j, c in row.items():
                if j != p:
                    v -= c * sol[j]
            sol[p] = v % self.r
        return sol


def achievable_rank(fb: FactorBase, m: int) -> int | None:
    """Rank mod r of the relations from every two-point decomposition of every subgroup
    target: the rank a collection can reach.  It is below the column count when the
    psi classes force a kernel, e.g. on a cofactor-4 curve when the class-{1,3} columns
    only ever meet as sigma_a e_a - sigma_b e_b and no 4-torsion point sits in F."""
    if m != 2 or len(fb.xs) * (len(fb.xs) + 1) // 2 > 3_000_000:
        return None
    C, K = fb.curve, fb.curve.K
    px, py = C.psi(fb.xs, fb.ys)
    sx, _ = K.pair_sums(fb.xs, fb.ys)
    qx, _ = K.pair_sums(px, py)
    ok = (qx == np.uint64(kernel.INF_X)) & (sx != np.uint64(kernel.INF_X))
    i, j = np.triu_indices(len(fb.xs))
    t = RankTracker(fb.effective_columns, C.r)
    for a, b in zip(i[ok].tolist(), j[ok].tolist()):
        row: dict[int, int] = {}
        for k in (a, b):
            if fb.col_of[k] >= 0:
                col = int(fb.col_of[k])
                row[col] = (row.get(col, 0) + int(fb.col_coeff[k])) % C.r
        t.add(row, 0)
        if t.rank == fb.effective_columns:
            break
    return t.rank


def coupon_time(rates: list[float]) -> tuple[float, float] | None:
    """(mean, sd) of the attempts until every column with per-attempt hit rate rates[j] is hit:
    E[T] = int_0^inf S(t) dt and E[T^2] = int_0^inf 2t S(t) dt, S(t) = 1 - prod_j (1 - e^(-rate_j t))."""
    if not rates:
        return 0.0, 0.0
    if min(rates) <= 0:
        return None
    t_max = 12.0 / min(rates) + 12.0 * sum(1.0 / r for r in rates) / len(rates)
    steps = 4000
    m1 = m2 = 0.0
    prev_t, prev_f = 0.0, 1.0
    for i in range(1, steps + 1):
        t = t_max * (i / steps) ** 2
        f = 1.0 - math.prod(1.0 - math.exp(-r * t) for r in rates)
        m1 += (t - prev_t) * (f + prev_f) / 2
        m2 += (t - prev_t) * (t * f + prev_t * prev_f)
        prev_t, prev_f = t, f
    return m1, math.sqrt(max(0.0, m2 - m1 * m1))


def column_hit_rates(fb: FactorBase) -> list[float] | None:
    """Exact per-attempt rate at which an ordinary subgroup target has an m = 2 decomposition
    touching each column (from psi-filtered pair sums)."""
    C, K = fb.curve, fb.curve.K
    if len(fb.xs) * (len(fb.xs) + 1) // 2 > 3_000_000:
        return None
    px, py = C.psi(fb.xs, fb.ys)
    sx, _ = K.pair_sums(fb.xs, fb.ys)
    qx, _ = K.pair_sums(px, py)
    ok = (qx == np.uint64(kernel.INF_X)) & (sx != np.uint64(kernel.INF_X))
    i, j = np.triu_indices(len(fb.xs))
    rates = np.zeros(fb.effective_columns)
    for col in (fb.col_of[i[ok]], fb.col_of[j[ok]]):
        col = col[col >= 0]
        np.add.at(rates, col, 1.0)
    return (rates / (C.r - 1)).tolist()


class CollectionMonitor:
    """Rolling heuristics over a stream of PDP attempts."""

    def __init__(self, columns: int, target_rank: int | None = None, predicted: dict | None = None, window: int = 500):
        self.columns = columns
        self.target_rank = columns if target_rank is None else target_rank
        self.predicted = predicted or {}
        self.window = window
        self.attempts = 0
        self.status: Counter = Counter()
        self.D_by_status: dict[str, Counter] = {}
        self.costs: list[int] = []
        self.walls: list[int] = []
        self.relations = 0
        self.novel = 0
        self.rank = 0
        self.recent: deque = deque(maxlen=window)
        self.per_degree_costs: list[list[tuple[int, int]]] = []
        self.success_degrees: list[int] = []
        self.rank_trajectory: list[tuple[int, int]] = [(0, 0)]
        self.covered: set[int] = set()
        self.weights: list[int] = []

    def observe(self, rec: dict) -> None:
        """rec: status, D (or None), cost, wall_ns, relations, novel, per_degree [(D, cost), ...],
        and optionally rows: the column sets of the relations found."""
        self.attempts += 1
        for cols in rec.get("rows", []):
            self.covered |= set(cols)
            self.weights.append(len(cols))
        st = rec["status"]
        self.status[st] += 1
        self.D_by_status.setdefault(st, Counter())[rec.get("D")] += 1
        self.costs.append(rec["cost"])
        self.walls.append(rec.get("wall_ns", 0))
        self.relations += rec.get("relations", 0)
        self.novel += rec.get("novel", 0)
        if rec.get("novel"):
            self.rank += rec["novel"]
            self.rank_trajectory.append((self.attempts, self.rank))
        self.recent.append((rec.get("relations", 0) > 0, rec.get("novel", 0), rec["cost"]))
        self.per_degree_costs.append(rec.get("per_degree", []))
        if rec.get("relations", 0) and rec.get("D") is not None:
            self.success_degrees.append(rec["D"])

    # ------------------------------------------------------------------ summaries
    def _abort_table(self) -> list[dict]:
        if not self.success_degrees:
            return []
        degrees = sorted({D for pd in self.per_degree_costs for D, _ in pd})
        out = []
        found = len(self.success_degrees)
        for Da in degrees:
            cost = statistics.fmean(sum(c for D, c in pd if D <= Da) for pd in self.per_degree_costs)
            kept = sum(1 for D in self.success_degrees if D <= Da)
            rate = kept / self.attempts
            out.append({"D_abort": Da, "ops_per_attempt": cost, "relations_kept": kept / found,
                        "ops_per_relation": cost / rate if rate else None})
        return out

    def yield_estimate(self) -> float | None:
        """Relations per attempt: a Beta prior with mean equal to the predicted yield and the
        weight of two relations, updated by the observed attempts (falls back to the raw rate)."""
        hits = self.status.get("verified_decomposition", 0)
        p0 = self.predicted.get("p_decomposable")
        if p0:
            return (hits + 2) / (self.attempts + 2 / p0)
        return hits / self.attempts if self.attempts else None

    def summary(self) -> dict:
        n = self.attempts
        succ = sum(1 for s, _, _ in self.recent if s)
        novel_recent = sum(v for _, v, _ in self.recent)
        cost_mean = statistics.fmean(self.costs) if self.costs else None
        novel_rate = novel_recent / len(self.recent) if self.recent else 0.0
        remaining = max(0, self.target_rank - self.rank)
        p_hat = self.yield_estimate()
        successes = self.status.get("verified_decomposition", 0)
        q_hat = (self.novel + 1) / (successes + 1)
        # rank deficit at the observed novel fraction, or covering the untouched columns with
        # relations of the observed weight w (coupon collector: (C/w) * H_u relations), whichever is larger
        w = statistics.fmean(self.weights) if self.weights else 2.0
        uncovered = max(0, self.columns - len(self.covered))
        rates = self.predicted.get("column_rates")
        projected_attempts = projected_sd = None
        if p_hat:
            deficit = (remaining / q_hat) / p_hat if remaining else 0.0
            if rates:
                moments = coupon_time([rates[j] for j in range(self.columns) if j not in self.covered])
            else:
                cover = (self.columns / max(w, 1.0)) * sum(1.0 / i for i in range(1, uncovered + 1)) / p_hat
                moments = (cover, None)
            if moments is not None:
                projected_attempts = max(deficit, moments[0])
                projected_sd = moments[1] if moments[0] >= deficit else None
        abort = self._abort_table()
        best = min((a for a in abort if a["ops_per_relation"] is not None), key=lambda a: a["ops_per_relation"], default=None)
        pred_D = self.predicted.get("expected_D_solve")
        obs_D = [D for c in self.D_by_status.values() for D, k in c.items() for _ in range(k) if D is not None]
        return {
            "attempts": n,
            "status": dict(self.status),
            "yield_per_attempt": self.status.get("verified_decomposition", 0) / n if n else None,
            "yield_wilson95": wilson95(self.status.get("verified_decomposition", 0), n),
            "predicted_yield": self.predicted.get("p_decomposable"),
            "recent_window": len(self.recent),
            "recent_yield": succ / len(self.recent) if self.recent else None,
            "yield_estimate": p_hat,
            "novel_fraction_estimate": q_hat,
            "uncovered_columns": uncovered,
            "mean_relation_weight": w,
            "novel_rows_per_attempt_recent": novel_rate,
            "relations": self.relations,
            "novel_rows": self.novel,
            "rank": self.rank,
            "target_rank": self.target_rank,
            "D_hist": {st: {str(k): v for k, v in sorted(c.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))}
                       for st, c in self.D_by_status.items()},
            "D_mean_observed": statistics.fmean(obs_D) if obs_D else None,
            "D_mean_predicted": pred_D,
            "D_drift": (statistics.fmean(obs_D) - pred_D) if obs_D and pred_D is not None else None,
            "ops_per_attempt_mean": cost_mean,
            "ops_per_attempt_ci95": bootstrap_mean_ci(self.costs[-2000:], "monitor"),
            "ops_per_relation": sum(self.costs) / self.relations if self.relations else None,
            "ops_per_novel_row": sum(self.costs) / self.novel if self.novel else None,
            "projected_attempts_to_target": projected_attempts,
            "projected_attempts_sd": projected_sd,
            "projected_ops_to_target": projected_attempts * cost_mean if projected_attempts is not None and cost_mean else None,
            "abort_policy": abort,
            "best_abort": best,
        }

    def render(self) -> str:
        s = self.summary()
        y = s["yield_per_attempt"] or 0.0
        ci = s["yield_wilson95"] or [0, 0]
        eta = s["projected_attempts_to_target"]
        best = s["best_abort"]
        return (
            f"[{s['attempts']:6d}] rank {s['rank']}/{s['target_rank']} yield {y:.4f} [{ci[0]:.4f},{ci[1]:.4f}]"
            + (f" (pred {s['predicted_yield']:.4f})" if s["predicted_yield"] is not None else "")
            + f" novel/att {s['novel_rows_per_attempt_recent']:.4f} ops/att {s['ops_per_attempt_mean']:.3g}"
            + (f" ops/row {s['ops_per_novel_row']:.3g}" if s["ops_per_novel_row"] else "")
            + (f" D {s['D_mean_observed']:.2f}" if s["D_mean_observed"] is not None else "")
            + (f" (pred {s['D_mean_predicted']:.2f})" if s["D_mean_predicted"] is not None else "")
            + (f" eta {eta:.0f}" + (f"±{s['projected_attempts_sd']:.0f}" if s["projected_attempts_sd"] else "") + " att"
               if eta is not None else "")
            + (f" best abort D={best['D_abort']}" if best else "")
        )


# ------------------------------------------------------------------ collection run
def collect(args, workload: dict | None = None, meter: opcount.Meter | None = None) -> dict:
    """Collect relations to the achievable rank, solve mod r, and descend fresh targets.

    Every phase runs inside `meter` (exclusive wall time and operation counters).  When a
    query has S >= 1 solutions, the exhaustive enumeration supplies the count the degree scan
    uses as its completion test and the solutions read off after it, so it is charged to the
    phase it serves (pdp or target_descent) as `anf_op`.  With S = 0 the scan refutes without
    reading S, so that enumeration stays in `instrument` with the diagnostics.

    `workload` (see ../ic-bench) fixes the query stream, the targets and their
    rerandomization streams independently of the factor base, so bases pair on it.
    Without one, the streams are keyed by the factor-base digest as in results/collect.jsonl.
    """
    meter = meter or opcount.Meter()
    t_all = time.perf_counter_ns()
    with meter.phase("setup"):
        C = ToyCurve(args.n)
    if workload is not None and workload["curve_id"] != C.curve_id:
        raise ValueError(f"workload is for {workload['curve_id']}, not {C.curve_id}")
    with meter.phase("factor_base"):
        fb = FactorBase(C, args.family, args.l, args.seed)
    with meter.phase("precompute"):
        P = Pieces(fb, args.m)
        achievable = achievable_rank(fb, args.m)
    with meter.phase("instrument"):
        struct = P.structure()
        exact = exact_subgroup_yield(fb, args.m)
        pred = {**predictions(args.n, args.m, args.l, struct), **predicted_yield(fb, args.m)}
        if exact:
            pred["p_decomposable"] = exact["p_decomposable"]
        if args.m == 2:
            pred["column_rates"] = column_hit_rates(fb)
    columns = fb.effective_columns
    target_rank = columns if achievable is None else achievable
    mon = CollectionMonitor(columns, target_rank=target_rank, predicted=pred)
    tracker = RankTracker(columns, C.r)
    limits = macaulay.Limits(d_max=args.abort_degree or args.d_max, max_cols=args.max_cols, max_rows=args.max_rows)
    if workload is None:
        rng = random.Random(f"collect|{fb.digest}|{args.m}|{args.workload_seed}")
    else:
        rng = random.Random(workload["query_stream"])

    def decompose(R: tuple[int, int], charge: str) -> tuple[dict, set]:
        with meter.phase("queries" if charge == "pdp" else charge):
            s = P.system(R[0])
        with meter.phase("instrument") as ops:
            before, t0 = ops.copy(), time.perf_counter_ns()
            S, sols = s.solutions()
            enum_ops, enum_ns = ops - before, time.perf_counter_ns() - t0
        # with S = 0 the scan never reads S (it runs to its refutation), so the enumeration is a check
        if S >= 1:
            meter.move("instrument", charge, enum_ops, enum_ns)
        with meter.phase(charge) as ops:
            scan = macaulay.degree_scan(s, S, limits, mode=args.mode)
            ops["mac_op"] += scan["xors"] + scan["build_ops"]
        rows: set = set()
        status = {"refuted": "proved_unsat", "solved": "solved"}.get(scan["status"], "budget")
        if status == "solved":
            with meter.phase("relation_check" if charge == "pdp" else charge):
                for v in sols.tolist():
                    c = classify_solution(fb, args.m, R, v)
                    if c["status"] in ("verified", "improper"):
                        rows.add(tuple(sorted(relation_row(fb, c["points"]).items())))
            status = "verified_decomposition" if rows else "lift_rejected"
        return {"status": status, "scan": scan}, rows

    trace = []
    snapshots: list[dict] = []
    while mon.attempts < args.max_attempts and tracker.rank < target_rank:
        with meter.phase("queries"):
            k, R = C.random_subgroup_point(rng)
        res, rows = decompose(R, "pdp")
        scan = res["scan"]
        rels = novel = 0
        with meter.phase("matrix_build"):
            for row in rows:
                rels += 1
                novel += tracker.add(dict(row), k)
        rec = {
            "status": res["status"],
            "D": scan["D_solve"],
            "cost": scan["xors"] + scan["build_ops"],
            "wall_ns": scan["wall_ns"],
            "relations": rels,
            "novel": novel,
            "rows": [[j for j, _ in row] for row in rows],
            "per_degree": [(r["D"], r["xors"] + r["build_ops"]) for r in scan["per_degree"]],
        }
        mon.observe(rec)
        trace.append({"attempt": mon.attempts, "k": k, "status": res["status"], "D": scan["D_solve"],
                      "cost": rec["cost"], "relations": rels, "novel": novel, "rank": tracker.rank})
        if novel or (args.report_every and mon.attempts % args.report_every == 0):
            s = mon.summary()
            snapshots.append({"attempt": mon.attempts, "rank": tracker.rank,
                              "projected_attempts": s["projected_attempts_to_target"],
                              "projected_sd": s["projected_attempts_sd"],
                              "yield_estimate": s["yield_estimate"]})
        if args.report_every and mon.attempts % args.report_every == 0:
            print(mon.render(), file=sys.stderr, flush=True)
    if args.report_every:
        print(mon.render(), file=sys.stderr, flush=True)
    complete = tracker.rank >= target_rank
    with meter.phase("relation_la"):
        logs = tracker.solve()
    verified_logs = None
    if tracker.rank == columns:
        with meter.phase("recovery_check"):
            verified_logs = all(C.K.smul(C.G, logs[j]) == rep for j, rep in enumerate(fb.column_reps))
    # target descent: Q + [a]G until it decomposes; with a kernel in the relation matrix the
    # log of every decomposable subgroup point is still determined
    def target_stream():
        if workload is None:
            drng = random.Random(f"descent|{fb.digest}|{args.m}|{args.workload_seed}")
            for _ in range(args.descent_targets):
                s_true, Q = C.random_subgroup_point(drng)
                yield s_true, Q, drng
        else:
            for i, (s_true, qx, qy) in enumerate(workload["targets"]):
                yield s_true, (qx, qy), random.Random(f"{workload['rerandomization_stream']}|{i}")

    descents = []
    for s_true, Q, arng in target_stream() if complete else []:
        tries = 0
        found = None
        before = meter.ops.get("target_descent", Counter()).copy()
        while tries < args.max_attempts and found is None:
            tries += 1
            with meter.phase("target_descent"):
                a = arng.randrange(1, C.r)
                Qa = C.K.add(Q, C.K.smul(C.G, a))
            if Qa[0] == kernel.INF_X:
                continue
            res, rows = decompose(Qa, "target_descent")
            if rows:
                row = dict(next(iter(rows)))
                with meter.phase("target_descent") as ops:
                    found = (sum(c * logs[j] for j, c in row.items()) - a) % C.r
                    ops["modr_mul"] += len(row)
        ok = None
        if found is not None:
            with meter.phase("recovery_check"):
                ok = C.K.smul(C.G, found) == Q
        descents.append({"attempts": tries, "recovered": found is not None, "verified": ok,
                         "matches_workload": None if workload is None else found == s_true,
                         "ops": dict(meter.ops.get("target_descent", Counter()) - before)})
    summary = mon.summary()
    out = {
        "schema": "pdp-collection-run/2",
        "kind": "stage",
        "candidate_id": None,
        "curve_id": C.curve_id,
        "cell": {"n": args.n, "m": args.m, "l": args.l, "family": args.family, "seed": args.seed, "mode": args.mode,
                 "abort_degree": args.abort_degree, "workload_seed": args.workload_seed},
        "factor_base": fb.record(),
        "factor_base_sha256": fb.digest,
        "effective_columns": columns,
        "achievable_rank": achievable,
        "predictions": pred,
        "exact_yield": exact,
        "monitor": summary,
        "snapshots": snapshots,
        "final_rank": tracker.rank,
        "collection_complete": complete,
        "factor_base_logs_verified": verified_logs,
        "descents": descents,
        "dlp_verified": bool(descents) and all(d["verified"] for d in descents),
        "relation_linear_algebra": "dense Gaussian elimination mod r (RankTracker); free columns set to 0",
        "target_descent": "Q + [a]G with fresh random a until the PDP solver decomposes it",
        "phase_wall_ns": {k: v for k, v in meter.wall_ns.items() if k != "instrument"},
        "phase_ops": {k: dict(v) for k, v in meter.ops.items() if k != "instrument"},
        "instrument_wall_ns": meter.wall_ns.get("instrument", 0),
        "wall_ns": time.perf_counter_ns() - t_all,
        "implementation_sha256": implementation_sha256(),
    }
    if args.out:
        with open(args.out, "a") as fh:
            fh.write(canonical(out) + "\n")
    if args.trace:
        with open(args.trace, "w") as fh:
            for t in trace:
                fh.write(json.dumps(t) + "\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="collect relations to the achievable rank with the monitor, solve, and descend fresh targets")
    c.add_argument("--n", type=int, required=True)
    c.add_argument("--m", type=int, default=2)
    c.add_argument("--l", type=int, required=True)
    c.add_argument("--family", default="prefix")
    c.add_argument("--seed", type=int, default=1)
    c.add_argument("--mode", default="mxl", choices=macaulay.MODES)
    c.add_argument("--abort-degree", type=int, default=0, help="stop each query at this degree (0 = no abort)")
    c.add_argument("--d-max", type=int, default=10)
    c.add_argument("--max-cols", type=int, default=40_000)
    c.add_argument("--max-rows", type=int, default=200_000)
    c.add_argument("--max-attempts", type=int, default=200_000)
    c.add_argument("--workload-seed", type=int, default=1)
    c.add_argument("--descent-targets", type=int, default=3, help="fresh targets to descend and verify")
    c.add_argument("--report-every", type=int, default=500)
    c.add_argument("--out", default="")
    c.add_argument("--trace", default="")
    args = ap.parse_args()
    if args.cmd == "collect":
        res = collect(args)
        m = res["monitor"]
        print(json.dumps({k: res[k] for k in ("curve_id", "cell", "effective_columns", "achievable_rank", "final_rank",
                                              "factor_base_logs_verified", "dlp_verified", "descents")}
                         | {"attempts": m["attempts"], "yield": m["yield_per_attempt"], "novel_rows": m["novel_rows"],
                            "ops_per_novel_row": m["ops_per_novel_row"], "best_abort": m["best_abort"]}, indent=1))


if __name__ == "__main__":
    main()
