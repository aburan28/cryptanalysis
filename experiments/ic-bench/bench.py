#!/usr/bin/env python3
"""End-to-end index-calculus benchmark on toy Koblitz curves, one verified DLP per run.

    python3 bench.py run --suite ci --jobs 4 --out-dir out/          # CSV + receipts
    python3 bench.py run --suite ci --jobs 4 --record                # also history + baseline
    python3 compare.py baseline/ci.csv out/ci.csv                    # regression check

Every cell is a complete IC pipeline: build the factor base, collect relations with the
Macaulay (XL closure) PDP solver on the frozen workload's ordinary query stream until the
achievable rank, solve the relation matrix mod r, descend each workload target and check
[log Q]G = Q.  Each cell is a fully specified candidate, so it gets an AGENTS.md `IC1` ID
over its manifest (candidates/<id>.json).  Workloads fix the curve, query stream, targets
and rerandomization streams, so the factor base is the declared variable of a suite.

Costs are the opcount counters of every exclusive phase, priced in the frozen calibration
(calibration.json, unit `rps`).  Counters and priced totals are exact for a given source
state; wall time is recorded alongside and is not compared.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import multiprocessing
import os
import platform
import random
import resource
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
PDP = HERE.parent / "pdp-degree-heuristics"
ROOT = HERE.parents[1]
sys.path.insert(0, str(PDP))
sys.path.insert(0, str(HERE))

import kernel  # noqa: E402
import macaulay  # noqa: E402
import opcount  # noqa: E402
from calibrate import weights_for  # noqa: E402
from factor_base import FactorBase  # noqa: E402
from profile import pdp_config  # noqa: E402
from toycurve import ToyCurve, canonical, sha256_hex  # noqa: E402

PHASES = ("setup", "isogeny", "factor_base", "precompute", "queries", "pdp", "relation_check",
          "matrix_build", "relation_la", "target_descent", "recovery_check")
SOURCES = [
    PDP / "pdpkernel.c", PDP / "kernel.py", PDP / "opcount.py", PDP / "toycurve.py", PDP / "factor_base.py",
    PDP / "descent.py", PDP / "macaulay.py", PDP / "relations.py", PDP / "monitor.py", PDP / "profile.py",
    HERE.parent / "pdp-scaling" / "sumpoly.py", HERE.parent / "pdp-scaling" / "gf2n.py", HERE / "bench.py",
]
CALIBRATION = HERE / "calibration.json"
HISTORY = HERE / "history.csv"
RECEIPTS = HERE / "results" / "receipts.jsonl"

LIMITS = {"d_max": 10, "max_cols": 40_000, "max_rows": 200_000}


def cells(n, m, l, families, workload_seeds, targets=3, max_attempts=200_000, mode="mxl"):
    return [{"n": n, "m": m, "l": l, "family": f, "seed": 1, "mode": mode, "workload_seed": w,
             "targets": targets, "max_attempts": max_attempts}
            for w in workload_seeds for f in families]


SUITES = {
    # small enough for a pull-request check on four cores
    "ci": cells(13, 3, 3, ["prefix", "geomtrace", "random"], [1, 2, 3])
    + cells(19, 2, 5, ["prefix", "geomtrace", "random"], [1]),
    "full": cells(13, 3, 3, ["prefix", "geomtrace", "random"], [1, 2, 3])
    + cells(19, 2, 5, ["prefix", "geometric", "geomtrace", "geomtraceu", "random", "kertrace"], [1, 2, 3])
    + cells(19, 2, 6, ["prefix", "geometric", "geomtrace", "geomtraceu", "random"], [1, 2, 3])
    + cells(23, 2, 6, ["prefix", "geomtrace", "random"], [1], max_attempts=800_000),
}

CSV_FIELDS = [
    "bench_cell", "candidate_id", "workload_id", "run_id", "suite", "curve_id", "n", "m", "l", "family", "mode",
    "status", "verified", "targets", "targets_verified", "fb_points", "geometric_points", "effective_columns",
    "achievable_rank", "final_rank", "ordinary_queries", "pdp_verified", "pdp_proved_unsat", "pdp_budget",
    "pdp_lift_rejected", "verified_relations", "novel_rows", "descent_attempts",
    *[f"ops_{p}" for p in PHASES], "total_operations", "amortized_ops_per_target", "ops_per_novel_row",
    "rho_operations", "rho_floor_operations", "ratio_to_rho", "ratio_to_floor", "S_rps", "S_ec_add",
    *[f"count_{c}" for c in opcount.CLASSES], "wall_ns", "priced_over_wall", "peak_rss_bytes", "calibration_id",
    "implementation_sha256", "git_commit", "recorded_at", "host",
]
DETERMINISTIC = [f for f in CSV_FIELDS if f.startswith(("ops_", "count_")) or f in (
    "status", "verified", "targets_verified", "fb_points", "effective_columns", "achievable_rank", "final_rank",
    "ordinary_queries", "pdp_verified", "pdp_proved_unsat", "pdp_budget", "pdp_lift_rejected",
    "verified_relations", "novel_rows", "descent_attempts", "total_operations", "rho_operations")]


# ------------------------------------------------------------------ identities
def source_digests() -> dict[str, str]:
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES}


def implementation_sha256() -> str:
    return sha256_hex({"sources": source_digests(), "kernel_cflags": kernel.CFLAGS})


def cell_label(c: dict) -> str:
    return f"n{c['n']}m{c['m']}l{c['l']}-{c['family']}-s{c['seed']}-{c['mode']}-w{c['workload_seed']}"


def workload(curve: ToyCurve, seed: int, count: int) -> tuple[str, dict]:
    rng = random.Random(f"icbench-targets|{curve.curve_id}|{seed}")
    targets = []
    for _ in range(count):
        s, Q = curve.random_subgroup_point(rng)
        targets.append([s, Q[0], Q[1]])
    r = curve.r
    record = {
        "schema": "ic-bench-workload/1",
        "curve_id": curve.curve_id,
        "subgroup_order": str(r),
        "prng": "CPython random.Random seeded with the string (version-2 seeding)",
        "query_law": "R = [k]G with k uniform on [1, r-1], drawn in order from query_stream",
        "query_stream": f"icbench-queries|{curve.curve_id}|{seed}",
        "target_law": "Q = [s]G with s uniform on [1, r-1]",
        "targets": targets,
        "target_count": count,
        "rerandomization_law": "Q_i + [a]G with a uniform on [1, r-1], drawn from rerandomization_stream + '|i'",
        "rerandomization_stream": f"icbench-descent|{curve.curve_id}|{seed}",
        "cache_state": "cold",
        "rho_reference": {"group_operations": round(math.sqrt(math.pi * r / 2)),
                          "rule": "expected parallel rho without equivalence classes, sqrt(pi r / 2)"},
        "rho_floor": {"group_operations": round(math.sqrt(math.pi * r / (4 * curve.n))),
                      "rule": "rho on classes {+-tau^j P}, sqrt(pi r / (4 n))"},
        "seed": seed,
    }
    return sha256_hex(record)[:12], record


def endomorphism_record(curve: ToyCurve) -> dict:
    mu = 1 if curve.a2 == 1 else -1
    t, q = curve.trace, 2**curve.n
    if t % 2 == 0:
        raise ValueError("supersingular trace: the ordinary endomorphism record does not apply")
    f2, rem = divmod(4 * q - t * t, 7)
    f_pi = math.isqrt(f2)
    assert rem == 0 and f_pi * f_pi == f2, "4q - t^2 is not 7 f^2"
    return {
        "ordinary": True,
        "cm_discriminant": mu * mu - 8,
        "endomorphism_order_conductor": 1,
        "conductor_status": "proved",
        "proof": "tau(x, y) = (x^2, y^2) is an F_2-rational endomorphism with tau^2 - mu tau + 2 = 0; "
        "Z[tau] has discriminant mu^2 - 8 = -7, a fundamental discriminant, so Z[tau] is the maximal "
        "order of Q(sqrt(-7)), and End(E/F_2^n) is an order of that field containing it",
        "frobenius_order_conductor": f_pi,
        "frobenius_order_rule": "Z[pi], pi = tau^n, has discriminant t^2 - 4q = -7 f^2",
        "volcano_levels": {"odd_ell": "L0 (surface) for every odd prime ell: v_ell(1) = 0",
                           "ell_2": "not_applicable: degree 2 is the characteristic"},
    }


def candidate_manifest(curve: ToyCurve, fb: FactorBase, cell: dict) -> tuple[str, dict]:
    m = cell["m"]
    pdp = pdp_config(m, macaulay.Limits(**LIMITS))
    pdp.update({
        "stage_code": f"PDP{m}xl",
        "modes": [cell["mode"]],
        "completion_test": "refutation (1 in the row space) needs no oracle; for S >= 1 solutions the scan "
        "stops when the standard monomials number S, with S and the solutions read off an exhaustive "
        "enumeration (Moebius transform) that is charged to the phase it serves",
        "summation_polynomials": "curve-independent symbolic S_k from pdp-scaling/sumpoly.py, loaded once per "
        "process before the run (not charged)",
    })
    record = {
        "schema": "ic-candidate/1",
        "field": curve.field_record(),
        "curve": {**curve.curve_record(), "curve_id": curve.curve_id},
        "isogeny": "none",
        "endomorphism": endomorphism_record(curve),
        "factor_base": fb.record(),
        "point_decomposition": pdp,
        "relation_collection": {
            "stage_code": "RCsample",
            "query_law": "the workload's ordinary subgroup points R = [k]G, one PDP attempt each",
            "rows": "every verified decomposition (proper or improper, every sign choice) of R, as a row over "
            "the folded columns with right-hand side k",
            "verification": "relations.classify_solution: lift each abscissa and check the signed point sum is R",
            "dependencies": "rows reduced into an incremental echelon form mod r; only rank-increasing rows kept",
            "stop": "rank reaches the achievable rank (m = 2: rank of the two-point relations of every subgroup "
            "target, computed in precompute) or the effective column count (m >= 3)",
        },
        "relation_linear_algebra": {
            "stage_code": "LAgauss",
            "modulus": "r",
            "columns": f"factor_base.effective_columns ({fb.record()['quotient_rule']} orbits of pi_r(P))",
            "solver": "incremental dense Gaussian elimination mod r (monitor.RankTracker), back substitution "
            "with free columns set to 0",
            "rank_criterion": "achievable rank",
            "block_parameters": "none",
            "preconditioner": "none",
        },
        "target_descent": {
            "stage_code": "TDpdp",
            "policy": "Q + [a]G with a from the workload's rerandomization stream, decomposed by the same PDP "
            "solver until a verified relation appears; log Q = sum c_j log_j - a mod r",
            "recursive_solvers": "none",
            "success": "[log Q]G = Q",
        },
        "implementation": {
            "sources_sha256": source_digests(),
            "kernel_cflags": kernel.CFLAGS,
            "entry_point": "experiments/ic-bench/bench.py -> monitor.collect(args, workload, meter)",
        },
    }
    digest = sha256_hex(record)
    cid = (f"IC1N{curve.n}C{curve.tag}fb{fb.usable_points}PDP{m}xlRCsampleLAgaussTDpdpISO0h{digest[:12]}")
    return cid, record


def resource_envelope(cell: dict) -> tuple[str, dict]:
    env = {"max_query_attempts": cell["max_attempts"], "max_descent_attempts_per_target": cell["max_attempts"],
           "processes_per_run": 1, "process": "fresh spawned interpreter per run, kernel prebuilt"}
    return "ENV1h" + sha256_hex(env)[:12], env


# ------------------------------------------------------------------ one run
def _warm_process():
    import descent

    kernel.lib()
    for m in (2, 3):
        descent.summation_polynomial(m + 1)


def run_cell(cell: dict, calibration: dict) -> dict:
    """Run one cell in this (fresh) process and return its receipt."""
    import monitor

    t_all = time.perf_counter_ns()
    curve = ToyCurve(cell["n"])
    wid, wrec = workload(curve, cell["workload_seed"], cell["targets"])
    fb = FactorBase(curve, cell["family"], cell["l"], cell["seed"])
    cid, manifest = candidate_manifest(curve, fb, cell)
    eid, env = resource_envelope(cell)
    weights = weights_for(calibration, cell["n"])
    args = SimpleNamespace(n=cell["n"], m=cell["m"], l=cell["l"], family=cell["family"], seed=cell["seed"],
                           mode=cell["mode"], abort_degree=0, max_attempts=cell["max_attempts"],
                           workload_seed=cell["workload_seed"], descent_targets=cell["targets"],
                           report_every=0, out="", trace="", **LIMITS)
    meter = opcount.Meter()
    t_run = time.perf_counter_ns()
    res = monitor.collect(args, workload=wrec, meter=meter)
    wall = time.perf_counter_ns() - t_run
    with meter.phase("isogeny"):
        pass
    priced = meter.priced(weights)
    phase_ops = {p: priced.get(p, 0) for p in PHASES}
    phase_wall = {p: meter.wall_ns.get(p, 0) for p in PHASES}
    counters = {p: dict(meter.ops.get(p, {})) for p in PHASES}
    mon = res["monitor"]
    st = mon["status"]
    descents = res["descents"]
    verified = bool(descents) and all(d["verified"] and d["matches_workload"] for d in descents)
    if not res["collection_complete"]:
        status = "insufficient_relations"
    elif not all(d["recovered"] for d in descents):
        status = "budget"
    elif not verified:
        status = "error"
    else:
        status = "complete"
    total = sum(phase_ops.values()) if status == "complete" else None
    r = curve.r
    rho = wrec["rho_reference"]["group_operations"] * weights["ec_add"]
    floor = wrec["rho_floor"]["group_operations"] * weights["ec_add"]
    per_target = [sum(k * weights[c] for c, k in d["ops"].items()) for d in descents]
    priced_charged = sum(phase_ops.values())
    run = cell.get("run", 1)
    run_id = f"{cid}W{wid}R{run}"
    solved = st.get("verified_decomposition", 0)
    receipt = {
        "schema_version": 1,
        "kind": "full_dlp",
        "status": status,
        "candidate_id": cid,
        "proposal_id": None,
        "run_id": run_id,
        "workload_id": wid,
        "pair_block_id": f"W{wid}",
        "source_curve_ref": curve.curve_id,
        "profile_id": cell_label(cell),
        "isogeny_route_ref": "none",
        "bench_cell": cell_label(cell),
        "suite": cell.get("suite"),
        "cell": {k: cell[k] for k in ("n", "m", "l", "family", "seed", "mode", "workload_seed", "targets")},
        "subgroup_order": str(r),
        "counts": {
            "ordinary_queries": mon["attempts"],
            "solved_queries": solved,
            "verified_decompositions": solved,
            "verified_relations": mon["relations"],
            "novel_rows": mon["novel_rows"],
            "effective_columns": res["effective_columns"],
            "final_rank": res["final_rank"],
            "pdp_attempts": mon["attempts"],
            "pdp_verified": solved,
            "pdp_proved_unsat": st.get("proved_unsat", 0),
            "pdp_timeout": 0,
            "pdp_budget": st.get("budget", 0),
            "pdp_error": 0,
            "pdp_lift_rejected": st.get("lift_rejected", 0),
            "targets": len(descents),
            "targets_verified": sum(1 for d in descents if d["verified"] and d["matches_workload"]),
            "descent_attempts": sum(d["attempts"] for d in descents),
        },
        "phase_operations": phase_ops,
        "phase_wall_ns": phase_wall,
        "phase_counters": counters,
        "instrument": {"wall_ns": meter.wall_ns.get("instrument", 0), "counters": dict(meter.ops.get("instrument", {})),
                       "note": "diagnostics (structure, exact yield, predictions) and S = 0 enumerations; not charged"},
        "total_operations": total,
        "operation_unit": calibration["unit"],
        "rho_operations": rho,
        "rho_floor_operations": floor,
        "ratio_to_rho": total / rho if total is not None else None,
        "ratio_to_floor": total / floor if total is not None else None,
        "S_rps": total / math.sqrt(r) if total is not None else None,
        "S_ec_add": total / (weights["ec_add"] * math.sqrt(r)) if total is not None else None,
        "warm": {"k": len(descents), "per_target_operations": per_target,
                 "shared_operations": priced_charged - sum(per_target),
                 "amortized_operations_per_target": total / len(descents) if total is not None and descents else None,
                 "shared": "every phase except target descent (factor base, collection, relation LA, log checks)"},
        "verified_scalar": status == "complete",
        "scalar_certificate_ref": f"{run_id}#descents" if status == "complete" else None,
        "descents": [{k: d[k] for k in ("attempts", "recovered", "verified", "matches_workload", "scalar")}
                     for d in descents],
        "stage": {
            "fb_points": fb.usable_points,
            "geometric_points": fb.geometric_points,
            "nominal_dimension": cell["l"],
            "effective_columns": res["effective_columns"],
            "achievable_rank": res["achievable_rank"],
            "factor_base_sha256": fb.digest,
            "factor_base_logs_verified": res["factor_base_logs_verified"],
            "yield_per_query": mon["yield_per_attempt"],
            "yield_wilson95": mon["yield_wilson95"],
            "exact_p_decomposable": (res["exact_yield"] or {}).get("p_decomposable"),
            "novel_rows_per_query": mon["novel_rows"] / mon["attempts"] if mon["attempts"] else None,
            "pdp_mac_ops_per_query": mon["ops_per_attempt_mean"],
            "operations_per_novel_row": (phase_ops["queries"] + phase_ops["pdp"] + phase_ops["relation_check"]
                                         + phase_ops["matrix_build"]) / mon["novel_rows"] if mon["novel_rows"] else None,
            "priced_over_wall": priced_charged / 1000 / sum(phase_wall.values()) if sum(phase_wall.values()) else None,
        },
        "wall_ns": time.perf_counter_ns() - t_all,
        "run_wall_ns": wall,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "provenance": {
            "workload_fixture_sha256": sha256_hex(wrec),
            "source_sha256": implementation_sha256(),
            "host_id": platform.node(),
            "resource_envelope_id": eid,
            "calibration_id": calibration["calibration_id"],
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "resource_envelope": env,
    }
    return {"receipt": receipt, "manifest": (cid, manifest), "workload": (wid, wrec)}


def _worker(args):
    return run_cell(*args)


# ------------------------------------------------------------------ outputs
def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def csv_row(rec: dict, commit: str, recorded_at: str) -> dict:
    c, cnt, st = rec["cell"], rec["counts"], rec["stage"]
    totals = {cls: 0 for cls in opcount.CLASSES}
    for p in rec["phase_counters"].values():
        for cls, k in p.items():
            totals[cls] += k
    row = {
        "bench_cell": rec["bench_cell"], "candidate_id": rec["candidate_id"], "workload_id": rec["workload_id"],
        "run_id": rec["run_id"], "suite": rec["suite"], "curve_id": rec["source_curve_ref"],
        "n": c["n"], "m": c["m"], "l": c["l"], "family": c["family"], "mode": c["mode"],
        "status": rec["status"], "verified": rec["verified_scalar"], "targets": cnt["targets"],
        "targets_verified": cnt["targets_verified"], "fb_points": st["fb_points"],
        "geometric_points": st["geometric_points"], "effective_columns": cnt["effective_columns"],
        "achievable_rank": st["achievable_rank"], "final_rank": cnt["final_rank"],
        "descent_attempts": cnt["descent_attempts"],
        **{k: cnt[k] for k in ("ordinary_queries", "pdp_verified", "pdp_proved_unsat", "pdp_budget",
                               "pdp_lift_rejected", "verified_relations", "novel_rows")},
        **{f"ops_{p}": rec["phase_operations"][p] for p in PHASES},
        "total_operations": rec["total_operations"],
        "amortized_ops_per_target": rec["warm"]["amortized_operations_per_target"],
        "ops_per_novel_row": st["operations_per_novel_row"],
        "rho_operations": rec["rho_operations"], "rho_floor_operations": rec["rho_floor_operations"],
        "ratio_to_rho": rec["ratio_to_rho"], "ratio_to_floor": rec["ratio_to_floor"],
        "S_rps": rec["S_rps"], "S_ec_add": rec["S_ec_add"],
        **{f"count_{cls}": totals[cls] for cls in opcount.CLASSES},
        "wall_ns": rec["wall_ns"], "priced_over_wall": st["priced_over_wall"],
        "peak_rss_bytes": rec["peak_rss_bytes"], "calibration_id": rec["provenance"]["calibration_id"],
        "implementation_sha256": rec["provenance"]["source_sha256"], "git_commit": commit,
        "recorded_at": recorded_at, "host": rec["provenance"]["host_id"],
    }
    for k, v in row.items():
        if isinstance(v, float):
            row[k] = f"{v:.6g}"
        elif v is None:
            row[k] = ""
    return row


def write_csv(path: Path, rows: list[dict], append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not (append and path.exists() and path.stat().st_size)
    with path.open("a" if append else "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def next_run_numbers(history: list[dict]) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for row in history:
        key = (row["candidate_id"], row["workload_id"])
        out[key] = max(out.get(key, 0), int(row["run_id"].rsplit("R", 1)[1]))
    return out


def write_manifest(directory: Path, ident: str, record: dict) -> None:
    path = directory / f"{ident}.json"
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    if path.exists():
        assert path.read_text() == text, f"{path} exists with different content"
        return
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def run_suite(suite: str, jobs: int, calibration: dict, history: list[dict]) -> list[dict]:
    todo = [dict(c, suite=suite) for c in SUITES[suite]]
    _warm_process()
    ctx = multiprocessing.get_context("spawn")
    results = []
    with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx, initializer=_warm_process,
                             max_tasks_per_child=1) as pool:
        futures = [(c, pool.submit(_worker, (c, calibration))) for c in todo]
        for c, fut in futures:
            out = fut.result()
            rec = out["receipt"]
            print(f"{rec['bench_cell']:34s} {rec['status']:22s} queries={rec['counts']['ordinary_queries']:6d} "
                  f"total={rec['total_operations']} wall={rec['wall_ns'] / 1e9:.1f}s", flush=True)
            results.append(out)
    # run numbers: one more than any recorded run of the same candidate on the same workload
    last = next_run_numbers(history)
    for out in results:
        rec = out["receipt"]
        key = (rec["candidate_id"], rec["workload_id"])
        last[key] = last.get(key, 0) + 1
        rec["run_id"] = f"{rec['candidate_id']}W{rec['workload_id']}R{last[key]}"
        if rec["scalar_certificate_ref"]:
            rec["scalar_certificate_ref"] = f"{rec['run_id']}#descents"
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a suite; write <suite>.csv, <suite>.jsonl and manifests to --out-dir")
    r.add_argument("--suite", default="ci", choices=sorted(SUITES))
    r.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    r.add_argument("--out-dir", default=str(HERE / "out"))
    r.add_argument("--record", action="store_true",
                   help="append to history.csv and results/receipts.jsonl, write manifests under candidates/ and "
                   "workloads/, and replace baseline/<suite>.csv and .jsonl")
    sub.add_parser("list", help="list the cells of every suite")
    args = ap.parse_args()
    if args.cmd == "list":
        for name, cs in SUITES.items():
            print(f"{name}: {len(cs)} cells")
            for c in cs:
                print("  " + cell_label(c))
        return
    calibration = json.loads(CALIBRATION.read_text())
    history = read_csv(HISTORY)
    t0 = time.time()
    results = run_suite(args.suite, args.jobs, calibration, history)
    commit, stamp = git_commit(), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    receipts = [o["receipt"] for o in results]
    rows = [csv_row(rec, commit, stamp) for rec in receipts]
    out = Path(args.out_dir)
    write_csv(out / f"{args.suite}.csv", rows)
    (out / f"{args.suite}.jsonl").write_text("".join(canonical(rec) + "\n" for rec in receipts))
    for o in results:
        write_manifest(out / "candidates", *o["manifest"])
        write_manifest(out / "workloads", *o["workload"])
    if args.record:
        write_csv(HISTORY, rows, append=True)
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a") as fh:
            fh.writelines(canonical(rec) + "\n" for rec in receipts)
        for o in results:
            write_manifest(HERE / "candidates", *o["manifest"])
            write_manifest(HERE / "workloads", *o["workload"])
        write_csv(HERE / "baseline" / f"{args.suite}.csv", rows)
        (HERE / "baseline" / f"{args.suite}.jsonl").write_text("".join(canonical(rec) + "\n" for rec in receipts))
    bad = [rec["bench_cell"] for rec in receipts if rec["status"] != "complete"]
    print(f"{len(receipts)} runs in {time.time() - t0:.0f}s; {len(receipts) - len(bad)} complete verified DLPs"
          + (f"; not complete: {', '.join(bad)}" if bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
