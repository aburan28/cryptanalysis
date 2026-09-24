"""G5: per-curve summation-polynomial (Semaev) systems on the real n = 131 curves.

Everything here runs under `sage -python`.  Field: F_2[z]/(z^131+z^13+z^2+z+1),
elements exchanged as integer bitmasks (bit i = z^i), via the ground-truth loader.

Boolean variables: x_i = sum_j v_{i,j} w_j, (w_j) a basis of the subspace V (k-dim),
variable index i*k + j  <->  bit i*k+j of a monomial mask (multilinear monomials).

Systems:
  plain : the n = 131 bit equations of S_{m+1}(x_1..x_m, x(R)) plus the field equations
          v^2 + v  (the standard PDP system).
  codex : plain + Codex's rational-lift membership indicators (one per block) + pairwise
          distinct-x constraints (Codex run-01 `make_equations`, m = 3 only).

Measurements:
  * msolve 0.9.5 F4 (grevlex, 1 thread): per-round degree table, max degree reached,
    CPU time, reduced GB -> number of F_2 solutions;
  * Codex's formal "degree of regularity": full F_2 row reduction of the generator list
    (degree-compatible pivots), J = ideal of the highest-degree components, d_reg = 1 + max
    degree of a standard monomial of R/J (Singular std, degrevlex);
  * the exact solution set by brute force (subset-sum / Moebius transform of the ANF),
    independent of both solvers.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import random
import re
import resource
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k  # noqa: E402
import numpy as np  # noqa: E402
from sage.all import GF, EllipticCurve, PolynomialRing  # noqa: E402

K = ecc2k.field()
ZGEN = K.gen()
N = ecc2k.N
NB = 131
MSOLVE = os.environ.get("MSOLVE", "/opt/homebrew/bin/msolve")
TMP = Path(os.environ.get("TMPDIR", "/Volumes/SSD990/ecdlp-hardness-work/tmp"))
assert str(TMP).startswith("/Volumes/SSD990/"), "TMPDIR must be on the SSD"
M64 = (1 << 64) - 1


def dec(i):
    return K.from_integer(int(i))


def enc(u):
    return int(u.to_integer())


def ftrace(u) -> int:
    return int(u.trace())


# --------------------------------------------------------------------------
# Boolean polynomials with F_q coefficients: dict mask -> K element (nonzero)
# --------------------------------------------------------------------------
def padd(*ps):
    d = {}
    for p in ps:
        for m, c in p.items():
            if m in d:
                v = d[m] + c
                if v:
                    d[m] = v
                else:
                    del d[m]
            else:
                d[m] = c
    return d


def pmul(p, q):
    d = {}
    for m, c in p.items():
        for n, e in q.items():
            z = m | n
            v = c * e
            if z in d:
                v = d[z] + v
                if v:
                    d[z] = v
                else:
                    del d[z]
            elif v:
                d[z] = v
    return d


def psq(p):
    # (sum c_M M)^2 = sum c_M^2 M^2 = sum c_M^2 M in the Boolean ring (char 2)
    return {m: c * c for m, c in p.items()}


def pscale(p, a):
    if not a:
        return {}
    return {m: c * a for m, c in p.items()}


def S_field(m, xs, r, b):
    """S_{m+1}(x_1..x_m, r) evaluated in F_q (same formulas as the Boolean version)."""
    if m == 2:
        x1, x2 = xs
        return x1**2 * x2**2 + x1**2 * r**2 + x2**2 * r**2 + x1 * x2 * r + b
    if m == 3:
        x, y, z = xs
        a1 = (x + y) ** 2
        b1 = x * y
        c1 = b1**2 + b
        a2 = (z + r) ** 2
        b2 = z * r
        c2 = b2**2 + b
        return (a1 * c2 + a2 * c1) ** 2 + (a1 * b2 + a2 * b1) * (b1 * c2 + b2 * c1)
    raise ValueError(m)


def descended_anf(m, basis, b, r):
    """S_{m+1}(x_1, .., x_m, r) with x_i = sum_j v_{ij} basis[j], in the Boolean ring.
    Returns {mask: int coefficient in F_q (bitmask)}; bit t of the coefficient = equation t."""
    k = len(basis)
    xs = [{1 << (i * k + j): basis[j] for j in range(k)} for i in range(m)]
    if m == 2:
        x1, x2 = xs
        x1x2 = pmul(x1, x2)
        r2 = r * r
        s = padd(psq(x1x2), pscale(psq(x1), r2), pscale(psq(x2), r2), pscale(x1x2, r), {0: b})
    elif m == 3:
        x, y, z = xs
        a1 = psq(padd(x, y))
        b1 = pmul(x, y)
        c1 = padd(psq(b1), {0: b})
        a2 = psq(padd(z, {0: r}))
        b2 = pscale(z, r)
        c2 = padd(psq(b2), {0: b})
        s = padd(
            psq(padd(pmul(a1, c2), pmul(a2, c1))),
            pmul(padd(pmul(a1, b2), pmul(a2, b1)), padd(pmul(b1, c2), pmul(b2, c1))),
        )
    else:
        raise ValueError(m)
    return {mask: enc(c) for mask, c in s.items() if c}


def anf_equations(anf):
    """Split {mask: F_q coefficient} into the 131 Boolean equations (sets of masks)."""
    eqs = [set() for _ in range(NB)]
    for mask, c in anf.items():
        while c:
            lo = c & -c
            eqs[lo.bit_length() - 1].add(mask)
            c ^= lo
    return [e for e in eqs if e]


def coeff_rank(anf) -> int:
    """F_2-dimension of the span of the coefficients = number of independent Boolean
    equations of the descended S_{m+1} (the ideal only depends on this span)."""
    piv = {}
    for c in anf.values():
        v = c
        while v:
            h = v.bit_length() - 1
            if h in piv:
                v ^= piv[h]
            else:
                piv[h] = v
                break
    return len(piv)


def eval_anf(anf, a: int) -> int:
    acc = 0
    for mask, c in anf.items():
        if mask & ~a == 0:
            acc ^= c
    return acc


def solutions_bruteforce(anf, nv):
    """All assignments a in F_2^nv with sum_{mask subset of a} c_mask = 0 (Moebius/zeta transform)."""
    size = 1 << nv
    A = np.zeros((size, 3), dtype=np.uint64)
    for mask, c in anf.items():
        A[mask, 0] = c & M64
        A[mask, 1] = (c >> 64) & M64
        A[mask, 2] = c >> 128
    for i in range(nv):
        B = A.reshape(-1, 2, 1 << i, 3)
        B[:, 1] ^= B[:, 0]
    zero = ~(A.any(axis=1))
    return [int(a) for a in np.nonzero(zero)[0]]


def anf_degree(anf) -> int:
    return max((bin(mm).count("1") for mm in anf), default=-1)


# --------------------------------------------------------------------------
# subspaces
# --------------------------------------------------------------------------
def poly_basis(k):
    return [ZGEN**j for j in range(k)]


def random_basis(k, rng):
    """k F_2-independent random field elements (Codex's coordinate_basis procedure)."""
    basis = []
    pivots = {}
    while len(basis) < k:
        u = rng.getrandbits(NB)
        v = u
        while v and v.bit_length() - 1 in pivots:
            v ^= pivots[v.bit_length() - 1]
        if v:
            pivots[v.bit_length() - 1] = v
            basis.append(dec(u))
    return basis


def span_values(basis):
    k = len(basis)
    vals = [K.zero()] * (1 << k)
    for mask in range(1, 1 << k):
        low = mask & -mask
        vals[mask] = vals[mask ^ low] + basis[low.bit_length() - 1]
    return vals


def is_independent(basis):
    vals = span_values(basis)
    return len({enc(v) for v in vals}) == len(vals)


# --------------------------------------------------------------------------
# curves, factor base, targets
# --------------------------------------------------------------------------
class CurveCtx:
    def __init__(self, label, b, a2=0, order=None):
        self.label = label
        self.b = b
        self.E = EllipticCurve(K, [1, a2, 0, 0, b])
        if order is None:
            order = int(self.E.cardinality(algorithm="pari"))
        self.order = order
        assert order % 4 == 0
        nodd = order
        while nodd % 2 == 0:
            nodd //= 2
        self.nodd = nodd              # odd part (= N for the class curves)
        self.two = order // nodd      # size of the 2-primary part (4 for Tr(b) = 1)
        self.two_part_is_z4 = self.two == 4

    def random_odd_target(self, rng):
        """[2-part] * (random point): a random point of the odd-order subgroup (the
        N-subgroup for the class curves, where this is [4]P)."""
        while True:
            x = dec(rng.getrandbits(NB))
            pts = self.E.lift_x(x, all=True)
            if not pts:
                continue
            P = pts[rng.getrandbits(1) % len(pts)]
            R = self.two * P
            if not R.is_zero():
                assert (self.nodd * R).is_zero()
                return R


def _pkey(P):
    return None if P.is_zero() else (enc(P[0]), enc(P[1]))


def factor_domain(C: CurveCtx, basis):
    """Rational-lift membership over V (x != 0) and the 2-primary component [nodd]P of each
    lift (Codex's four-torsion tags; identical test for any 2-part)."""
    vals = span_values(basis)
    lifts, tors = {}, {}
    tpts = {}
    for mask, x in enumerate(vals):
        if mask == 0:
            continue
        pts = C.E.lift_x(x, all=True)
        if pts:
            assert len(pts) == 2 and pts[1] == -pts[0]
            p = min(pts, key=lambda P: enc(P[1]))
            lifts[mask] = (p, -p)
            T = C.nodd * p
            assert (C.two * T).is_zero()
            tors[mask] = (_pkey(T), _pkey(-T))
            tpts[_pkey(T)] = T
            tpts[_pkey(-T)] = -T
    tpts[None] = C.E(0)
    add = {}  # lazily filled cache of sums in the 2-primary group (key, key) -> key
    return {"basis": basis, "values": vals, "lifts": lifts, "tors": tors, "tadd": add, "tpts": tpts}


def _tors_sum(domain, ids, signs):
    """Key of the sum of the 2-primary components (None = O), with a cache of point sums."""
    add, tpts = domain["tadd"], domain["tpts"]
    acc = None
    for i, s in zip(ids, signs):
        t = domain["tors"][i][s]
        key = (acc, t)
        if key not in add:
            S = tpts[acc] + tpts[t]
            ks = _pkey(S)
            tpts.setdefault(ks, S)
            add[key] = ks
        acc = add[key]
    return acc


def enumerate_image(domain, m=3, odd_only=True):
    """Codex's exact image: signed m-subsets of distinct rational x's whose sum lies in the
    odd-order subgroup (odd_only=False: no subgroup filter).  key (enc x, enc y) -> set of
    x-mask tuples."""
    image = {}
    ids = sorted(domain["lifts"])
    for tri in itertools.combinations(ids, m):
        for signs in itertools.product(range(2), repeat=m):
            if odd_only and _tors_sum(domain, tri, signs) is not None:
                continue
            pts = [domain["lifts"][i][s] for i, s in zip(tri, signs)]
            T = pts[0]
            for P in pts[1:]:
                T = T + P
            if T.is_zero():
                continue
            key = (enc(T[0]), enc(T[1]))
            image.setdefault(key, set()).add(tri)
    return image


def planted_target(C: CurveCtx, domain, m, rng, odd_only=True, tries=100000):
    ids = sorted(domain["lifts"])
    if len(ids) < m:
        return None
    for _ in range(tries):
        tri = rng.sample(ids, m)
        signs = [rng.getrandbits(1) for _ in range(m)]
        if odd_only and _tors_sum(domain, tri, signs) is not None:
            continue
        pts = [domain["lifts"][i][s] for i, s in zip(tri, signs)]
        T = pts[0]
        for P in pts[1:]:
            T = T + P
        if T.is_zero():
            continue
        if odd_only:
            assert (C.nodd * T).is_zero()
        return T, sorted(tri)
    return None


# --------------------------------------------------------------------------
# Codex-mode extra generators (membership indicator ANF, distinctness)
# --------------------------------------------------------------------------
def membership_anf(allowed, k):
    """ANF (over F_2, as a set of masks on k variables) of the NON-membership indicator."""
    truth = [0 if i in allowed else 1 for i in range(1 << k)]
    anf = truth[:]
    for i in range(k):
        for mm in range(1 << k):
            if mm >> i & 1:
                anf[mm] ^= anf[mm ^ (1 << i)]
    return {mm for mm, c in enumerate(anf) if c}


def distinct_poly(a, c, k):
    """prod_i (1 + v_{a,i} + v_{c,i}) as a set of masks (multilinear)."""
    poly = {0}
    for i in range(k):
        va, vc = 1 << (a * k + i), 1 << (c * k + i)
        new = {}
        for mm in poly:
            for t in (0, va, vc):
                z = mm | t
                new[z] = new.get(z, 0) ^ 1
        poly = {z for z, v in new.items() if v}
    return poly


# --------------------------------------------------------------------------
# generator lists.  A generator is a set of monomials; a monomial is a mask
# (multilinear) or ("sq", i) for v_i^2.
# --------------------------------------------------------------------------
def build_generators(anf, nv, k=None, m=None, mode="plain", allowed=None):
    gens = [set(e) for e in anf_equations(anf)]
    n_desc = len(gens)
    if mode == "codex":
        mem = membership_anf(allowed, k)
        for blk in range(m):
            if mem:
                gens.append({mm << (blk * k) for mm in mem})
        for a, c in itertools.combinations(range(m), 2):
            gens.append(distinct_poly(a, c, k))
    for i in range(nv):
        gens.append({("sq", i), 1 << i})
    return gens, n_desc


def _mon_key(mon, nv):
    """Codex's row-reduction column order: (degree, exponent tuple) ascending."""
    if isinstance(mon, tuple):
        i = mon[1]
        e = tuple(2 if j == i else 0 for j in range(nv))
        return (2, e)
    e = tuple((mon >> j) & 1 for j in range(nv))
    return (sum(e), e)


def _mon_deg(mon):
    return 2 if isinstance(mon, tuple) else bin(mon).count("1")


def row_reduce(gens, nv):
    """Full F_2 row reduction of the coefficient matrix with the pivot = the largest monomial
    in the (degree, exponent-tuple) order (identical to Codex run-01 `row_reduce`)."""
    mons = sorted(set().union(*gens), key=lambda mm: _mon_key(mm, nv))
    index = {mm: i for i, mm in enumerate(mons)}
    rows = [sum(1 << index[mm] for mm in g) for g in gens]
    pivots = {}
    for row in rows:
        while row:
            p = row.bit_length() - 1
            if p not in pivots:
                pivots[p] = row
                break
            row ^= pivots[p]
    for p in sorted(pivots):
        for q in sorted(pivots):
            if q > p and (pivots[q] >> p) & 1:
                pivots[q] ^= pivots[p]
    out = []
    for p in sorted(pivots, reverse=True):
        row = pivots[p]
        g = set()
        while row:
            lo = row & -row
            g.add(mons[lo.bit_length() - 1])
            row ^= lo
        out.append(g)
    return out


def top_form(g):
    d = max(_mon_deg(mm) for mm in g)
    return {mm for mm in g if _mon_deg(mm) == d}, d


_RINGS = {}


def sage_ring(nv):
    if nv not in _RINGS:
        _RINGS[nv] = PolynomialRing(GF(2), nv, names=[f"u{i}" for i in range(nv)], order="degrevlex")
    return _RINGS[nv]


def to_sage(g, nv):
    S = sage_ring(nv)
    d = {}
    for mm in g:
        if isinstance(mm, tuple):
            e = tuple(2 if j == mm[1] else 0 for j in range(nv))
        else:
            e = tuple((mm >> j) & 1 for j in range(nv))
        d[e] = 1
    return S(d)


def formal_regularity(gens, nv, cap, reduce_first=True):
    """Codex's formal d_reg: J = <top forms of the (row-reduced) generators>,
    d_reg = 1 + max degree of the standard monomials of R/J (0 for the unit ideal)."""
    from cysignals.alarm import AlarmInterrupt, alarm, cancel_alarm

    t0 = time.process_time()
    red = row_reduce(gens, nv) if reduce_first else [set(g) for g in gens]
    t_rr = time.process_time() - t0
    tops = [top_form(g)[0] for g in red]
    deg_hist = {}
    for g in red:
        d = top_form(g)[1]
        deg_hist[d] = deg_hist.get(d, 0) + 1
    rec = {
        "reduced": reduce_first,
        "n_generators": len(red),
        "generator_top_degree_hist": {str(k): v for k, v in sorted(deg_hist.items())},
        "row_reduction_cpu": t_rr,
        "unit_after_rr": any(g == {0} for g in red),
    }
    if rec["unit_after_rr"]:
        rec.update({"status": "verified", "d_reg": 0, "top_quotient_dim": 0, "hilbert_function": [],
                    "std_cpu": 0.0})
        return rec
    S = sage_ring(nv)
    H = S.ideal([to_sage(t, nv) for t in tops])
    try:
        alarm(cap)
        t1 = time.process_time()
        HG = H.groebner_basis(algorithm="libsingular:std")
        H.groebner_basis.set_cache(HG)
        nb = H.normal_basis()
        t_std = time.process_time() - t1
        cancel_alarm()
    except AlarmInterrupt:
        rec.update({"status": "timeout", "cap_seconds": cap, "d_reg": None, "top_quotient_dim": None})
        return rec
    finally:
        cancel_alarm()
    hf = {}
    for mono in nb:
        dd = int(mono.degree())
        hf[dd] = hf.get(dd, 0) + 1
    dmax = max(hf) if hf else -1
    rec.update({
        "status": "verified",
        "d_reg": 0 if not nb else 1 + dmax,
        "top_quotient_dim": len(nb),
        "hilbert_function": [hf.get(d, 0) for d in range(dmax + 1)],
        "std_cpu": t_std,
    })
    return rec


# --------------------------------------------------------------------------
# msolve
# --------------------------------------------------------------------------
_ROUND = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+) x (\d+)\s+([\d.]+)%\s+(\d+) new\s+(\d+) zero\s+([\d.]+) \|\s*([\d.]+)"
)


def _mon_str(mm, names):
    if isinstance(mm, tuple):
        return f"{names[mm[1]]}^2"
    if mm == 0:
        return "1"
    return "*".join(names[j] for j in range(len(names)) if (mm >> j) & 1)


def run_msolve(gens, nv, cap, tag):
    names = [f"v{i}" for i in range(nv)]
    TMP.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(tag.encode()).hexdigest()[:16]
    inp = TMP / f"g5_{h}_{os.getpid()}.ms"
    out = TMP / f"g5_{h}_{os.getpid()}.out"
    polys = ["+".join(_mon_str(mm, names) for mm in sorted(g, key=lambda x: (isinstance(x, tuple), x))) for g in gens if g]
    inp.write_text(",".join(names) + "\n2\n" + ",\n".join(polys) + "\n")
    r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    w0 = time.monotonic()
    cmd = ["timeout", str(int(cap)), MSOLVE, "-v", "2", "-g", "2", "-t", "1", "-f", str(inp), "-o", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    wall = time.monotonic() - w0
    r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
    rec = {"cpu": cpu, "wall": wall, "returncode": p.returncode, "input_bytes": inp.stat().st_size}
    if p.returncode == 124:
        rec["status"] = "timeout"
        rec["cap_seconds"] = cap
        inp.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
        return rec, None
    if p.returncode != 0:
        rec["status"] = "error"
        rec["stderr"] = p.stderr[-800:]
        rec["stdout_tail"] = p.stdout[-800:]
        return rec, None
    rounds = []
    for line in p.stdout.splitlines():
        mt = _ROUND.match(line)
        if mt:
            g = mt.groups()
            rounds.append({"deg": int(g[0]), "sel": int(g[1]), "pairs": int(g[2]),
                           "rows": int(g[3]), "cols": int(g[4]), "density": float(g[5]),
                           "new": int(g[6]), "zero": int(g[7]), "cpu": float(g[9])})
    mo = re.search(r"overall\(cpu\)\s+([\d.]+)", p.stdout)
    rec["msolve_cpu_reported"] = float(mo.group(1)) if mo else None
    mo = re.search(r"max\. matrix data\s+(\d+) x (\d+)", p.stdout)
    rec["max_matrix"] = [int(mo.group(1)), int(mo.group(2))] if mo else None
    mo = re.search(r"#zero reductions\s+(\d+)", p.stdout)
    rec["zero_reductions"] = int(mo.group(1)) if mo else None
    mo = re.search(r"size of basis\s+(\d+)", p.stdout)
    rec["basis_size_before_reduce"] = int(mo.group(1)) if mo else None
    rec["rounds"] = rounds
    rec["degree_sequence"] = [r["deg"] for r in rounds]
    rec["max_degree"] = max((r["deg"] for r in rounds), default=None)
    rec["n_rounds"] = len(rounds)
    text = out.read_text()
    inp.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    body = text[text.index("[") + 1: text.rindex("]")]
    basis = [s.strip() for s in body.replace("\n", "").split(",") if s.strip()]
    rec["status"] = "ok"
    return rec, basis


def parse_poly(s, nv):
    """msolve output polynomial -> list of exponent tuples (F_2 coefficients)."""
    mons = []
    for term in s.replace("-", "+").split("+"):
        term = term.strip()
        if not term:
            continue
        e = [0] * nv
        coef = 1
        for f in term.split("*"):
            f = f.strip()
            if f.startswith("v"):
                if "^" in f:
                    v, ex = f.split("^")
                    e[int(v[1:])] += int(ex)
                else:
                    e[int(f[1:])] += 1
            else:
                coef = int(f) % 2
        if coef:
            mons.append(tuple(e))
    # F_2: cancel duplicates
    cnt = {}
    for e in mons:
        cnt[e] = cnt.get(e, 0) ^ 1
    return [e for e, c in cnt.items() if c]


def drl_leading(mons):
    # degrevlex, v0 > v1 > ... : larger degree wins; ties: smaller exponent in the LAST
    # differing variable wins
    def key(e):
        return (sum(e), tuple(-x for x in reversed(e)))
    return max(mons, key=key)


def gb_solution_count(basis, nv, check_points=()):
    """#standard monomials of the reduced GB (= #F_2-solutions: the ideal contains the field
    equations, so it is radical and all its zeros are F_2-rational)."""
    if basis == ["1"]:
        return 0, True
    polys = [parse_poly(s, nv) for s in basis]
    lms = []
    for pm in polys:
        e = drl_leading(pm)
        if any(x >= 2 for x in e):
            continue  # v_i^2 leading terms: standard monomials are squarefree anyway
        lms.append(sum(1 << i for i, x in enumerate(e) if x))
    for i in range(nv):
        # make sure every v_i^2 is in LT (field equations); if not, the count is not finite
        pass
    arr = np.arange(1 << nv, dtype=np.int64)
    bad = np.zeros(1 << nv, dtype=bool)
    for L in lms:
        bad |= (arr & L) == L
    count = int((~bad).sum())
    ok = True
    for a in check_points:
        for pm in polys:
            v = 0
            for e in pm:
                if all((a >> i) & 1 for i, x in enumerate(e) if x):
                    v ^= 1
            if v:
                ok = False
    return count, ok


# --------------------------------------------------------------------------
# solution classification
# --------------------------------------------------------------------------
def classify_solutions(C: CurveCtx, basis, m, sols, R):
    """For each Boolean solution: are all x_i liftable to E(F_q), and does some signed sum
    of the lifts equal +-R?  Returns counts."""
    k = len(basis)
    vals = span_values(basis)
    out = {"n": len(sols), "all_rational_and_sum_ok": 0, "nonrational": 0, "rational_but_no_sum": 0,
           "x_zero_present": 0, "repeated_x": 0}
    for a in sols:
        xs_masks = [(a >> (i * k)) & ((1 << k) - 1) for i in range(m)]
        if any(mm == 0 for mm in xs_masks):
            out["x_zero_present"] += 1
        if len(set(xs_masks)) < m:
            out["repeated_x"] += 1
        pts = []
        okr = True
        for mm in xs_masks:
            x = vals[mm]
            if x == 0:
                okr = False
                break
            L = C.E.lift_x(x, all=True)
            if not L:
                okr = False
                break
            pts.append(L[0])
        if not okr:
            out["nonrational"] += 1
            continue
        hit = False
        for signs in itertools.product((1, -1), repeat=m):
            T = C.E(0)
            for s, P in zip(signs, pts):
                T = T + (P if s == 1 else -P)
            if not T.is_zero() and T[0] == R[0]:
                hit = True
                break
        if hit:
            out["all_rational_and_sum_ok"] += 1
        else:
            out["rational_but_no_sum"] += 1
    return out


def seed_int(*parts) -> int:
    return int.from_bytes(hashlib.sha256(":".join(str(p) for p in parts).encode()).digest()[:8], "big")
