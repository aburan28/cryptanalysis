"""Confirmatory replication of the one anomaly found (26 floor cells with |z|>3 vs 14.3 expected,
MC p = 0.005, exceedance_mc.json): recompute the rational-x counts of all 263 class curves and of
both nulls on 12 NEW random nested subspaces (seeds 9101..9112, fixed before looking), k = 8..16,
and count |z|>3 cells at k in {8,10,12,14,16}, plus KS / dispersion per group.
Pre-declared test: floor exceedance count vs the Monte-Carlo of the exact nested-binomial model
(p < 0.01 would confirm heavier tails on the floor; otherwise the first result was a fluctuation).
Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; sage -python replicate.py"""
import sys, json, time, random, math
import numpy as np
from scipy import stats
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
OUT = "/Volumes/SSD990/ecdlp-hardness-work/index-calculus/"
NB, KMAX = 131, 16
K = ecc2k.field()
z = K.gen()
t0 = time.time()
raw = json.load(open(OUT + "raw_counts.json"))
raw2 = json.load(open(OUT + "raw_counts_null2.json"))
TM = int(raw["log"]["trace_mask_int"])
labels = list(ecc2k.LABELS) + raw["meta"]["null_labels"] + raw2["meta"]["labels"]
bvals = [int(ecc2k.RECORDS[l]["b_int"]) for l in ecc2k.LABELS] + \
        [int(raw["null_curves"][l]["b_int"]) for l in raw["meta"]["null_labels"]] + \
        [int(raw2["null_curves"][l]["b_int"]) for l in raw2["meta"]["labels"]]


def par(v):
    return bin(v).count("1") & 1


def ints_to_bits(vals):
    a = np.zeros((len(vals), NB), dtype=np.uint8)
    for r, v in enumerate(vals):
        a[r] = np.unpackbits(np.frombuffer(int(v).to_bytes(17, "little"), dtype=np.uint8), bitorder="little")[:NB]
    return a


def gf2_rank(vs):
    rows, rank = list(vs), 0
    for bit in range(NB):
        piv = next((i for i in range(rank, len(rows)) if (rows[i] >> bit) & 1), None)
        if piv is None:
            continue
        rows[rank], rows[piv] = rows[piv], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] >> bit) & 1:
                rows[i] ^= rows[rank]
        rank += 1
    return rank


tr_pow = []
u = K(1)
for e in range(2 * NB - 1):
    tr_pow.append(int(u.trace()))
    u *= z
H = np.array([[tr_pow[i + j] for j in range(NB)] for i in range(NB)], dtype=np.float32)
Bbits = ints_to_bits(bvals).astype(np.float32)
KS = [8, 10, 12, 14, 16]
Z = {}   # label -> subspace -> k -> z
bases = {}
for seed in range(9101, 9113):
    rng = random.Random(seed)
    while True:
        basis = [rng.getrandbits(NB) for _ in range(KMAX)]
        if gf2_rank(basis) == KMAX and gf2_rank(basis + [1]) == KMAX + 1:   # 1 not in V_16
            break
    s = "r%d" % seed
    bases[s] = [str(v) for v in basis]
    xs = [0] * (1 << KMAX)
    for c in range(1, 1 << KMAX):
        low = (c & -c).bit_length() - 1
        xs[c] = xs[c & (c - 1)] ^ basis[low]
    ws = [0] + [ecc2k.enc(1 / (ecc2k.dec(x) ** 2)) for x in xs[1:]]
    L = np.mod(ints_to_bits(ws).astype(np.float32) @ H, 2.0)
    S = np.mod(L @ Bbits.T, 2.0).astype(np.uint8)
    trx = np.array([par(x & TM) for x in xs], dtype=np.uint8)
    lift = ((S ^ trx[:, None]) == 0)
    lift[0, :] = True
    cum = np.cumsum(lift, axis=0)
    vr = random.Random(seed)
    for _ in range(100):   # spot checks against Sage's trace
        ci, c = vr.randrange(len(labels)), vr.randrange(1, 1 << KMAX)
        xv = ecc2k.dec(xs[c])
        assert bool(lift[c, ci]) == ((xv + ecc2k.dec(bvals[ci]) / (xv * xv)).trace() == 0)
    for ci, l in enumerate(labels):
        Z.setdefault(l, {})[s] = {}
        for k in KS:
            n = (1 << k) - 1
            Z[l][s][k] = ((int(cum[(1 << k) - 1, ci]) - 1) - n / 2) / math.sqrt(n / 4)
    print(s, "done %.1fs" % (time.time() - t0), flush=True)

SUBS = list(bases)
groups = {"floor": [l for l in ecc2k.LABELS if l != "E0"], "null1": raw["meta"]["null_labels"],
          "null2": raw2["meta"]["labels"]}
res = {"subspace_seeds": list(range(9101, 9113)), "bases": bases}
# MC of the exceedance count for 262 curves x 12 subspaces (all random: coins 2^k - 1, nested)
mc = []
rngm = np.random.default_rng(123)
for r in range(3000):
    X = np.zeros(262 * 12)
    prev = 0
    cnt = 0
    for k in range(1, 17):
        coins = (1 << k) - 1
        X = X + rngm.binomial(coins - prev, 0.5, size=X.shape)
        prev = coins
        if k in KS:
            cnt += int((np.abs((X - coins / 2) / math.sqrt(coins / 4)) > 3).sum())
    mc.append(cnt)
mc = np.array(mc)
for g, L in groups.items():
    zs = {k: [Z[l][s][k] for l in L for s in SUBS] for k in KS}
    exceed = [(l, s, k) for l in L for s in SUBS for k in KS if abs(Z[l][s][k]) > 3]
    scale = 262 / len(L)
    ent = {"n_cells_per_k": len(zs[8]), "n_exceed": len(exceed), "exceed_cells": exceed,
           "mc_mean_for_262_curves": float(mc.mean()),
           "mean_z": {k: float(np.mean(zs[k])) for k in KS}, "sd_z": {k: float(np.std(zs[k], ddof=1)) for k in KS},
           "chi2_disp_p": {k: float(2 * min(stats.chi2.cdf(np.sum(np.square(zs[k])), len(zs[k])),
                                             stats.chi2.sf(np.sum(np.square(zs[k])), len(zs[k])))) for k in KS},
           "ks_norm_p": {k: float(stats.kstest(zs[k], "norm").pvalue) for k in KS}}
    if len(L) == 262:
        ent["mc_p_ge_obs"] = float((1 + (mc >= len(exceed)).sum()) / (1 + len(mc)))
    else:
        ent["expected_exceed_for_this_size"] = float(mc.mean() * len(L) / 262)
        ent["poisson_p_ge_obs_approx"] = float(stats.poisson.sf(len(exceed) - 1, mc.mean() * len(L) / 262))
    res[g] = ent
    print(g, "exceed", len(exceed), "MC mean(262 curves) %.1f" % mc.mean(), ent.get("mc_p_ge_obs", ent.get("poisson_p_ge_obs_approx")),
          "sd", {k: round(v, 3) for k, v in ent["sd_z"].items()}, "chi2p", {k: round(v, 3) for k, v in ent["chi2_disp_p"].items()})
res["E0_z"] = {s: Z["E0"][s] for s in SUBS}
res["elapsed_s"] = time.time() - t0
json.dump(res, open(OUT + "replicate.json", "w"), indent=1)
print("done %.1fs" % (time.time() - t0))
