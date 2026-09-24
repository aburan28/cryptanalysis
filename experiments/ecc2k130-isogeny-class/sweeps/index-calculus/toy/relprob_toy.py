"""Toy check that the m-summand relation probability over a subspace factor base depends only
on |F|, not on the endomorphism ring.  Analogue of ECC2K-130 at n = 19:

  E0_19 : y^2 + xy = x^3 + 1 over F_{2^19},  #E0 = 4 * 130873 (prime),
  t^2 - 4q = -7 * 457^2, kronecker(-7, 457) = +1  ->  457-volcano with E0 alone on the crater
  and h(-7*457^2) = 456 floor curves (conductor 457), exactly like 263 for n = 131.

For E0, a seeded sample of 100 of the 456 floor curves, 100 random non-isogenous curves (a2 = 0,
Tr(b) uniform) and 100 random non-isogenous curves with Tr(b) = 1 (#E = 4 mod 8, like the class),
for l in {5, 6, 7} and m in {2, 3, 4}, we compute EXACTLY
  S_m = { P_1 + ... + P_m : P_i in F_V },  F_V = { P : x(P) in span(1, z, ..., z^(l-1)) },
by discrete logs in the cyclic group E(F_q) = Z/4N and boolean sumsets, and report
  y_m = |S_m| / #E   (probability that a uniformly random point decomposes; for class curves
also over the order-N subgroup), next to the same quantity for a uniformly random subset of the
same cyclic group, closed under negation, of the same size |F_V| and containing the unique point
of order 2 (x = 0) like F_V does (so the |F|-dependence is removed exactly, curve by curve).
Every E(F_{2^19}) is cyclic because q - 1 = 2^19 - 1 is prime.

Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; sage -python relprob_toy.py
"""
import json, time, random, math
import numpy as np
from sage.all import GF, PolynomialRing, EllipticCurve, pari, ZZ, kronecker, is_prime

OUT = "/Volumes/SSD990/ecdlp-hardness-work/index-calculus/toy/"
n = 19
ELL = 457
t0 = time.time()
R = PolynomialRing(GF(2), "z")
zz = R.gen()
# first irreducible trinomial / pentanomial of degree 19, as in pdp-scaling/gf2n.py style
mod = None
for a in range(1, n):
    f = zz ** n + zz ** a + 1
    if f.is_irreducible():
        mod = f
        break
if mod is None:
    for a in range(3, n):
        for b in range(2, a):
            for c in range(1, b):
                f = zz ** n + zz ** a + zz ** b + zz ** c + 1
                if mod is None and f.is_irreducible():
                    mod = f
K = GF(2 ** n, "z", modulus=mod)
z = K.gen()
q = 2 ** n
tt = [2, -1]
for i in range(2, n + 1):
    tt.append(-tt[-1] - 2 * tt[-2])
t = tt[n]
CARD = q + 1 - t
N = CARD // 4
assert CARD == 4 * N and is_prime(N)
assert t * t - 4 * q == -7 * ELL ** 2 and kronecker(-7, ELL) == 1
info = {"n": n, "modulus": str(mod), "t": t, "card": CARD, "N": N, "ell": ELL}

# floor j-invariants: roots of H_D mod 2, D = -7*457^2
D = -7 * ELL ** 2
tp = time.time()
H = pari.polclass(D)
info["polclass_seconds"] = time.time() - tp
Hz = PolynomialRing(ZZ, "Y")(list(reversed(pari.Vec(H).sage())))
H2 = Hz.change_ring(K)
roots = [r for r, e in H2.roots()]
info["hD_degree"] = int(Hz.degree())
info["floor_roots_in_Fq"] = len(roots)
assert len(roots) == Hz.degree() == 456
curves = {"E0": (0, K(1))}
for idx, j in enumerate(sorted(roots, key=lambda u: u.to_integer())):
    b = 1 / j
    E = EllipticCurve(K, [1, 0, 0, 0, b])
    a2 = 0 if E.cardinality() == CARD else 1
    E = EllipticCurve(K, [1, a2, 0, 0, b])
    assert E.cardinality() == CARD
    curves["F%03d" % idx] = (a2, b)
info["floor_a2_values"] = sorted(set(v[0] for k, v in curves.items() if k != "E0"))
rng = random.Random(1919)
floor_keep = sorted(rng.sample([k for k in curves if k != "E0"], 100))
curves = {k: curves[k] for k in ["E0"] + floor_keep}
info["floor_sample"] = "100 of 456 floor curves, random.Random(1919).sample"
nullc, nullm = {}, {}
while len(nullc) < 100 or len(nullm) < 100:
    b = K.from_integer(rng.randrange(2, q))
    E = EllipticCurve(K, [1, 0, 0, 0, b])
    c = E.cardinality()
    if c in (CARD, q + 1 + t):
        continue
    if len(nullc) < 100:
        nullc["R%03d" % len(nullc)] = (0, b)
    elif b.trace() == 1 and len(nullm) < 100:
        assert c % 8 == 4
        nullm["S%03d" % len(nullm)] = (0, b)
curves.update(nullc)
curves.update(nullm)
info["class_Tr_b"] = sorted(set(int(v[1].trace()) for k, v in curves.items() if k == "E0" or k.startswith("F")))
print("curves ready %.1fs" % (time.time() - t0), info, flush=True)

LS = [5, 6, 7]
MS = [2, 3, 4]
nprng = np.random.default_rng(7)


def sumsets(logs, M, mmax):
    """boolean indicator arrays of S_1..S_mmax in Z/M"""
    base = np.zeros(M, dtype=bool)
    base[np.asarray(logs) % M] = True
    out = {1: base}
    cur = base
    for m in range(2, mmax + 1):
        nxt = np.zeros(M, dtype=bool)
        for f in np.flatnonzero(base):
            nxt |= np.roll(cur, int(f))
        out[m] = nxt
        cur = nxt
    return out


def random_symmetric(size, M):
    """random subset of Z/M closed under negation with the same size and the same number of
    self-inverse elements as a factor base containing the 2-torsion point (x = 0) once."""
    s = set([M // 2])            # the point of order 2 (x = 0 point) is always in F_V
    while len(s) < size:
        a = int(nprng.integers(1, M))
        if a == M // 2 or a in s:
            continue
        s.add(a)
        s.add((-a) % M)
    return sorted(s)


def halftrace(c):
    h, u = c, c
    for _ in range((n - 1) // 2):
        u = u ** 4
        h += u
    return h


def lift_points(E, a2, b, x):
    """both points with abscissa x (one if x = 0), via the half-trace; [] if none"""
    if x == 0:
        return [E(0, b.sqrt())]
    c = x + a2 + b / (x * x)
    if c.trace() != 0:
        return []
    w = halftrace(c)
    y = x * w
    return [E(x, y), E(x, y + x)]


results = {}
# every E(F_{2^19}) is cyclic: E = Z/n1 x Z/n2 with n1 | q - 1 = 2^19 - 1 (prime) and n1^2 | #E < q - 1
assert is_prime(q - 1)
for lab, (a2, b) in curves.items():
    E = EllipticCurve(K, [1, a2, 0, 0, b])
    Mg = int(E.cardinality())
    assert Mg % 4 == 0
    while True:
        G = E.random_point()
        if G.order() == Mg:
            break
    rec = {"group": "E0" if lab == "E0" else ("floor" if lab.startswith("F") else ("null" if lab.startswith("R") else "null_matched"))}
    for l in LS:
        pts = []
        for c in range(1 << l):
            x = K(sum(((c >> i) & 1) * z ** i for i in range(l)))
            for P in lift_points(E, K(a2), b, x):
                pts.append(P)
        logs = [int(P.log(G)) for P in pts]
        S = sumsets(logs, Mg, max(MS))
        Srand = sumsets(random_symmetric(len(logs), Mg), Mg, max(MS))
        rl = {"F_size": len(pts)}
        for m in MS:
            # y = |S_m| / #E over the whole (cyclic) group; for class curves also over the order-N subgroup
            yF = float(S[m].sum()) / Mg
            yR = float(Srand[m].sum()) / Mg
            rl["m%d" % m] = {"y_curve": yF, "y_randset": yR,
                             "heuristic": len(pts) ** m / (math.factorial(m) * Mg)}
            if Mg == CARD:
                rl["m%d" % m]["yN_curve"] = float(S[m][::4].sum()) / N
                rl["m%d" % m]["yN_randset"] = float(Srand[m][::4].sum()) / N
        rec["l%d" % l] = rl
    results[lab] = rec
    with open(OUT + "relprob_toy_percurve.jsonl", "a") as fh:
        fh.write(json.dumps({"label": lab, **rec}) + "\n")
    if len(results) % 25 == 0:
        print(len(results), "curves %.1fs" % (time.time() - t0), flush=True)

# summary
from scipy import stats
summary = {}
for l in LS:
    for m in MS:
        key = "l%d_m%d" % (l, m)
        ent = {}
        for g in ("E0", "floor", "null", "null_matched"):
            ratio = [r["l%d" % l]["m%d" % m]["y_curve"] / r["l%d" % l]["m%d" % m]["y_randset"]
                     for r in results.values() if r["group"] == g]
            yc = [r["l%d" % l]["m%d" % m]["y_curve"] for r in results.values() if r["group"] == g]
            ent[g] = {"count": len(ratio), "mean_ratio_to_randset": float(np.mean(ratio)),
                      "sd_ratio": float(np.std(ratio, ddof=1)) if len(ratio) > 1 else None,
                      "mean_y": float(np.mean(yc))}
        fr = [r["l%d" % l]["m%d" % m]["y_curve"] / r["l%d" % l]["m%d" % m]["y_randset"]
              for r in results.values() if r["group"] == "floor"]
        nr = [r["l%d" % l]["m%d" % m]["y_curve"] / r["l%d" % l]["m%d" % m]["y_randset"]
              for r in results.values() if r["group"] == "null"]
        mr = [r["l%d" % l]["m%d" % m]["y_curve"] / r["l%d" % l]["m%d" % m]["y_randset"]
              for r in results.values() if r["group"] == "null_matched"]
        ks = stats.ks_2samp(fr, nr)
        ent["ks2_floor_vs_null_ratio"] = {"D": float(ks.statistic), "p": float(ks.pvalue)}
        ks = stats.ks_2samp(fr, mr)
        ent["ks2_floor_vs_null_matched_ratio"] = {"D": float(ks.statistic), "p": float(ks.pvalue)}
        ent["E0_ratio_percentile_in_floor_plus_null"] = float(
            np.mean(np.array(fr + nr) <= ent["E0"]["mean_ratio_to_randset"]))
        summary[key] = ent
        print(key, json.dumps(ent), flush=True)

# E0 only: tau-orbit collapse of the union factor base  U_j F_{V^{2^j}}  (unknowns vs size)
tau_demo = {}
for l in LS:
    V = [K(sum(((c >> i) & 1) * z ** i for i in range(l))) for c in range(1 << l)]
    U = set()
    for x in V:
        y = x
        for j in range(n):
            U.add(y.to_integer())
            y = y * y
    for lab in ["E0", floor_keep[0], "R000"]:
        a2, b = curves[lab]
        E = EllipticCurve(K, [1, a2, 0, 0, b])
        lift = [u for u in U if u == 0 or ((K.from_integer(u) + b / K.from_integer(u) ** 2).trace() == 0)]
        npts = sum(1 if u == 0 else 2 for u in lift)
        # unknowns: points up to negation; for E0 additionally up to tau (x -> x^2 orbits)
        if lab == "E0":
            orbs = set()
            for u in lift:
                y = K.from_integer(u)
                orbs.add(min((y ** (2 ** j)).to_integer() for j in range(n)))
            unknowns = len(orbs)
        else:
            unknowns = len(lift)
        tau_demo["l%d_%s" % (l, lab)] = {"union_x_count": len(U), "union_points": npts,
                                         "unknowns_mod_neg_and_endos": unknowns}
print(json.dumps(tau_demo, indent=0))
json.dump({"info": info, "summary": summary, "tau_union_demo": tau_demo,
           "per_curve": {k: v for k, v in results.items()},
           "curves": {k: {"a2": a2, "b_int": int(b.to_integer())} for k, (a2, b) in curves.items()},
           "elapsed_s": time.time() - t0}, open(OUT + "relprob_toy.json", "w"), indent=0)
print("done %.1fs" % (time.time() - t0))
