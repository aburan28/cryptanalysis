"""Point-decomposition (summation polynomial + Weil descent) cost on E0 vs its
volcano descendants vs unrelated random-b curves, all at n = 131.

The descendants share E0's group, so any difference in index-calculus cost can
only come from the coefficient b in S_{m+1}.  This runs the pdp-scaling
pipeline (sumpoly.py / descend.py / solve.py, msolve F4 over F_2) on
planted instances for each curve and records msolve's own statistics.

    python3 pdp_descendants.py --m 3 --ls 4,5 --seeds 4 --random 40 --out pdp_m3.csv
    # factor-base control: E0 without 1 in V, the others with b^(1/4) in V
    python3 pdp_descendants.py --m 3 --ls 4,5 --groups E0 --e0-seeds 40 --bases shift --out pdp_m3_e0_shift.csv
    python3 pdp_descendants.py --m 3 --ls 4,5 --groups descendant,random --seeds 1 --random 40 \
        --bases qroot --out pdp_m3_qroot.csv
    # density control: one dense basis vector unrelated to b
    python3 pdp_descendants.py --m 3 --ls 5 --groups E0,descendant --seeds 1 --e0-seeds 20 \
        --descendants 20 --bases dense --out pdp_m3_dense.csv

The field is F_2[z]/(z^131 + z^13 + z^2 + z + 1), the modulus sweep.sage used,
so the b values in results.json are used as-is.  Set TMPDIR to a volume with
free space: every instance writes its msolve input to a temporary directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDP = HERE.parent / "pdp-scaling"
sys.path.insert(0, str(PDP))

import descend  # noqa: E402
import solve  # noqa: E402
import sumpoly  # noqa: E402
from gf2n import Curve, GF2n  # noqa: E402

N_FIELD = 131
WRAPPER = HERE / "msolve_stats.sh"

FIELDS = [
    "group", "orbit", "curve_id", "b", "basis", "m", "l", "seed", "status", "verified",
    "cpu", "vars", "monomials", "max_deg", "first_zero_deg", "degree_profile", "max_rows", "max_cols",
    "pairs_reduced", "zero_reductions", "basis_size",
]


def curves(n_random: int) -> list[dict]:
    res = json.load(open(HERE / "results.json"))
    out = [{"group": "E0", "orbit": "", "curve_id": "E0", "b": 1}]
    for r in res["descendants"]:
        if r["level"] == "floor":
            out.append({
                "group": "descendant",
                "orbit": r["frobenius_orbit"],
                "curve_id": f"d{r['kernel_index']}",
                "b": int(r["b_hex"], 16),
            })
    rng = random.Random(131)
    for i in range(n_random):
        out.append({
            "group": "random", "orbit": "", "curve_id": f"r{i}",
            "b": rng.getrandbits(N_FIELD) | 2,  # never in F_2
        })
    return out


# ---- factor-base bases ----------------------------------------------------
# std:   V = span{1, z, ..., z^(l-1)}           (the pdp-scaling default)
# shift: V = span{z, ..., z^l}                  (1 not in V)
# qroot: V = span{b^(1/4), z, ..., z^(l-1)}     (b^(1/4) in V; equals std on E0)
# dense: V = span{w, z, ..., z^(l-1)}, w a fixed dense element unrelated to b
# For m = 3, S_4's x_i^3 x_j x_k x_R coefficients pick up a factor
# (b + w^4) when both singletons are the same basis vector w, so V containing
# b^(1/4) kills 3*C(l,2) monomials of the descent whatever b is.

def basis_for(F: GF2n, kind: str, l: int, b: int) -> list[int]:
    if kind == "std":
        return [1 << j for j in range(l)]
    if kind == "shift":
        return [1 << (j + 1) for j in range(l)]
    if kind == "qroot":
        return [F.sqrt(F.sqrt(b))] + [1 << j for j in range(1, l)]
    if kind == "dense":
        return [random.Random(20260924).getrandbits(N_FIELD) | 1] + [1 << j for j in range(1, l)]
    raise ValueError(kind)


def block_polys_basis(F: GF2n, basis: list[int], max_e: int) -> list[dict[int, int]]:
    """descend.block_polys with x = sum_j v_j basis[j]."""
    out = []
    for e in range(max_e + 1):
        poly = {0: 1}
        k, ee = 0, e
        while ee:
            if ee & 1:
                lin = [(1 << j, F.frob(w, k)) for j, w in enumerate(basis)]
                nxt: dict[int, int] = {}
                for mask, c in poly.items():
                    for vm, zc in lin:
                        nm = mask | vm
                        nxt[nm] = nxt.get(nm, 0) ^ F.mul(c, zc)
                poly = {mk: c for mk, c in nxt.items() if c}
            ee >>= 1
            k += 1
        out.append(poly)
    return out


class BasisInstance(descend.Instance):
    basis: list[int] = []

    def x_from_assignment(self, v: int) -> list[int]:
        xs = []
        for i in range(self.m):
            c, x = (v >> (i * self.l)) & ((1 << self.l) - 1), 0
            for j, w in enumerate(self.basis):
                if (c >> j) & 1:
                    x ^= w
            xs.append(x)
        return xs


def liftable_in_V(m_: int, l: int, b: int, kind: str) -> int:
    """Number of nonzero x in V that lift to E_b (m distinct ones are needed)."""
    F = GF2n(N_FIELD)
    E = Curve(F, b)
    basis = basis_for(F, kind, l, b)
    count = 0
    for c in range(1, 1 << l):
        x = 0
        for j, w in enumerate(basis):
            if (c >> j) & 1:
                x ^= w
        count += E.lift_x(x) is not None
    return count


def make_instance_basis(m: int, l: int, seed: int, b: int, kind: str) -> descend.Instance:
    """descend.make_instance with the factor base V = span(basis_for(kind))."""
    rng = random.Random(seed)
    F = GF2n(N_FIELD)
    E = Curve(F, b)
    basis = basis_for(F, kind, l, b)
    S = sumpoly.load(m + 1)
    while True:
        cs, pts = [], []
        while len(pts) < m:
            c = rng.getrandbits(l)
            x = 0
            for j, w in enumerate(basis):
                if (c >> j) & 1:
                    x ^= w
            P = E.lift_x(x)
            if P is not None:
                cs.append(c)
                pts.append(P if rng.getrandbits(1) else E.neg(P))
        R = E.sum(pts)
        if not R.inf and len({P.x for P in pts}) == m:
            break
    saved = descend.block_polys
    descend.block_polys = lambda F_, l_, max_e: block_polys_basis(F_, basis, max_e)
    try:
        anf = descend.descend(S, F, E, m, l, R.x)
    finally:
        descend.block_polys = saved
    planted = 0
    for i, c in enumerate(cs):
        planted |= c << (i * l)
    inst = BasisInstance(n=N_FIELD, mod=F.mod, b=b, m=m, l=l, xR=R.x, anf=anf,
                         planted=planted, points=pts)
    inst.basis = basis
    assert inst.evaluate(planted) == 0
    return inst


STEP = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+) x (\d+)\s+[\d.]+%\s+(\d+) new\s+(\d+) zero")


def parse_stats(text: str) -> dict:
    steps = [tuple(int(g) for g in m.groups()) for m in map(STEP.match, text.splitlines()) if m]
    get = lambda pat: (lambda m: int(m.group(1)) if m else None)(re.search(pat, text))
    mx = re.search(r"max\. matrix data\s+(\d+) x (\d+)", text)
    first_zero = next((s[0] for s in steps if s[6] > 0), None)
    return {
        "max_deg": max((s[0] for s in steps), default=None),
        "first_zero_deg": first_zero,
        "degree_profile": "-".join(str(s[0]) for s in steps),
        "max_rows": int(mx.group(1)) if mx else None,
        "max_cols": int(mx.group(2)) if mx else None,
        "pairs_reduced": get(r"#pairs reduced\s+(\d+)"),
        "zero_reductions": get(r"#zero reductions\s+(\d+)"),
        "basis_size": get(r"size of basis\s+(\d+)"),
    }


def job(args: tuple) -> dict:
    cur, m, l, seed, timeout, kind = args
    row = {k: cur[k] for k in ("group", "orbit", "curve_id")}
    row.update({"b": hex(cur["b"]), "basis": kind, "m": m, "l": l, "seed": seed})
    if liftable_in_V(m, l, cur["b"], kind) < m:
        # make_instance would loop forever: fewer than m distinct x in V lift.
        return {**row, "status": "infeasible"}
    with tempfile.TemporaryDirectory() as d:
        stats = os.path.join(d, "stats.txt")
        os.environ["MSOLVE"] = str(WRAPPER)
        os.environ["MSOLVE_STATS"] = stats
        if kind == "std":
            inst = descend.make_instance(N_FIELD, m, l, seed, b=cur["b"])
        else:
            inst = make_instance_basis(m, l, seed, cur["b"], kind)
        assert inst.mod == GF2n(N_FIELD).mod
        t0 = time.process_time()
        res = solve.solve_msolve(inst, timeout, 1)
        row.update({
            "status": res["status"], "verified": res.get("verified", False),
            "cpu": res.get("seconds", time.process_time() - t0),
            "vars": inst.nvars, "monomials": len(inst.anf),
        })
        if os.path.exists(stats):
            row.update(parse_stats(open(stats).read()))
        return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--ls", default="4,5")
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--random", type=int, default=40)
    ap.add_argument("--e0-seeds", type=int, default=0, help="extra seeds for E0 (default: seeds*20)")
    ap.add_argument("--descendants", type=int, default=0, help="limit descendants (0 = all 262)")
    ap.add_argument("--bases", default="std", help="comma-separated: std, shift, qroot")
    ap.add_argument("--groups", default="E0,descendant,random", help="comma-separated curve groups")
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--jobs", type=int, default=10)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    cs = [c for c in curves(a.random) if c["group"] in a.groups.split(",")]
    if a.descendants:
        ds = [c for c in cs if c["group"] == "descendant"]
        keep = {c["curve_id"] for c in ds[:: max(1, len(ds) // a.descendants)][: a.descendants]}
        cs = [c for c in cs if c["group"] != "descendant" or c["curve_id"] in keep]
    e0_seeds = a.e0_seeds or a.seeds * 20
    tasks = []
    for l in (int(x) for x in a.ls.split(",")):
        for c in cs:
            ns = e0_seeds if c["group"] == "E0" else a.seeds
            for kind in a.bases.split(","):
                tasks += [(c, a.m, l, s, a.timeout, kind) for s in range(1, ns + 1)]
    # Interleave curves so CPU time is not confounded with run order.
    random.Random(0).shuffle(tasks)
    print(f"{len(tasks)} instances", file=sys.stderr)
    out = Path(a.out)
    with out.open("w", newline="") as fh, Pool(a.jobs) as pool:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for i, row in enumerate(pool.imap_unordered(job, tasks), 1):
            w.writerow(row)
            fh.flush()
            if i % 100 == 0:
                print(f"{i}/{len(tasks)}", file=sys.stderr)


if __name__ == "__main__":
    main()
