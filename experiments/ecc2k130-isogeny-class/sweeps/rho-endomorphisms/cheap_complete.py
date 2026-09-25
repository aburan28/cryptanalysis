"""(3) Complete search over ALL endomorphisms of the floor curves with small separable degree.
Every endomorphism alpha of a floor curve factors as alpha = beta o Frob^e (e >= 0 inseparable exponent), i.e.
alpha = tau^e * mu' in O_K with tau not dividing mu'.  Writing mu' = taubar^b * mu (Verschiebung part b) the
eigenvalue on the N-subgroup is  ev(alpha) = lambda^e * (2/lambda)^b * ev(mu)  = 2^b * lambda^(e-b) * ev(mu),
and alpha in O_263 fixes (e - b) mod 131 through the image of mu in O_K/263 = F_263 x F_263
(tau -> (123,139)):  (123/139)^(e-b) = mu2/mu1.  (If mu in 263*O_K every e is allowed: 'sandwich' maps.)
Since tau^131 = pi acts trivially on E(F_q), only (e-b) mod 131 matters for the eigenvalue.
We enumerate every mu in O_K with Norm(mu) <= 2^LOGM, every b in [0, 130] and both signs, i.e. every endomorphism
with separable degree 2^b * Norm(mu) (any inseparable degree), and test whether the eigenvalue has order < 2^20.
Usage: python3 cheap_complete.py LOGM NPROC  -> cheap_complete_<LOGM>.json
"""
import sys, json, math, time, os
import numpy as np
from multiprocessing import Pool
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms")
import common_rho as C

N, LAM = C.N, C.LAM
LOGM, NPROC = int(sys.argv[1]), int(sys.argv[2])
M = 1 << LOGM
BMAX = 130
NPZ = "S_order_lt_2^20.npz"
MASK = (1 << 64) - 1
# F_263 data
r0 = 123 * pow(139, -1, 263) % 263
DLOG = {}
z = 1
for e in range(131):
    DLOG[z] = e
    z = z * r0 % 263
assert len(DLOG) == 131
LAMPOW = [pow(LAM, e, N) for e in range(131)]
POW2 = [pow(2, b, N) for b in range(BMAX + 1)]
_S = None


def init():
    global _S, _LO, _SET
    dat = np.load(NPZ)
    _LO = np.sort(dat["lo"])
    _SET = None


def check_vals(vals, tags):
    """vals: list of ints mod N; return indices whose value's low 64 bits are in S (then verify exactly)"""
    lo = np.array([v & MASK for v in vals], dtype=np.uint64)
    pos = np.searchsorted(_LO, lo)
    pos[pos >= len(_LO)] = len(_LO) - 1
    return [i for i in np.nonzero(_LO[pos] == lo)[0]]


def work(yr):
    y0, y1 = yr
    hits, n_mu, n_eig, n_sandwich = [], 0, 0, 0
    triv = [0]
    D = 7
    for y in range(y0, y1):
        disc = 4 * M - D * y * y
        if disc < 0:
            continue
        s = math.isqrt(disc)
        for x in range(-((y + s) // 2), (s - y) // 2 + 1):
            if x == 0 and y == 0:
                continue
            n_mu += 1
            m1, m2 = (x + 124 * y) % 263, (x + 140 * y) % 263     # omega = tau + 1 -> (124, 140)
            evmu = (x + y * C.W_OK) % N
            if m1 == 0 and m2 == 0:
                es = range(131); n_sandwich += 1
            elif m1 == 0 or m2 == 0:
                continue
            else:
                rho = m2 * pow(m1, -1, 263) % 263
                if rho not in DLOG:
                    continue
                es = [DLOG[rho]]
            for e in es:
                g = LAMPOW[e] * evmu % N
                vals = []
                for b in range(BMAX + 1):
                    v = g * POW2[b] % N
                    vals.append(v); vals.append(N - v)
                n_eig += len(vals)
                for i in check_vals(vals, None):
                    v = vals[i]
                    o = C.order_mod_N(v)
                    i = int(i)
                    if 2 < o < 2 ** 20:
                        hits.append((x, y, e, i // 2, 1 - 2 * (i % 2), o))
                    elif o <= 2:
                        triv[0] += 1
    return hits, n_mu, n_eig, n_sandwich, triv[0]


if __name__ == "__main__":
    t0 = time.time()
    if not os.path.exists(NPZ):
        from cvp_lib import elements_by_order
        S = [h for d, h in elements_by_order(N, C.NM1_FACT, 2 ** 20)]
        np.savez(NPZ, lo=np.array([h & MASK for h in S], dtype=np.uint64))
    # sanity: membership test catches the known small-order elements lambda^k (order 131)
    init()
    assert check_vals([LAM, (N - LAM) % N, 12345], None)[:2] == [0, 1]
    ymax = math.isqrt(4 * M // 7) + 1
    step = max(1, (2 * ymax + 1) // (NPROC * 20) + 1)
    ranges = [(a, min(a + step, ymax + 1)) for a in range(-ymax, ymax + 1, step)]
    allh, nmu, neig, nsw, ntriv = [], 0, 0, 0, 0
    with Pool(NPROC, initializer=init) as pool:
        for h_, a_, b_, c_, d_ in pool.imap_unordered(work, ranges):
            allh += h_; nmu += a_; neig += b_; nsw += c_; ntriv += d_
    out = {"log2_M_norm_mu_bound": LOGM, "b_max_verschiebung": BMAX, "num_mu_enumerated": nmu,
           "num_mu_in_263OK_sandwich": nsw, "num_eigenvalues_tested": neig, "num_trivial_eigenvalue_pm1": ntriv,
           "hits_order_lt_2^20": [dict(x=x, y=y, e=e, b=b, sign=sg, order=o) for x, y, e, b, sg, o in allh],
           "seconds": round(time.time() - t0, 1)}
    json.dump(out, open("cheap_complete_%d.json" % LOGM, "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "hits_order_lt_2^20"}), "hits:", len(allh))
    print("hits sample:", out["hits_order_lt_2^20"][:10])
