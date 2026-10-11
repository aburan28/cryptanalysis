#!/usr/bin/env python3
"""One-target IC-versus-rho benchmark executable for scripts/isolated_bench.py.

One process solves one frozen public target and prints, as its last line, the runner's fields:

    online_ms=<float> verified=<0|1> curve_id=... target_x=... target_y=... fixture_scalar=... ...

--variant ic   runs the ic-bench m = 2 pipeline (monitor.collect).  Target-independent setup (factor
               base, relation collection to the achievable rank with the frozen query stream, relation
               linear algebra, factor-base log checks) runs first and is NOT timed.  online_ms is the
               target's online interval measured inside monitor.collect: from the first target-
               dependent rerandomization to the independent scalar replay [log Q] G == Q, so every
               failed attempt is inside it (AGENTS.md T_online,1).
--variant rho  runs ic-bench's one-target Pollard rho (bench.rho_one_target: three-set r-adding walk,
               Floyd cycle detection, restarts on a degenerate collision) on the same point.  online_ms
               is from the first walk computation to the scalar replay [s] G == Q.

The target comes from a frozen scalar law, s = 1 + SHA-256("<panel_key>:<curve_id>:<index>") mod (r-1),
Q = [s]G; building it is fixture construction and stays outside both timers.  verified=1 needs the
recovered scalar to pass scalar replay and to equal s.  Both variants use the same Python field and
curve arithmetic (pdpkernel.c through ctypes); per-call overhead weighs more on rho's single walk than
on IC's batched attempts, which the manifest records.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(ROOT / "experiments" / "pdp-degree-heuristics"))
sys.path.insert(0, str(ROOT / "experiments" / "ic-bench"))

import bench  # noqa: E402
import monitor  # noqa: E402
import opcount  # noqa: E402
from factor_base import FactorBase  # noqa: E402
from toycurve import ToyCurve, sha256_hex  # noqa: E402


def fixture_scalar(panel_key: str, curve: ToyCurve, index: int) -> int:
    digest = hashlib.sha256(f"{panel_key}:{curve.curve_id}:{index}".encode()).digest()
    return 1 + int.from_bytes(digest, "big") % (curve.r - 1)


def one_target_workload(curve: ToyCurve, query_seed: int, panel_key: str, index: int, s: int,
                        Q: tuple[int, int]) -> tuple[str, dict]:
    """The bench workload law with an explicit frozen target.  The query stream depends only on the
    curve and query_seed, so the setup is the same for every target of a panel."""
    r = curve.r
    record = {
        "schema": "ic-bench-workload/1",
        "curve_id": curve.curve_id,
        "subgroup_order": str(r),
        "prng": "CPython random.Random seeded with the string (version-2 seeding)",
        "query_law": "R = [k]G with k uniform on [1, r-1], drawn in order from query_stream",
        "query_stream": f"icbench-queries|{curve.curve_id}|{query_seed}",
        "target_law": "s = 1 + SHA-256('<panel_key>:<curve_id>:<index>') mod (r-1), Q = [s]G",
        "targets": [[s, Q[0], Q[1]]],
        "target_count": 1,
        "rerandomization_law": "the rerandomization law of the candidate's TDpdp manifest",
        "rerandomization_stream": f"isolated-panel-descent|{curve.curve_id}|{panel_key}|{index}",
        "cache_state": "prepared",
        "panel_key": panel_key,
        "panel_index": index,
        "seed": query_seed,
    }
    return sha256_hex(record)[:12], record


def run_ic(args, curve: ToyCurve, s: int, Q: tuple[int, int]) -> dict:
    bench._warm_process()
    wid, wrec = one_target_workload(curve, args.query_seed, args.panel_key, args.index, s, Q)
    fb = FactorBase(curve, args.family, args.l, args.seed)
    cell = {"m": 2, "mode": args.mode}
    if args.rerandomize != "uniform":
        cell["rerandomize"] = args.rerandomize
    cid, _ = bench.candidate_manifest(curve, fb, cell)
    margs = SimpleNamespace(n=args.n, m=2, l=args.l, family=args.family, seed=args.seed, mode=args.mode,
                            rerandomize=args.rerandomize, abort_degree=0, max_attempts=args.max_attempts,
                            workload_seed=args.query_seed, descent_targets=1, report_every=0, out="",
                            trace="", **bench.LIMITS)
    res = monitor.collect(margs, workload=wrec, meter=opcount.Meter())
    if not res["collection_complete"] or not res["descents"]:
        return {"online_ms": None, "verified": 0, "status": "insufficient_relations", "candidate_id": cid,
                "workload_id": wid}
    d = res["descents"][0]
    ok = bool(d["verified"]) and d["scalar"] == s
    return {"online_ms": d["online_wall_ns"] / 1e6 if d["recovered"] else None, "verified": int(ok),
            "status": "complete" if ok else ("budget" if not d["recovered"] else "error"),
            "attempts": d["attempts"], "candidate_id": cid, "workload_id": wid,
            "setup_queries": res["monitor"]["attempts"], "final_rank": res["final_rank"]}


def run_rho(args, curve: ToyCurve, s: int, Q: tuple[int, int]) -> dict:
    out = bench.rho_one_target(curve, Q, f"isolated-panel|{curve.curve_id}|{args.panel_key}|{args.index}")
    ok = bool(out["verified"]) and out["scalar"] == s
    return {"online_ms": out["online_wall_ns"] / 1e6, "verified": int(ok), "status": out["status"],
            "steps": out["steps"], "restarts": out["restarts"]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", choices=("ic", "rho"), required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--family", required=True)
    ap.add_argument("--l", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--mode", default="ht")
    ap.add_argument("--rerandomize", default="walk", choices=("uniform", "walk"))
    ap.add_argument("--query-seed", type=int, default=1)
    ap.add_argument("--panel-key", required=True)
    ap.add_argument("--index", type=int, required=True)
    ap.add_argument("--max-attempts", type=int, default=800_000)
    args = ap.parse_args()
    t0 = time.perf_counter_ns()
    curve = ToyCurve(args.n)
    s = fixture_scalar(args.panel_key, curve, args.index)
    Q = curve.K.smul(curve.G, s)
    out = run_ic(args, curve, s, Q) if args.variant == "ic" else run_rho(args, curve, s, Q)
    fields = {
        "online_ms": "nan" if out["online_ms"] is None else f"{out['online_ms']:.6f}",
        "verified": out["verified"], "status": out["status"], "variant": args.variant,
        "curve_id": curve.curve_id, "subgroup_order": curve.r, "target_x": Q[0], "target_y": Q[1],
        "fixture_scalar": s, "panel_key": args.panel_key, "panel_index": args.index,
        **{k: v for k, v in out.items() if k not in ("online_ms", "verified", "status")},
        "process_ms": f"{(time.perf_counter_ns() - t0) / 1e6:.3f}",
    }
    print(" ".join(f"{k}={v}" for k, v in fields.items()), flush=True)
    sys.exit(0 if out["verified"] else 1)


if __name__ == "__main__":
    main()
