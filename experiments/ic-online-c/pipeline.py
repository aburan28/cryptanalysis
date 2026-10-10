#!/usr/bin/env python3
"""Complete m = 2 index calculus on the toy Koblitz curves with the batched C half-trace oracle, and
a paired one-target comparison against parallel-collision rho in the same C arithmetic.

    python3 pipeline.py prepare --n 41 --family geomtraceu --l 15 --seed 1
    python3 pipeline.py panel --n 41 --family geomtraceu --l 15 --seed 1 --targets 32 --variants v1 v0 rho

Stages (AGENTS.md names):

- factor base: ../pdp-degree-heuristics FactorBase (folded +-pi_r columns).
- relation collection, RCwalk: W = 256 walks R_i = [k0]G + i [a]G, every PDP2ht decomposition of
  every walk point kept as a two-term row with right-hand side k0 + i a mod r, until the rows reach
  `--relations` times the column count.
- relation linear algebra, LAgraph: the rows are the edges of a gain graph over the columns. One
  breadth-first pass writes each column as alpha t + beta in its component's root t. Any row
  whose t coefficient is nonzero fixes t, and every row is checked. Each fixed log is verified as
  [x]G = rep.
- target descent, TDpdp: Q + i [a0]G, decomposed by the online PDP oracle until a row evaluates on
  the solved logs; log Q = value - i a0, verified as [log Q]G = Q inside the online interval.

Online PDP oracles for the paired comparison (same logs, same target, same rerandomization):
v1 = htfast.c htf_run (batched), v0 = htfast.c htf_run_v0 (the previous C oracle), py = the Python
HalfTraceSolver that the ic-bench IC1 runs use.  rho = htfast.c htf_rho.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import platform
import random
import statistics
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "experiments" / "ic-bench"))

import htfast  # noqa: E402
from htfast import DP_DTYPE, FactorBase, Kernel, Walk, WalkV0, curve, rho_call  # noqa: E402
from toycurve import canonical, sha256_hex  # noqa: E402

RESULTS = HERE / "results"
CACHE = HERE / "cache"
PANEL_KEY = "ic-online-c-v1"
SOURCES = [HERE / "htfast.c", HERE / "htfast.py", HERE / "pipeline.py"] + [
    ROOT / "experiments" / "pdp-degree-heuristics" / f for f in
    ("factor_base.py", "htsolver.py", "toycurve.py", "kernel.py", "pdpkernel.c", "gf2n.py")]
VARIANTS = ("v1", "v0", "py")
COLLECTION_LAW = "ic-online-c RCwalk/1: W = 256 walks, every verified decomposition kept, first ratio x columns rows"
WALK_ONLINE = 32
WALK_COLLECT = 256


def ns() -> int:
    return time.perf_counter_ns()


def source_digests() -> dict[str, str]:
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES if p.exists()}


def host() -> dict:
    model = ""
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                model = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return {"cpu_model": model, "logical_cpus": os.cpu_count(), "platform": platform.platform(),
            "python": platform.python_version(), "controlled": False,
            "note": "unisolated cloud VM; exploratory wall times (AGENTS.md isolation gate not met)"}


# ------------------------------------------------------------------ setup

class Setup:
    def __init__(self, n: int, family: str, l: int, seed: int):
        t0 = ns()
        self.C = curve(n)
        t1 = ns()
        self.fb = FactorBase(self.C, family, l, seed)
        t2 = ns()
        self.k = Kernel(self.fb)
        t3 = ns()
        fb = self.fb
        self.point = {}
        for x, y, col, coeff in zip(fb.xs.tolist(), fb.ys.tolist(), fb.col_of.tolist(), fb.col_coeff.tolist()):
            self.point[(x, y)] = (col, int(coeff) % self.C.r if col >= 0 else 0)
        t4 = ns()
        self.walls = {"setup": t1 - t0, "factor_base": t2 - t1, "precompute_tables": t3 - t2 + t4 - t3}
        self.family, self.l, self.seed = family, l, seed

    def terms(self, x1, y1, x2, y2) -> list[tuple[int, int]]:
        acc: dict[int, int] = {}
        r = self.C.r
        for P in ((x1, y1), (x2, y2)):
            col, c = self.point[P]
            if col >= 0:
                acc[col] = (acc.get(col, 0) + c) % r
        return [(j, c) for j, c in acc.items() if c]


# ------------------------------------------------------------------ LAgraph

class GainGraph:
    """Rows sum c_j x_j = k (one or two columns) over Z/r; each column x = alpha t_comp + beta."""

    def __init__(self, columns: int, r: int, rows: list[tuple[list[tuple[int, int]], int]]):
        self.r = r
        adj: list[list[int]] = [[] for _ in range(columns)]
        for e, (terms, _) in enumerate(rows):
            if len(terms) == 2:
                adj[terms[0][0]].append(e)
                adj[terms[1][0]].append(e)
        comp = [-1] * columns
        alpha = [0] * columns
        beta = [0] * columns
        ncomp = 0
        for s in range(columns):
            if comp[s] >= 0 or not adj[s]:
                continue
            comp[s], alpha[s], beta[s] = ncomp, 1, 0
            dq = deque([s])
            while dq:
                a = dq.popleft()
                for e in adj[a]:
                    (j1, c1), (j2, c2) = rows[e][0]
                    k = rows[e][1]
                    if j1 == a:
                        b, ca, cb = j2, c1, c2
                    else:
                        b, ca, cb = j1, c2, c1
                    if comp[b] >= 0:
                        continue
                    inv = pow(cb, -1, r)
                    comp[b] = ncomp
                    alpha[b] = (-ca * alpha[a] * inv) % r
                    beta[b] = ((k - ca * beta[a]) * inv) % r
                    dq.append(b)
            ncomp += 1
        for j in range(columns):
            if comp[j] < 0:
                comp[j], alpha[j], beta[j] = ncomp, 1, 0
                ncomp += 1
        t: list[int | None] = [None] * ncomp
        inconsistent = fixing = 0
        for terms, k in rows:
            cid = comp[terms[0][0]]
            if any(comp[j] != cid for j, _ in terms):
                raise AssertionError("a row spans two components")
            a = sum(c * alpha[j] for j, c in terms) % r
            b = (k - sum(c * beta[j] for j, c in terms)) % r
            if a:
                v = b * pow(a, -1, r) % r
                fixing += 1
                if t[cid] is None:
                    t[cid] = v
                elif t[cid] != v:
                    inconsistent += 1
            elif b:
                inconsistent += 1
        self.comp, self.alpha, self.beta, self.t = comp, alpha, beta, t
        self.ncomp, self.inconsistent, self.fixing_rows = ncomp, inconsistent, fixing
        self.log = [None if t[comp[j]] is None else (alpha[j] * t[comp[j]] + beta[j]) % r for j in range(columns)]

    def evaluate(self, terms: list[tuple[int, int]]) -> int | None:
        r, val = self.r, 0
        free: dict[int, int] = {}
        for j, c in terms:
            lj = self.log[j]
            if lj is not None:
                val += c * lj
            else:
                cid = self.comp[j]
                free[cid] = (free.get(cid, 0) + c * self.alpha[j]) % r
                val += c * self.beta[j]
        if any(free.values()):
            return None
        return val % r

    def summary(self) -> dict:
        solved = sum(1 for v in self.log if v is not None)
        sizes: dict[int, int] = {}
        for c in self.comp:
            sizes[c] = sizes.get(c, 0) + 1
        return {"columns": len(self.log), "solved_columns": solved, "components": self.ncomp,
                "largest_component": max(sizes.values()) if sizes else 0, "fixing_rows": self.fixing_rows,
                "inconsistent_rows": self.inconsistent}


# ------------------------------------------------------------------ precompute

def collection_stream(C, query_seed: int) -> tuple[int, int]:
    rng = random.Random(f"ic-online-c-collect|{C.curve_id}|{query_seed}")
    return rng.randrange(1, C.r), rng.randrange(1, C.r)


def collect(st: Setup, query_seed: int, ratio: float, W: int = WALK_COLLECT) -> dict:
    C, k = st.C, st.k
    k0, a = collection_stream(C, query_seed)
    columns = st.fb.effective_columns
    want = math.ceil(ratio * columns)
    t0 = ns()
    P0 = k.smul(C.G, k0)
    step = k.smul(C.G, a)
    walk = Walk(k, P0, step, W)
    rows: list[tuple[list[tuple[int, int]], int]] = []
    while len(rows) < want:
        hits = walk.run(64, False, max_hits=1 << 16)
        for h in hits.tolist():
            i = int(h[0])
            terms = st.terms(h[3], h[4], h[5], h[6])
            if terms:
                rows.append((terms, (k0 + i * a) % C.r))
    wall = ns() - t0
    s = walk.stats
    return {"rows": rows[:want], "wall_ns": wall, "attempts": int(s[4]), "candidates": int(s[5]),
            "consistent_systems": int(s[6]), "candidate_hits": int(s[7]), "relations": len(rows),
            "c_walk_ns": int(s[0]), "c_pdp_ns": int(s[1]), "c_check_ns": int(s[2]), "k0": k0, "a": a}


def cache_path(st: Setup, query_seed: int, ratio: float) -> Path:
    key = sha256_hex({"fb": st.fb.digest, "curve": st.C.curve_id, "query_seed": query_seed, "ratio": str(ratio),
                      "collection_law": COLLECTION_LAW})[:16]
    return CACHE / f"n{st.C.n}-{st.family}-l{st.l}-s{st.seed}-q{query_seed}-{key}.json.gz"


def prepare(st: Setup, query_seed: int, ratio: float, verbose: bool = True) -> tuple[GainGraph, dict]:
    path = cache_path(st, query_seed, ratio)
    if path.exists():
        rec = json.loads(gzip.open(path, "rt").read())
        rows = [([tuple(t) for t in terms], k) for terms, k in rec.pop("rows")]
        t0 = ns()
        g = GainGraph(st.fb.effective_columns, st.C.r, rows)
        rec["relation_la_ns_reload"] = ns() - t0
        rec["cache"] = str(path.relative_to(HERE))
        return g, rec
    col = collect(st, query_seed, ratio)
    if verbose:
        print(f"collect: {col['relations']} rows from {col['attempts']} attempts in {col['wall_ns'] / 1e9:.1f} s",
              file=sys.stderr, flush=True)
    t0 = ns()
    g = GainGraph(st.fb.effective_columns, st.C.r, col["rows"])
    t_la = ns() - t0
    t0 = ns()
    reps = st.fb.column_reps
    bad = sum(1 for j, v in enumerate(g.log) if v is not None and st.k.smul(st.C.G, v)[:2] != reps[j])
    t_rc = ns() - t0
    summ = g.summary()
    if bad or summ["inconsistent_rows"]:
        raise AssertionError(f"log verification failed: {bad} wrong logs, {summ['inconsistent_rows']} inconsistent rows")
    rec = {
        "schema": "ic-online-c-precompute/1",
        "curve_id": st.C.curve_id, "factor_base_sha256": st.fb.digest, "query_seed": query_seed,
        "relation_ratio": str(ratio), "collection_law": COLLECTION_LAW, "collection_kernel_sha256": htfast.source_sha256(),
        "walls_ns": {**st.walls, "relation_collection": col["wall_ns"],
                                                     "relation_la": t_la, "log_recovery_check": t_rc},
        "collection": {k: v for k, v in col.items() if k != "rows"},
        "graph": summ, "logs_verified": summ["solved_columns"],
        "rows": [[list(map(list, terms)), k] for terms, k in col["rows"]],
    }
    CACHE.mkdir(exist_ok=True)
    with gzip.open(path, "wt") as fh:
        fh.write(json.dumps(rec))
    rec.pop("rows")
    rec["cache"] = str(path.relative_to(HERE))
    return g, rec


# ------------------------------------------------------------------ targets, IDs

def fixture_scalar(C, index: int) -> int:
    digest = hashlib.sha256(f"{PANEL_KEY}:{C.curve_id}:{index}".encode()).digest()
    return 1 + int.from_bytes(digest, "big") % (C.r - 1)


def rerandomizer(C, index: int) -> int:
    return random.Random(f"ic-online-c-descent|{C.curve_id}|{PANEL_KEY}|{index}").randrange(1, C.r)


def workload_record(C, index: int, s: int, Q: tuple, query_seed: int, ratio: float) -> tuple[str, dict]:
    r = C.r
    rec = {
        "schema": "ic-online-c-workload/1", "curve_id": C.curve_id, "subgroup_order": str(r),
        "prng": "CPython random.Random seeded with the string (version-2 seeding)",
        "collection_law": "W = 256 walks R_i = [k0]G + i [a]G with (k0, a) drawn from collection_stream",
        "collection_stream": f"ic-online-c-collect|{C.curve_id}|{query_seed}",
        "collection_stop": f"rows >= {ratio} x effective columns",
        "target_law": f"s = 1 + SHA-256('{PANEL_KEY}:<curve_id>:<index>') mod (r - 1), Q = [s]G",
        "targets": [[s, Q[0], Q[1]]], "target_count": 1, "panel_index": index,
        "rerandomization_law": "a0 = first randrange(1, r) of rerandomization_stream; attempts Q + i [a0]G",
        "rerandomization_stream": f"ic-online-c-descent|{C.curve_id}|{PANEL_KEY}|{index}",
        "rho_stream": f"ic-online-c-rho|{C.curve_id}|{PANEL_KEY}|{index}",
        "rho_law": "32-entry r-adding walk T_j = [c_j]G + e_j Q (e_j in {0, 1}, 16 each), W starts [a_w]G + Q, "
                   "distinguished points (x >> 8) mod 2^dp_bits = 0; [c_j]G and [a_w]G are target-independent and "
                   "computed before the rho clock",
        "cache_state": "prepared: factor-base logs ready before the online clock",
        "rho_reference": {"group_operations": round(math.sqrt(math.pi * r / 2)),
                          "rule": "expected parallel rho without equivalence classes, sqrt(pi r / 2)"},
        "rho_floor": {"group_operations": round(math.sqrt(math.pi * r / (4 * C.n))),
                      "rule": "rho on classes {+-tau^j P}, sqrt(pi r / (4 n)); not implemented here"},
    }
    return sha256_hex(rec)[:12], rec


PDP_DESCRIPTIONS = {
    "v1": "htfast.c htf_run: W = 32 walks per round; one Montgomery inversion (four interleaved chains) for "
          "the walk denominators and one for every 1/S; columns pi(S HT(v_j^2)), pi(S) read from byte tables "
          "linear in S; one reduced-echelon elimination over l + 1 unknowns (eps included); the candidates of "
          "a round share one batched inversion of u^2; signed lifts checked in C",
    "v0": "htfast.c htf_run_v0: the fb-search/htenum.c ht_attempt_batch oracle on one point at a time after a "
          "single affine walk step (one inversion per step), l field multiplications and nchk * l parities per "
          "system, one elimination per eps, one batch inversion per eps branch; signed lifts checked in C",
    "py": "pdp-degree-heuristics/htsolver.py HalfTraceSolver.decompose after one Python-ctypes walk step, "
          "the oracle of the ic-bench online-ht IC1 runs",
}


def candidate_record(st: Setup, variant: str, query_seed: int, ratio: float) -> tuple[str, dict]:
    import bench

    C, fb = st.C, st.fb
    rec = {
        "schema": "ic-candidate/1",
        "field": C.field_record(),
        "curve": {**C.curve_record(), "curve_id": C.curve_id},
        "isogeny": "none",
        "endomorphism": bench.endomorphism_record(C),
        "factor_base": fb.record(),
        "point_decomposition": {
            "stage_code": "PDP2ht", "summand_count": 2,
            "summation_polynomial": "S_3 as the Artin-Schreier equation (p/S)^2 + p/S = (u + sqrt(b)/S)^2, "
                                    "u = X + Y, p = XY (Courtois, ePrint 2016/003)",
            "solver": "half-trace projection onto F / V^(2) plus the trace row, residual enumeration over the "
                      "solution space, X = u HT(p/u^2) kept if X in V and the signed lifts sum to R",
            "online_oracle": variant, "online_implementation": PDP_DESCRIPTIONS[variant],
            "collection_oracle": "v1", "monomial_order": "none", "limits": "none",
            "cache_policy": "V^(2) parity checks, HT, V-syndrome, pi and column byte tables per factor base",
        },
        "relation_collection": {
            "stage_code": "RCwalk", "query_law": "W = 256 walks R_i = [k0]G + i [a]G (workload collection stream)",
            "rows": "every verified decomposition of every walk point, a row over the folded columns with "
                    "right-hand side k0 + i a mod r",
            "verification": "C: signed lifts of X and Y sum to R exactly", "dependencies": "none removed",
            "stop": f"rows >= {ratio} x effective columns",
        },
        "relation_linear_algebra": {
            "stage_code": "LAgraph", "modulus": "r",
            "columns": f"factor_base.effective_columns ({fb.record()['quotient_rule']} orbits of pi_r(P))",
            "solver": "gain graph: BFS writes each column as alpha t + beta in its component root t; a row with "
                      "nonzero t coefficient fixes t; every row is checked; every fixed log is verified [x]G = rep",
            "rank_criterion": "none: unfixed components stay symbolic and a target row is used only if its t "
                              "coefficients cancel",
            "block_parameters": "none", "preconditioner": "none",
        },
        "target_descent": {
            "stage_code": "TDpdp",
            "policy": "Q + i [a0]G, i = 1, 2, ... (v1: 32 walks advancing by 32 [a0]G; v0, py: one walk), decomposed "
                      "by the online oracle until a row evaluates on the logs; log Q = value - i a0 mod r",
            "recursive_solvers": "none", "success": "[log Q]G = Q, inside the online interval",
        },
        "implementation": {"sources_sha256": source_digests(), "cflags": htfast.CFLAGS,
                           "entry_point": "experiments/ic-online-c/pipeline.py"},
    }
    digest = sha256_hex(rec)
    cid = f"IC1N{C.n}C{C.tag}fb{fb.usable_points}PDP2htRCwalkLAgraphTDpdpISO0h{digest[:12]}"
    return cid, rec


# ------------------------------------------------------------------ online

def _finish(st, g, Q, hits, a0) -> tuple[int | None, int | None]:
    r = st.C.r
    for h in sorted(hits.tolist(), key=lambda h: h[0]):
        val = g.evaluate(st.terms(h[3], h[4], h[5], h[6]))
        if val is not None:
            return (val - int(h[0]) * a0) % r, int(h[0])
    return None, None


def online_ic(st: Setup, g: GainGraph, Q: tuple, a0: int, variant: str, max_attempts: int) -> dict:
    C, k = st.C, st.k
    t0 = ns()
    step = k.smul(C.G, a0)
    if variant == "v1":
        walk = Walk(k, Q, step, WALK_ONLINE)
        rounds = max(1, max_attempts // WALK_ONLINE)
    elif variant == "v0":
        walk = WalkV0(k, (*Q, 0), step)
    t_setup = ns() - t0
    scalar = index = None
    t_py_pdp = 0
    attempts = candidates = 0
    if variant in ("v1", "v0"):
        while scalar is None:
            done = int(walk.stats[4])
            if done >= max_attempts:
                break
            hits = walk.run(rounds, True) if variant == "v1" else walk.run(max_attempts - done, True)
            if not len(hits) and int(walk.stats[4]) == done:
                break
            scalar, index = _finish(st, g, Q, hits, a0)
        s = walk.stats
        attempts, candidates = int(s[4]), int(s[5])
        c_walk, c_pdp, c_chk = int(s[0]), int(s[1]), int(s[2])
    else:
        sv, K = k.sv, C.K
        R, c_walk, c_pdp, c_chk = Q, 0, 0, 0
        for i in range(1, max_attempts + 1):
            ta = ns()
            R = K.add(R, step[:2])
            tb = ns()
            pairs = sv.decompose(R)
            tc = ns()
            c_walk += tb - ta
            c_pdp += tc - tb
            attempts += 1
            if pairs:
                hits = np.array([[i, R[0], R[1], *P1, *P2] for P1, P2 in pairs], dtype=object)
                scalar, index = _finish(st, g, Q, hits, a0)
                c_chk += ns() - tc
                if scalar is not None:
                    break
    t_rc0 = ns()
    verified = scalar is not None and k.smul(C.G, scalar)[:2] == tuple(Q)
    t_end = ns()
    online = t_end - t0
    t_rc = t_end - t_rc0
    phases = {"target_query": t_setup + c_walk, "target_pdp": c_pdp, "target_relation_check": c_chk,
              "target_recovery_check": t_rc}
    phases["target_descent"] = online - sum(phases.values())
    return {"online_ns": online, "phases_ns": phases, "attempts": attempts, "candidates": candidates,
            "attempt_index": index, "scalar": scalar, "verified": bool(verified)}


def rho_prepare(st: Setup, seed: str) -> dict:
    """Target-independent rho state: [c_j]G for the 32 table entries and [a_w]G for the W starts."""
    C, k = st.C, st.k
    r = C.r
    E = math.sqrt(math.pi * r / 2)
    W = 64 if E > 1e5 else 8
    dp_bits = max(0, int(math.log2(max(1.0, E / (W * 100)))))
    cap = 1 << max(10, math.ceil(math.log2(8 * E / 2 ** dp_bits + 1024)))
    rng = random.Random(seed)
    TC = [rng.randrange(1, r) for _ in range(32)]
    TE = [j % 2 for j in range(32)]
    rng.shuffle(TE)
    AW = [rng.randrange(1, r) for _ in range(W)]
    return {"W": W, "dp_bits": dp_bits, "table": np.zeros(cap, dtype=DP_DTYPE), "TC": TC, "TE": TE, "AW": AW,
            "TCG": [k.smul(C.G, c) for c in TC], "AWG": [k.smul(C.G, a) for a in AW]}


def online_rho(st: Setup, Q: tuple, prep: dict, max_steps: int) -> dict:
    """r-adding walk T_j = [c_j]G + e_j Q (e_j in {0, 1}, half of each), starts [a_w]G + Q."""
    C, k = st.C, st.k
    r, W, dp_bits, table = C.r, prep["W"], prep["dp_bits"], prep["table"]
    t0 = ns()
    Qp = (*Q, 0)
    T = [k.add(g, Qp) if e else g for g, e in zip(prep["TCG"], prep["TE"])]
    TX = np.array([t[0] for t in T], dtype=np.uint64)
    TY = np.array([t[1] for t in T], dtype=np.uint64)
    TC = np.array(prep["TC"], dtype=np.uint64)
    TD = np.array(prep["TE"], dtype=np.uint64)
    S = [k.add(g, Qp) for g in prep["AWG"]]
    X = np.array([p[0] for p in S], dtype=np.uint64)
    Y = np.array([p[1] for p in S], dtype=np.uint64)
    A = np.array(prep["AW"], dtype=np.uint64)
    B = np.ones(W, dtype=np.uint64)
    out = np.zeros(5, dtype=np.uint64)
    stats = np.zeros(3, dtype=np.int64)
    scalar, collisions = None, 0
    while scalar is None and int(stats[0]) < max_steps:
        if not rho_call(k, W, X, Y, A, B, TX, TY, TC, TD, (1 << dp_bits) - 1, table, 1 << 12, out, stats):
            continue
        collisions += 1
        a1, b1, a2, b2, sg = (int(v) for v in out)
        if sg == 1:
            num, den = a1 - a2, b2 - b1
        else:
            num, den = -(a1 + a2), b1 + b2
        if den % r:
            cand = num * pow(den, -1, r) % r
            if k.smul(C.G, cand)[:2] == tuple(Q):
                scalar = cand
    online = ns() - t0
    return {"online_ns": online, "steps": int(stats[0]), "walks": W, "dp_bits": dp_bits,
            "distinguished_points": int(stats[2]), "collisions": collisions, "scalar": scalar,
            "verified": scalar is not None, "c_walk_ns": int(stats[1]),
            "ns_per_step": int(stats[1]) / max(1, int(stats[0]))}


# ------------------------------------------------------------------ CLI

def next_run(path: Path, cid: str, wid: str) -> int:
    if not path.exists():
        return 1
    k = 0
    for line in path.open():
        if line.strip():
            row = json.loads(line)
            if row.get("candidate_id") == cid and row.get("workload_id") == wid:
                k = max(k, int(row["run_id"].rsplit("R", 1)[1]))
    return k + 1


def cmd_prepare(args) -> None:
    st = Setup(args.n, args.family, args.l, args.seed)
    g, rec = prepare(st, args.query_seed, args.relations)
    print(canonical({k: v for k, v in rec.items()}))


def cmd_panel(args) -> None:
    st = Setup(args.n, args.family, args.l, args.seed)
    g, pre = prepare(st, args.query_seed, args.relations)
    C = st.C
    ids = {v: candidate_record(st, v, args.query_seed, args.relations) for v in VARIANTS if v in args.variants}
    out_path = RESULTS / args.out
    RESULTS.mkdir(exist_ok=True)
    manifests = RESULTS / "manifests"
    manifests.mkdir(exist_ok=True)
    for v, (cid, rec) in ids.items():
        (manifests / f"{cid}.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    hw = host()
    # warm the kernel and the interpreter paths once, outside every timer
    online_ic(st, g, C.G, 12345, "v1", 64)
    if "rho" in args.variants:
        online_rho(st, C.G, rho_prepare(st, "warm-up"), 1 << 12)
    for index in range(args.first, args.first + args.targets):
        s = fixture_scalar(C, index)
        Q = st.k.smul(C.G, s)[:2]
        wid, wrec = workload_record(C, index, s, Q, args.query_seed, args.relations)
        (manifests / f"W{wid}.json").write_text(json.dumps(wrec, indent=1, sort_keys=True) + "\n")
        a0 = rerandomizer(C, index)
        order = list(args.variants)
        if index % 2:
            order.reverse()
        res = {}
        for v in order:
            if v == "rho":
                res[v] = online_rho(st, Q, rho_prepare(st, wrec["rho_stream"]), args.max_rho_steps)
            else:
                res[v] = online_ic(st, g, Q, a0, v, args.max_attempts if v != "py" else args.max_py_attempts)
            res[v]["matches_fixture"] = res[v]["scalar"] == s
        rho = res.get("rho")
        with out_path.open("a") as fh:
            for v in VARIANTS:
                if v not in res:
                    continue
                cid = ids[v][0]
                ic = res[v]
                ok = ic["verified"] and ic["matches_fixture"]
                rho_ok = rho is not None and rho["verified"] and rho["matches_fixture"]
                row = {
                    "schema": "ic-online-c-run/1", "candidate_id": cid, "workload_id": wid,
                    "run_id": f"{cid}W{wid}R{next_run(out_path, cid, wid)}", "variant": v, "n": C.n, "l": st.l,
                    "family": st.family, "fb_seed": st.seed, "curve_id": C.curve_id, "panel_index": index,
                    "target_x": Q[0], "target_y": Q[1], "fixture_scalar": s,
                    "status": "complete" if ok else ("budget" if ic["scalar"] is None else "error"),
                    "ic_online_ns": ic["online_ns"], "ic_phases_ns": ic["phases_ns"], "ic_attempts": ic["attempts"],
                    "ic_candidates": ic["candidates"], "ic_attempt_index": ic["attempt_index"],
                    "ic_scalar": ic["scalar"], "ic_verified": ok,
                    "online_interval": "from the first target-dependent operation ([a0]G, then Q + i [a0]G) to "
                                       "the verified [log Q]G = Q; the five phases sum to it exactly",
                    "rho_online_ns": None if rho is None else rho["online_ns"],
                    "rho_steps": None if rho is None else rho["steps"],
                    "rho_ns_per_step": None if rho is None else rho["ns_per_step"],
                    "rho_scalar": None if rho is None else rho["scalar"], "rho_verified": rho_ok,
                    "online_speedup": (rho["online_ns"] / ic["online_ns"]) if (ok and rho_ok) else None,
                    "rho_floor_estimate_ns": None if rho is None else
                    rho["ns_per_step"] * math.sqrt(math.pi * C.r / (4 * C.n)),
                    "rho_floor_rule": "supplementary prediction, not a run: measured ns per rho step x "
                                      "sqrt(pi r / (4 n)) steps on {+-tau^j P} classes, class canonicalization free",
                    "precompute": {k: pre[k] for k in ("walls_ns", "collection", "graph", "cache") if k in pre},
                    "host": hw,
                }
                fh.write(canonical(row) + "\n")
        line = f"#{index} " + " ".join(
            f"{v}={res[v]['online_ns'] / 1e6:.2f}ms{'' if res[v]['verified'] else '(X)'}" for v in order)
        print(line, flush=True)


def summarize(path: Path) -> None:
    rows = [json.loads(x) for x in path.open() if x.strip()]
    print("| candidate | variant | n | l | verified | IC online ms, median [IQR] | IC online ms, mean | "
          "rho online ms, median | rho/IC, geometric mean [bootstrap 95%] | floor estimate / IC mean | "
          "attempts, median |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault((r["candidate_id"], r["variant"]), []).append(r)
    rng = random.Random(0)
    for (cid, v), g in sorted(groups.items(), key=lambda t: (t[1][0]["n"], t[1][0]["l"], t[0][1])):
        ok = [r for r in g if r["ic_verified"]]
        ic = sorted(r["ic_online_ns"] / 1e6 for r in ok)
        rh = sorted(r["rho_online_ns"] / 1e6 for r in g if r["rho_verified"])
        sp = [r["online_speedup"] for r in g if r["online_speedup"]]
        if sp:
            logs = [math.log(x) for x in sp]
            boots = sorted(math.exp(statistics.fmean(rng.choices(logs, k=len(logs)))) for _ in range(2000))
            gm = f"{math.exp(statistics.fmean(logs)):.2f} [{boots[49]:.2f}, {boots[1949]:.2f}]"
        else:
            gm = "-"
        q = lambda xs, f: xs[min(len(xs) - 1, int(f * len(xs)))] if xs else float("nan")  # noqa: E731
        att = sorted(r["ic_attempts"] for r in ok)
        fl = [r["rho_floor_estimate_ns"] / 1e6 for r in g if r.get("rho_floor_estimate_ns")]
        floor = f"{statistics.fmean(fl) / statistics.fmean(ic):.2f}" if fl and ic else "-"
        print(f"| `{cid}` | {v} | {g[0]['n']} | {g[0]['l']} | {len(ok)}/{len(g)} | "
              f"{statistics.median(ic):.3f} [{q(ic, .25):.3f}, {q(ic, .75):.3f}] | {statistics.fmean(ic):.3f} | "
              f"{statistics.median(rh) if rh else float('nan'):.2f} | {gm} | {floor} | "
              f"{statistics.median(att) if att else '-'} |")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "panel"):
        p = sub.add_parser(name)
        p.add_argument("--n", type=int, default=41)
        p.add_argument("--family", default="geomtraceu")
        p.add_argument("--l", type=int, default=15)
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--query-seed", type=int, default=1)
        p.add_argument("--relations", type=float, default=2.0)
        if name == "panel":
            p.add_argument("--targets", type=int, default=8)
            p.add_argument("--first", type=int, default=0)
            p.add_argument("--variants", nargs="+", default=["v1", "v0", "rho"], choices=list(VARIANTS) + ["rho"])
            p.add_argument("--max-attempts", type=int, default=2_000_000)
            p.add_argument("--max-py-attempts", type=int, default=200_000)
            p.add_argument("--max-rho-steps", type=int, default=1 << 34)
            p.add_argument("--out", default="online-panel.jsonl")
    s = sub.add_parser("summarize")
    s.add_argument("path")
    args = ap.parse_args()
    if args.cmd == "prepare":
        cmd_prepare(args)
    elif args.cmd == "panel":
        cmd_panel(args)
    else:
        summarize(Path(args.path))


if __name__ == "__main__":
    main()
