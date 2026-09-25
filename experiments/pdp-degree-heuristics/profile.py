#!/usr/bin/env python3
"""Profile factor bases: exact relation yield and exact PDP degree statistics per base.

    python3 profile.py --n 19 --m 2 --l 5,6,7 --families prefix,geometric,random \
        --seeds 1,2 --targets 40 --planted 8 --out results/n19_m2.jsonl

Every factor base of a cell sees the same frozen workload of ordinary targets R = [k]G
(k uniform on [1, r-1]), so rows pair on (curve, workload) with the factor base as the
declared variable.  One JSON line per (factor base, workload) run is appended to --out;
--trace keeps one line per target.  These are PDP-stage profiles: candidate_id is null
(no relation linear algebra or target descent is run) and every derived cost is labelled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import resource
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import kernel  # noqa: E402
import macaulay  # noqa: E402
import satengine  # noqa: E402
from descent import Pieces  # noqa: E402
from factor_base import FactorBase  # noqa: E402
from relations import Oracle, classify_solution, exact_subgroup_yield, predicted_yield  # noqa: E402
from toycurve import ToyCurve, canonical, sha256_hex  # noqa: E402

SCHEMA = "pdp-degree-profile/1"
SOURCES = [
    HERE / "pdpkernel.c",
    HERE / "kernel.py",
    HERE / "toycurve.py",
    HERE / "factor_base.py",
    HERE / "descent.py",
    HERE / "macaulay.py",
    HERE / "relations.py",
    HERE / "satengine.py",
    HERE / "profile.py",
    HERE.parent / "pdp-scaling" / "sumpoly.py",
    HERE.parent / "pdp-scaling" / "gf2n.py",
]


def source_digests() -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES}


def implementation_sha256() -> str:
    return sha256_hex({"sources": source_digests(), "cflags": kernel.CFLAGS})


# ------------------------------------------------------------------ records
def workload(curve: ToyCurve, seed: int, count: int) -> tuple[str, dict, list[list[int]]]:
    rng = random.Random(f"workload|{curve.curve_id}|{seed}")
    targets = []
    for _ in range(count):
        k, R = curve.random_subgroup_point(rng)
        targets.append([k, R[0], R[1]])
    record = {
        "curve_id": curve.curve_id,
        "subgroup_order": curve.r,
        "target_law": "R = [k]G with k uniform on [1, r-1] (ordinary nonzero subgroup points)",
        "seed": seed,
        "target_count": count,
        "targets_sha256": sha256_hex(targets),
        "cache_state": "cold",
    }
    return sha256_hex(record)[:12], record, targets


def pdp_config(m: int, limits: macaulay.Limits) -> dict:
    return {
        "summands": m,
        "summation_polynomial": f"S_{m + 1} by iterated resultants (experiments/pdp-scaling/sumpoly.py)",
        "weil_descent": "x_i = sum_j v_ij beta_j over the factor-base basis; v^2 = v",
        "equation_order": "equation t is bit t of each F_2^n coefficient, t = 0..n-1",
        "solver_family": "xl",
        "solver": "incremental dense Macaulay degree scan over F_2[x]/(x_i^2 + x_i); stop at "
        "refutation (1 in row space) or Groebner completion (standard monomials = #solutions)",
        "monomial_order": "grevlex, x_0 > ... > x_(N-1), multilinear",
        "internal_kernel": "pdpkernel.c incremental echelon with highest-bit pivots",
        "limits": {"d_max": limits.d_max, "max_cols": limits.max_cols, "max_rows": limits.max_rows},
        "cache_policy": "target-independent descent pieces cached per factor base",
    }


def stage_id(fb: FactorBase, m: int, config: dict) -> str:
    digest = sha256_hex({"factor_base": fb.record(), "point_decomposition": config})
    return f"PS1N{fb.curve.n}C{fb.curve.tag}fb{fb.usable_points}PDP{m}xlh{digest[:12]}"


# ------------------------------------------------------------------ workers
_CTX: dict = {}


def _context(cfg: dict):
    key = (cfg["n"], cfg["family"], cfg["l"], cfg["seed"], cfg["m"])
    if key not in _CTX:
        if len(_CTX) > 8:
            _CTX.clear()
        t0 = time.perf_counter_ns()
        C = ToyCurve(cfg["n"])
        t1 = time.perf_counter_ns()
        fb = FactorBase(C, cfg["family"], cfg["l"], cfg["seed"])
        t2 = time.perf_counter_ns()
        P = Pieces(fb, cfg["m"])
        t3 = time.perf_counter_ns()
        try:
            O = Oracle(fb, cfg["m"])
        except ValueError:
            O = None
        _CTX[key] = (C, fb, P, O, {"setup_ns": t1 - t0, "factor_base_ns": t2 - t1, "precompute_ns": t3 - t2})
    return _CTX[key]


def _limits(cfg: dict) -> macaulay.Limits:
    return macaulay.Limits(**cfg["limits"])


def task_structure(cfg: dict) -> dict:
    C, fb, P, O, times = _context(cfg)
    m = cfg["m"]
    t0 = time.perf_counter_ns()
    exact = exact_subgroup_yield(fb, m) if cfg.get("exact_yield", True) else None
    t_exact = time.perf_counter_ns() - t0
    struct = P.structure()
    return {
        "times": {**times, "exact_yield_ns": t_exact},
        "factor_base": fb.record(),
        "factor_base_sha256": fb.digest,
        "label": fb.label,
        "invariants": fb.invariants(kmax=max(3, m)),
        "structure": struct,
        "exact_yield": exact,
        "predicted_yield": predicted_yield(fb, m),
        "usable_points": fb.usable_points,
        "effective_columns": fb.effective_columns,
    }


def _planted_target(C: ToyCurve, fb: FactorBase, m: int, rng: random.Random) -> tuple[int, int] | None:
    usable = [i for i in range(len(fb.xs)) if fb.usable[i]]
    if len(usable) < m:
        return None
    for _ in range(20000):
        idx = rng.sample(usable, m)
        if len({int(fb.xs[i]) for i in idx}) < m:
            continue
        R = (kernel.INF_X, 0)
        for i in idx:
            R = C.K.add(R, (int(fb.xs[i]), int(fb.ys[i])))
        if R[0] != kernel.INF_X and C.in_subgroup(R):
            return R
    return None


def task_target(cfg: dict, kind: str, index: int, target: list[int] | None) -> dict:
    C, fb, P, O, _ = _context(cfg)
    m = cfg["m"]
    if kind == "planted":
        rng = random.Random(f"planted|{fb.digest}|{m}|{index}")
        R = _planted_target(C, fb, m, rng)
        if R is None:
            return {"kind": kind, "index": index, "status": "no_planted_target"}
        scalar = None
    else:
        scalar, R = target[0], (target[1], target[2])
    rec: dict = {"kind": kind, "index": index, "scalar": scalar}
    t0 = time.perf_counter_ns()
    s = P.system(R[0])
    rec["descent_ns"] = time.perf_counter_ns() - t0
    rec["equations"] = len(s.equations)
    rec["monomials"] = s.monomials
    rec["degree"] = s.top_degree
    t0 = time.perf_counter_ns()
    S, sols = s.solutions(max_out=cfg.get("max_solutions", 4096))
    rec["bruteforce_ns"] = time.perf_counter_ns() - t0
    rec["solutions"] = S
    t0 = time.perf_counter_ns()
    cls = [classify_solution(fb, m, R, v) for v in sols[: cfg.get("max_classify", 256)].tolist()]
    rec["verify_ns"] = time.perf_counter_ns() - t0
    sc = Counter(c["status"] for c in cls)
    rec["solution_status"] = dict(sc)
    rec["classified"] = len(cls)
    rec["oracle_ordered"] = O.ordered_count(R) if O is not None else None
    rational = sc.get("verified", 0) + sc.get("improper", 0)
    if rec["oracle_ordered"] is not None:
        rec["oracle_agrees"] = (rec["oracle_ordered"] > 0) == (rational > 0) or len(cls) < S
    rec["scan"] = {}
    rec["pdp_status"] = {}
    for mode in cfg.get("modes", ["xl", "mxl"]):
        scan = macaulay.degree_scan(s, S, _limits(cfg), mode=mode)
        rec["scan"][mode] = scan
        if scan["status"] == "refuted":
            assert S == 0, "refutation of a satisfiable system"
            rec["pdp_status"][mode] = "proved_unsat"
        elif scan["status"] == "solved":
            rec["pdp_status"][mode] = "verified_decomposition" if rational else "lift_rejected"
        else:
            rec["pdp_status"][mode] = "budget"
    if cfg.get("dreg") and index < cfg.get("dreg_targets", 8):
        rec["dreg"] = macaulay.homogeneous_regularity(s, macaulay.Limits(**cfg.get("dreg_limits", cfg["limits"])))
    if cfg.get("sat"):
        rec["sat"] = satengine.solve(s, cfg.get("sat_time_limit", 10.0))
    return rec


def _run_task(args):
    kind = args[0]
    if kind == "structure":
        return task_structure(args[1])
    return task_target(*args[1:])


# ------------------------------------------------------------------ statistics
def wilson95(k: int, n: int) -> list[float] | None:
    if n == 0:
        return None
    z = 1.959963984540054
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def bootstrap_mean_ci(values: list[float], seed: str, draws: int = 2000) -> list[float] | None:
    if len(values) < 3:
        return None
    rng = random.Random(seed)
    k = len(values)
    means = sorted(sum(rng.choices(values, k=k)) / k for _ in range(draws))
    return [means[int(0.025 * draws)], means[int(0.975 * draws) - 1]]


def hist(values) -> dict[str, int]:
    return {str(k): v for k, v in sorted(Counter(values).items(), key=lambda kv: (kv[0] is None, kv[0] if kv[0] is not None else 0))}


def mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def cumulative_ops(scan: dict, D_abort: int) -> int:
    return sum(r["xors"] + r["build_ops"] for r in scan["per_degree"] if r["D"] <= D_abort)


def predictions(n: int, m: int, l: int, struct: dict) -> dict:
    """Structure-only predictors of the solving degree (no targets needed)."""
    N = m * l
    d = struct["system_degree"]
    omega, omega_top = struct["omega"], struct["omega_top"]
    k1 = max(0, n - omega_top)
    d_low = struct.get("fallen_degree", 1 if m == 2 else d - 1) or 1
    sr = macaulay.semi_regular_dreg(N, [d] * n)
    fall = macaulay.semi_regular_dreg(N, [d] * (n - min(k1, n)) + [d_low] * min(k1, n))
    if n < omega:
        p_base = 2.0 ** (n - omega)
    else:
        p_base = 1.0
        for i in range(omega):
            p_base *= 1 - 2.0 ** (i - n)
    expected = None
    if fall is not None:
        expected = p_base * d + (1 - p_base) * max(fall, d)
    return {
        "semi_regular_dreg": sr,
        "fall_adjusted_dreg": fall,
        "base_fall_count": k1,
        "fallen_degree": d_low,
        "linearization_excess": n - (omega - 1),
        "p_base_refutation": p_base,
        "expected_D_solve": expected,
    }


def mode_stats(mode: str, ordinary: list[dict], planted: list[dict], p_dec: float, d_max: int, seed: str) -> dict:
    """Degree, status and cost statistics of one solver mode over the same targets."""
    scans = [r["scan"][mode] for r in ordinary]
    status = Counter(r["pdp_status"][mode] for r in ordinary)
    resolved = [(r, s) for r, s in zip(ordinary, scans) if s["D_solve"] is not None]
    unsat = [s for r, s in resolved if r["pdp_status"][mode] == "proved_unsat"]
    sat_like = [s for r, s in resolved if r["pdp_status"][mode] != "proved_unsat"]
    base_ref = sum(1 for r, s in resolved if r["pdp_status"][mode] == "proved_unsat" and s["D_solve"] <= r["degree"])
    ops = [s["xors"] + s["build_ops"] for s in scans]
    walls = [s["wall_ns"] for s in scans]
    pscans = [r["scan"][mode] for r in planted]
    planted_D = [s["D_solve"] for s in pscans]
    first = [s["per_degree"][0] for s in scans if s["per_degree"]]
    base = min((f["D"] for f in first), default=None)
    top = max([s["max_degree_built"] or 0 for s in scans + pscans] + [base or 0])
    abort = []
    if base is not None and planted:
        for Da in range(base, top + 1):
            cost = statistics.fmean(cumulative_ops(s, Da) for s in scans)
            kept = sum(1 for D in planted_D if D is not None and D <= Da) / len(planted)
            p_rel = p_dec * kept
            abort.append({
                "D_abort": Da,
                "ordinary_resolved": sum(1 for s in scans if s["D_solve"] is not None and s["D_solve"] <= Da) / len(scans),
                "planted_resolved": kept,
                "ops_per_attempt": cost,
                "ops_per_relation": cost / p_rel if p_rel > 0 else None,
            })
    best = min((a for a in abort if a["ops_per_relation"] is not None), key=lambda a: a["ops_per_relation"], default=None)
    mean_ops = statistics.fmean(ops) if ops else None
    return {
        "status": {
            "pdp_verified": status.get("verified_decomposition", 0),
            "pdp_proved_unsat": status.get("proved_unsat", 0),
            "pdp_budget": status.get("budget", 0),
            "pdp_lift_rejected": status.get("lift_rejected", 0),
        },
        "D_solve_mean": mean(s["D_solve"] for _, s in resolved),
        "D_solve_hist": hist(s["D_solve"] for s in scans),
        "D_solve_unsat_hist": hist(s["D_solve"] for s in unsat),
        "D_solve_sat_hist": hist(s["D_solve"] for s in sat_like),
        "censored": len(scans) - len(resolved),
        "FFD_mean": mean(s["FFD"] for s in scans),
        "FFD_hist": hist(s["FFD"] for s in scans),
        "base_refutations": base_ref,
        "base_refutation_wilson95": wilson95(base_ref, len(scans)),
        "base_fall_mean": mean(f["fall"] for f in first if not f["partial"]),
        "planted_D_solve_hist": hist(planted_D),
        "planted_solved": sum(1 for r in planted if r["pdp_status"][mode] == "verified_decomposition"),
        "ops_per_attempt_mean": mean_ops,
        "ops_per_attempt_median": statistics.median(ops) if ops else None,
        "ops_per_attempt_ci95": bootstrap_mean_ci(ops, seed + mode),
        "wall_ns_per_attempt_mean": statistics.fmean(walls) if walls else None,
        "final_cols_mean": mean(s["final_cols"] for s in scans),
        "final_rows_mean": mean(s["final_rows"] for s in scans),
        "derived_ops_per_relation": mean_ops / p_dec if mean_ops and p_dec else None,
        "abort_policy": abort,
        "best_abort": best,
    }


def summarize(cfg: dict, struct: dict, records: list[dict], wid: str, wrec: dict, run: int) -> dict:
    C = ToyCurve(cfg["n"])
    m, l, n = cfg["m"], cfg["l"], cfg["n"]
    limits = macaulay.Limits(**cfg["limits"])
    modes = cfg.get("modes", ["xl", "mxl"])
    config = pdp_config(m, limits)
    config["modes"] = modes
    fb_record = struct["factor_base"]
    digest = sha256_hex({"factor_base": fb_record, "point_decomposition": config})
    sid = f"PS1N{n}C{C.tag}fb{fb_record['actual_usable_point_count']}PDP{m}xlh{digest[:12]}"
    ordinary = [r for r in records if r["kind"] == "ordinary"]
    planted = [r for r in records if r["kind"] == "planted" and "scan" in r]
    exact = struct["exact_yield"]
    p_dec = exact["p_decomposable"] if exact else struct["predicted_yield"]["p_decomposable"]
    decomposable_sampled = sum(1 for r in ordinary if (r.get("oracle_ordered") or 0) > 0
                               or "verified_decomposition" in r["pdp_status"].values())
    per_mode = {mode: mode_stats(mode, ordinary, planted, p_dec, limits.d_max, sid + wid) for mode in modes}
    lead = per_mode[modes[0]]
    card = {
        "schema": SCHEMA,
        "kind": "stage",
        "candidate_id": None,
        "stage_config_id": sid,
        "curve_id": C.curve_id,
        "workload_id": wid,
        "run_id": f"{sid}W{wid}R{run}",
        "label": struct["label"],
        "cell": {"n": n, "m": m, "l": l, "N": m * l, "family": cfg["family"], "seed": cfg["seed"]},
        "curve": C.summary(),
        "workload": wrec,
        "factor_base": fb_record,
        "factor_base_sha256": struct["factor_base_sha256"],
        "point_decomposition": config,
        "relation_collection": "none",
        "relation_linear_algebra": "none",
        "target_descent": "none",
        "isogeny": "none",
        "structure": {**struct["invariants"], **struct["structure"]},
        "predictions": predictions(n, m, l, struct["structure"]),
        "yield": {
            "exact": exact,
            "predicted": struct["predicted_yield"],
            "p_decomposable_used": p_dec,
            "p_decomposable_source": "exact_whole_subgroup" if exact else "predicted",
            "sampled_decomposable": decomposable_sampled,
            "sampled_targets": len(ordinary),
            "sampled_wilson95": wilson95(decomposable_sampled, len(ordinary)),
            "oracle_agreement": sum(1 for r in ordinary if r.get("oracle_agrees", True)),
        },
        "counts": {
            "ordinary_queries": len(ordinary),
            "pdp_attempts": len(ordinary),
            **lead["status"],
            "pdp_timeout": 0,
            "pdp_error": 0,
            "algebraic_solutions": sum(r["solutions"] for r in ordinary),
            "solution_status": dict(sum((Counter(r["solution_status"]) for r in ordinary), Counter())),
            "planted": len(planted),
        },
        "degrees": {
            mode: {k: v for k, v in st.items() if not k.startswith(("ops_", "wall_", "final_", "derived_", "abort", "best_", "status"))}
            for mode, st in per_mode.items()
        },
        "cost": {
            "unit": "64-bit word XORs in elimination + monomial insertions in row building",
            "derived_ops_per_relation_note": "mean ordinary-attempt cost / decomposition probability; derived, not a collection run",
            **{mode: {k: v for k, v in st.items() if k.startswith(("ops_", "wall_", "final_", "derived_", "abort", "best_"))}
               for mode, st in per_mode.items()},
        },
        "sat_engine": None,
        "phase_wall_ns": {
            "setup": struct["times"]["setup_ns"],
            "factor_base": struct["times"]["factor_base_ns"],
            "precompute": struct["times"]["precompute_ns"],
            "queries": sum(r["descent_ns"] for r in ordinary),
            **{f"pdp_{mode}": sum(r["scan"][mode]["wall_ns"] for r in ordinary) for mode in modes},
            "relation_check": sum(r["verify_ns"] for r in ordinary),
            "matrix_build": None,
            "relation_la": None,
            "target_descent": None,
            "recovery_check": None,
            "instrument_bruteforce": sum(r["bruteforce_ns"] for r in ordinary),
            "instrument_exact_yield": struct["times"]["exact_yield_ns"],
        },
        "provenance": {
            "implementation_sha256": implementation_sha256(),
            "sources": source_digests(),
            "kernel_cflags": kernel.CFLAGS,
            "host_id": platform.node(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "workload_fixture_sha256": sha256_hex(wrec),
        },
    }
    dregs = [r["dreg"] for r in ordinary if "dreg" in r]
    if dregs:
        card["degrees"]["homogeneous"] = {
            "D_reg_emp_hist": hist(d["D_reg"] for d in dregs),
            "D_reg_emp_mean": mean(d["D_reg"] for d in dregs),
            "measured_targets": len(dregs),
        }
    sats = [r["sat"] for r in ordinary if "sat" in r]
    if sats:
        card["sat_engine"] = {
            "engine": "pycryptosat",
            "status": dict(Counter(s["status"] for s in sats)),
            "cpu_s_mean": mean(s.get("cpu_s") for s in sats),
            "cpu_s_median": statistics.median([s.get("cpu_s", 0.0) for s in sats]),
        }
    return card


# ------------------------------------------------------------------ driver
def run(args) -> list[dict]:
    families = args.families.split(",")
    seeds = [int(s) for s in args.seeds.split(",")]
    limits = {"d_max": args.d_max, "max_cols": args.max_cols, "max_rows": args.max_rows}
    cards = []
    ns = [int(v) for v in args.n.split(",")]
    ls = []
    for part in args.l.split(","):
        if "-" in part:
            a, b = part.split("-")
            ls += list(range(int(a), int(b) + 1))
        else:
            ls.append(int(part))
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for n in ns:
            C = ToyCurve(n)
            wid, wrec, targets = workload(C, args.workload_seed, args.targets)
            for l in ls:
                if args.m * l > args.max_vars:
                    continue
                cfgs = []
                for fam in families:
                    for seed in (seeds if fam not in ("prefix",) else [0]):
                        cfg = {
                            "n": n, "m": args.m, "l": l, "family": fam, "seed": seed, "limits": limits,
                            "dreg": args.dreg, "dreg_targets": args.dreg_targets,
                            "dreg_limits": {**limits, "d_max": args.dreg_max},
                            "sat": args.sat, "sat_time_limit": args.sat_time_limit,
                            "modes": args.modes.split(","),
                        }
                        try:
                            FactorBase(C, fam, l, seed)
                        except ValueError as exc:
                            print(f"skip {fam} n={n} l={l}: {exc}", file=sys.stderr)
                            continue
                        cfgs.append(cfg)
                futures = []
                for cfg in cfgs:
                    fut_s = pool.submit(_run_task, ("structure", cfg))
                    fut_t = [pool.submit(_run_task, ("target", cfg, "ordinary", i, t)) for i, t in enumerate(targets)]
                    fut_p = [pool.submit(_run_task, ("target", cfg, "planted", i, None)) for i in range(args.planted)]
                    futures.append((cfg, fut_s, fut_t, fut_p))
                for cfg, fut_s, fut_t, fut_p in futures:
                    t0 = time.time()
                    struct = fut_s.result()
                    records = [f.result() for f in fut_t] + [f.result() for f in fut_p]
                    card = summarize(cfg, struct, records, wid, wrec, args.run)
                    card["peak_rss_bytes_main"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
                    cards.append(card)
                    line = canonical(card)
                    if args.out:
                        with open(args.out, "a") as fh:
                            fh.write(line + "\n")
                    if args.trace:
                        with open(args.trace, "a") as fh:
                            for r in records:
                                fh.write(canonical({"run_id": card["run_id"], **r}) + "\n")
                    parts = []
                    for mode in cfg["modes"]:
                        d, c = card["degrees"][mode], card["cost"][mode]
                        parts.append(
                            f"{mode}: D={d['D_solve_hist']} base={d['base_refutations']} ops={c['ops_per_attempt_mean']:.3g}"
                        )
                    print(
                        f"n={n} m={args.m} l={l} {cfg['family']:9s} s={cfg['seed']} B={card['factor_base']['actual_usable_point_count']:4d} "
                        f"cols={card['factor_base']['effective_columns']:4d} prof={card['structure']['product_profile']} "
                        f"omega={card['structure']['omega']:3d} P={card['yield']['p_decomposable_used']:.3g} | "
                        + " | ".join(parts)
                        + f" | pred={card['predictions']['expected_D_solve']}",
                        flush=True,
                    )
    return cards


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", required=True, help="comma-separated field degrees")
    ap.add_argument("--m", type=int, required=True)
    ap.add_argument("--l", required=True, help="dimensions, e.g. 3,4,5 or 3-7")
    ap.add_argument("--families", default="prefix,geometric,random,normal,kertrace")
    ap.add_argument("--seeds", default="1,2")
    ap.add_argument("--targets", type=int, default=40)
    ap.add_argument("--planted", type=int, default=8)
    ap.add_argument("--workload-seed", type=int, default=1)
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--d-max", type=int, default=10)
    ap.add_argument("--max-cols", type=int, default=40_000)
    ap.add_argument("--max-rows", type=int, default=200_000)
    ap.add_argument("--max-vars", type=int, default=20)
    ap.add_argument("--modes", default="xl,mxl", help="Macaulay solver modes to measure (xl, mxl)")
    ap.add_argument("--dreg", action="store_true", help="also measure the homogeneous regularity degree")
    ap.add_argument("--dreg-targets", type=int, default=6)
    ap.add_argument("--dreg-max", type=int, default=10)
    ap.add_argument("--sat", action="store_true", help="also time CryptoMiniSat on every ordinary target")
    ap.add_argument("--sat-time-limit", type=float, default=10.0)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", default="")
    ap.add_argument("--trace", default="")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
