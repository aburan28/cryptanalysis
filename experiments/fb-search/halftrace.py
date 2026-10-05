#!/usr/bin/env python3
"""Two-point decomposition over a subspace by half-trace projection (m = 2, odd n).

On y^2 + xy = x^3 + b the third summation polynomial gives, for a target x-coordinate S != 0 and
symmetric functions u = X + Y, p = X Y of the two summands,

    S_3(X, Y, S) = p^2 + S^2 u^2 + S p + b = 0.

With F = p / S this is the Artin-Schreier equation F^2 + F = (u + sqrt(b)/S)^2, so

    p = S * (HT((u + sqrt(b)/S)^2) + eps),   eps in {0, 1},   Tr(u) = Tr(sqrt(b)/S),

where HT is the half-trace (odd n).  p is an F_2-affine function of u.  The two summands are the
roots of Z^2 + u Z + p, so the problem is: find u, X in V with X^2 + u X + p(u) = 0.

Both X^2 and u X lie in the product space V^(2) = span{v_i v_j}.  Projecting the equation onto
F_2^n / V^(2) removes every nonlinear term and leaves

    pi(p(u)) = 0,        pi : F_2^n -> F_2^(n - dim V^(2)),  ker pi = V^(2),

that is n - dim V^(2) linear equations in the l coordinates of u alone, plus the trace equation.
Their solution space has dimension max(0, l - rank); every u in it gives at most one {X, Y} by one
half-trace, checked for membership in V.  So the decomposition costs 2^(dim) * poly(n), and is a
single linear solve when the linearization excess e = n - dim V - dim V^(2) is >= 0.

Prior art (see PRIOR_ART.md): the half-trace rewrite of S_3 is Courtois (ePrint 2016/003, Sec. 2),
and the equivalent linear oracle in (e1, e2) with e2 in V^(2), its linearization condition
dim V + dim V^(2) <= n and the product-set optimality of the polynomial-degree subspace are in
../linearized-half-decomposition.  Added here: the measured search-dimension law beyond that limit,
with the trace correction, and the use of the oracle as a complete PDP solver in ic-bench (PDP2ht).

    python3 halftrace.py check --n 19 --l 6 --families prefix geometric geomtraceu random --seeds 1-3
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pdp-degree-heuristics"))
sys.path.insert(0, str(HERE.parent / "ic-bench"))
sys.path.insert(0, str(HERE))

import kernel  # noqa: E402
import opcount  # noqa: E402
from factor_base import FactorBase  # noqa: E402
from htsolver import HalfTraceSolver, half_trace  # noqa: E402,F401
from toycurve import ToyCurve, canonical  # noqa: E402


def cmd_check(args) -> None:
    """Compare against the exact decomposition table: same decompositions, candidate count 2^dim."""
    from online import decomposable_points
    from search import decomposition_lookup

    seeds = [int(s) for s in args.seeds.replace("-", ",").split(",")] if "," in args.seeds or "-" not in args.seeds \
        else list(range(int(args.seeds.split("-")[0]), int(args.seeds.split("-")[1]) + 1))
    C = ToyCurve(args.n)
    for fam in args.families:
        for sd in ([1] if fam == "prefix" else seeds):
            fb = FactorBase(C, fam, args.l, sd)
            sv = HalfTraceSolver(fb)
            truth = decomposition_lookup(fb)
            rng = random.Random(f"ht|{fb.digest}")
            pts = list(truth)
            match = mism = 0
            dims = []
            sample = [pts[rng.randrange(len(pts))] for _ in range(min(args.targets, len(pts)))] if pts else []
            for _ in range(args.targets):
                _, R = C.random_subgroup_point(rng)
                sample.append(R)
            for R in sample:
                got = sv.decompose(R)
                _, d = sv.candidates(R[0])
                dims.append(d)
                want_dec = R in truth
                if bool(got) == want_dec:
                    match += 1
                else:
                    mism += 1
            rec = {"n": args.n, "l": args.l, "family": fam, "seed": sd, "dim_V2": sv.dim_V2, "excess": sv.excess(),
                   "predicted_dim": max(0, -sv.excess()), "max_observed_dim": max(dims), "agree": match,
                   "disagree": mism}
            print(canonical(rec), flush=True)


def probe(fb: FactorBase, weights: dict, fails: int = 200, successes: int = 60) -> dict:
    """Priced cost of one half-trace decomposition attempt, failed and successful, and of one
    rerandomization Q + [a]G, under opcount (same classes and prices as the Macaulay pipeline)."""
    import time

    C, K = fb.curve, fb.curve.K
    sv = HalfTraceSolver(fb)
    rng = random.Random(f"ht-probe|{fb.digest}")

    def priced(fn):
        m = opcount.Meter()
        t0 = time.perf_counter_ns()
        with m.phase("x"):
            out = fn()
        return out, sum(m.priced(weights).values()), time.perf_counter_ns() - t0

    _, Q = C.random_subgroup_point(rng)
    fail_ops, fail_wall, rr_ops, dims = [], [], [], []
    while len(fail_ops) < fails:
        Qa, o, _ = priced(lambda: K.add(Q, K.smul(C.G, rng.randrange(1, C.r))))
        rr_ops.append(o)
        if Qa[0] in (kernel.INF_X, 0):
            continue
        got, o, w = priced(lambda: sv.decompose(Qa))
        if got:
            continue
        fail_ops.append(o)
        fail_wall.append(w)
        dims.append(sv.candidates(Qa[0])[1])
    px, py = C.psi(fb.xs, fb.ys)
    psi = list(zip(px.tolist(), py.tolist()))
    succ_ops, succ_wall = [], []
    while len(succ_ops) < successes:
        i, j = rng.randrange(len(fb.xs)), rng.randrange(len(fb.xs))
        if K.add(psi[i], psi[j])[0] != kernel.INF_X:
            continue
        R = K.add((int(fb.xs[i]), int(fb.ys[i])), (int(fb.xs[j]), int(fb.ys[j])))
        if R[0] in (kernel.INF_X, 0):
            continue
        got, o, w = priced(lambda: sv.decompose(R))
        assert got, "a planted decomposition was not found"
        succ_ops.append(o)
        succ_wall.append(w)
    mean = lambda v: sum(v) / len(v)  # noqa: E731
    return {"solver": "PDP2ht", "dim_V2": sv.dim_V2, "excess": sv.excess(),
            "residual_dim_mean": mean(dims), "residual_dim_max": max(dims),
            "c_fail_ops": mean(fail_ops), "c_success_ops": mean(succ_ops), "c_rerandomize_ops": mean(rr_ops),
            "c_fail_wall_ns": mean(fail_wall), "c_success_wall_ns": mean(succ_wall),
            "fails": fails, "successes": successes}


def cmd_compare(args) -> None:
    """Per-attempt cost, half-trace vs the Macaulay pipeline (online.probe), on the same bases."""
    import online
    from relations import predicted_yield

    cal = json.loads(Path(args.calibration).read_text())
    from calibrate import weights_for

    out = open(args.out, "a") if args.out else None
    for n in args.n:
        C = ToyCurve(n)
        w = weights_for(cal, n)
        rho = round((3.141592653589793 * C.r / 2) ** 0.5) * w["ec_add"]
        for l in args.l:
            if l > n // 2:
                continue
            for fam in args.families:
                fb = FactorBase(C, fam, l, args.seed)
                ht = probe(fb, w, args.fails, args.successes)
                mac = None
                if 2 * l <= 26 and not args.no_macaulay:
                    mac = online.probe(fb, w, max(20, args.fails // 4), max(8, args.successes // 4), planted=True)
                p = predicted_yield(fb, 2)["p_decomposable"]
                att = 1 / p
                # rerandomization is paid once per attempt by either solver
                on_ht = (att - 1) * (ht["c_fail_ops"] + ht["c_rerandomize_ops"]) + ht["c_success_ops"] + ht["c_rerandomize_ops"]
                rec = {"schema": "fb-search-halftrace-compare/1", "kind": "prediction", "n": n, "l": l, "family": fam,
                       "seed": args.seed, "calibration_id": cal["calibration_id"], "p_decomposable_predicted": p,
                       "halftrace": ht, "macaulay": mac, "rho_operations": rho,
                       "online_ops_halftrace": on_ht, "online_ratio_to_rho_halftrace": on_ht / rho,
                       "online_ops_macaulay": online.online_prediction(p, mac, "ops")["mean"] if mac else None}
                if mac:
                    rec["online_ratio_to_rho_macaulay"] = rec["online_ops_macaulay"] / rho
                print(f"n{n} l{l:<2d} {fam:10s} e={ht['excess']:+d} dim~{ht['residual_dim_mean']:.1f} "
                      f"c_fail ht={ht['c_fail_ops']:.2e}" + (f" mac={mac['c_fail_ops']:.2e}" if mac else "")
                      + f" c_succ ht={ht['c_success_ops']:.2e}" + (f" mac={mac['c_success_ops']:.2e}" if mac else "")
                      + f" rerand={ht['c_rerandomize_ops']:.2e} online/rho ht={rec['online_ratio_to_rho_halftrace']:.3g}"
                      + (f" mac={rec['online_ratio_to_rho_macaulay']:.3g}" if mac else ""), flush=True)
                if out:
                    out.write(canonical(rec) + "\n")
                    out.flush()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--n", type=int, required=True)
    c.add_argument("--l", type=int, required=True)
    c.add_argument("--families", nargs="+", default=["prefix", "geometric", "geomtraceu", "random"])
    c.add_argument("--seeds", default="1-3")
    c.add_argument("--targets", type=int, default=40)
    cp = sub.add_parser("compare", help="per-attempt and online cost, half-trace vs Macaulay")
    cp.add_argument("--n", type=int, nargs="+", required=True)
    cp.add_argument("--l", type=int, nargs="+", required=True)
    cp.add_argument("--families", nargs="+", default=["prefix", "geomtraceu", "geometric"])
    cp.add_argument("--seed", type=int, default=1)
    cp.add_argument("--fails", type=int, default=200)
    cp.add_argument("--successes", type=int, default=60)
    cp.add_argument("--no-macaulay", action="store_true")
    cp.add_argument("--calibration", default=str(HERE / "results" / "calibration-n19-23-41.json"))
    cp.add_argument("--out", default="")
    args = ap.parse_args()
    {"check": cmd_check, "compare": cmd_compare}[args.cmd](args)


if __name__ == "__main__":
    main()
