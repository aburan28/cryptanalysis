"""Rational-x density of factor-base subspaces for all 263 curves of the ECC2K-130
isogeny class (E0 + 262 conductor-263 floor curves) and a null of 263 random
ordinary curves y^2+xy = x^3+b over F_2^131 (a2 = 0, like every class member).

Run:  export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp
      sage -python density.py

For a curve y^2 + xy = x^3 + b (a2 = 0) and x != 0, x is the abscissa of an
F_q-point iff Tr(x + b/x^2) = 0; x = 0 always is (the point (0, sqrt b)).

Vectorisation: Tr(b * w) is F_2-bilinear, so with w_x = 1/x^2 and
L(w)_i = Tr(z^i w) (a Hankel matrix H[i][j] = Tr(z^(i+j)) applied to the bit
vector of w) we get Tr(x + b/x^2) = Tr(x) + <b, L(w_x)> mod 2.  One float32 BLAS
product (65536 x 131) @ (131 x 526) then decides every (x, curve) pair; sums are
<= 131 so float32 is exact.  Validation against Sage's own trace and lift_x is
done on random samples and on complete small counts (see validate()).

Subspaces (nested, V_k = span of the first k basis vectors, k = 1..16):
  canon : 1, z, ..., z^15 (the ECC2K-130 polynomial basis)
  rand1..rand3 : 16 random F_2-independent vectors, seeds 9001..9003
Outputs raw_counts.json with C[label][subspace][k] = #{x in V_k liftable} (incl. x=0).
"""
import sys, json, time, random, hashlib
import numpy as np

sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import pari, EllipticCurve

OUT = "/Volumes/SSD990/ecdlp-hardness-work/index-calculus/"
KMAX = 16
NB = 131
K = ecc2k.field()
z = K.gen()
t0 = time.time()
log = {}


def bits_of(v):
    """int -> uint8[131] little-endian bits"""
    return np.array([(v >> i) & 1 for i in range(NB)], dtype=np.uint8)


def ints_to_bits(vals):
    a = np.zeros((len(vals), NB), dtype=np.uint8)
    for r, v in enumerate(vals):
        # 131 bits -> 17 bytes little-endian then unpackbits(little)
        a[r] = np.unpackbits(np.frombuffer(int(v).to_bytes(17, "little"), dtype=np.uint8),
                             bitorder="little")[:NB]
    return a


# ---- trace data --------------------------------------------------------------
tr_pow = []           # Tr(z^e), e = 0..260
u = K(1)
for e in range(2 * NB - 1):
    tr_pow.append(int(u.trace()))
    u *= z
TM = sum(tr_pow[j] << j for j in range(NB))    # trace mask: Tr(x) = parity(x & TM)
H = np.array([[tr_pow[i + j] for j in range(NB)] for i in range(NB)], dtype=np.float32)
log["trace_mask_int"] = str(TM)
log["trace_mask_bits"] = [j for j in range(NB) if (TM >> j) & 1]
# sanity: Tr(1) = 131 mod 2 = 1
assert tr_pow[0] == 1


def par(v):
    return bin(v).count("1") & 1


# ---- subspaces ------------------------------------------------------------------
def gf2_rank(vs):
    rows = list(vs)
    rank = 0
    for bit in range(NB):
        piv = None
        for i in range(rank, len(rows)):
            if (rows[i] >> bit) & 1:
                piv = i
                break
        if piv is None:
            continue
        rows[rank], rows[piv] = rows[piv], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] >> bit) & 1:
                rows[i] ^= rows[rank]
        rank += 1
    return rank


SUBSPACES = {"canon": [1 << i for i in range(KMAX)]}
for r, seed in zip((1, 2, 3), (9001, 9002, 9003)):
    rng = random.Random(seed)
    while True:
        basis = [rng.getrandbits(NB) for _ in range(KMAX)]
        if gf2_rank(basis) == KMAX:
            break
    SUBSPACES["rand%d" % r] = basis
log["subspace_bases"] = {k: [str(v) for v in b] for k, b in SUBSPACES.items()}


def enumerate_space(basis):
    """x[c] = XOR_{i : bit i of c} basis[i], c = 0..2^16-1 (so V_k = rows < 2^k)."""
    xs = [0] * (1 << KMAX)
    for c in range(1, 1 << KMAX):
        low = (c & -c).bit_length() - 1
        xs[c] = xs[c & (c - 1)] ^ basis[low]
    return xs


# ---- curves ---------------------------------------------------------------------
labels = list(ecc2k.LABELS)
b_class = [int(ecc2k.RECORDS[l]["b_int"]) for l in labels]
assert all(int(ecc2k.RECORDS[l]["a2"]) == 0 for l in labels)

# null: 263 random b (a2 = 0), seeded; point-count each to prove not isogenous to E0
rng = random.Random(20260923)
null_b, null_orders = [], []
tp = time.time()
while len(null_b) < 263:
    b = rng.getrandbits(NB)
    if b in (0, 1):
        continue
    E = EllipticCurve(K, [1, 0, 0, 0, ecc2k.dec(b)])
    n = int(E.cardinality(algorithm="pari"))
    null_b.append(b)
    null_orders.append(n)
log["null_pointcount_seconds"] = time.time() - tp
null_labels = ["R%03d" % i for i in range(263)]
n_isog = sum(1 for n in null_orders if n == ecc2k.CARD)
n_twist = sum(1 for n in null_orders if n == ecc2k.TWIST_CARD)
log["null_order_eq_4N"] = n_isog
log["null_order_eq_twist"] = n_twist
log["null_order_mod4_all_zero"] = all(n % 4 == 0 for n in null_orders)
log["null_distinct_orders"] = len(set(null_orders))
assert n_isog == 0
null_info = {l: {"b_int": str(b), "order_pari": str(n)} for l, b, n in zip(null_labels, null_b, null_orders)}
print("null curves point-counted in %.1fs; #order=4N: %d, #order=q+1+t: %d"
      % (log["null_pointcount_seconds"], n_isog, n_twist), flush=True)

all_labels = labels + null_labels
all_b = b_class + null_b
Bbits = ints_to_bits(all_b).astype(np.float32)   # (526, 131)

counts = {l: {} for l in all_labels}
xs_store = {}
for sname, basis in SUBSPACES.items():
    ts = time.time()
    xs = enumerate_space(basis)
    xs_store[sname] = xs
    # w = 1/x^2
    ws = [0] * len(xs)
    for c in range(1, len(xs)):
        xv = ecc2k.dec(xs[c])
        ws[c] = ecc2k.enc(1 / (xv * xv))
    Wb = ints_to_bits(ws).astype(np.float32)        # (65536, 131)
    L = np.mod(Wb @ H, 2.0)                          # L(w)_i = sum_j w_j Tr(z^(i+j))
    S = np.mod(L @ Bbits.T, 2.0).astype(np.uint8)    # <b, L(w_x)> = Tr(b w_x)
    trx = np.array([par(x & TM) for x in xs], dtype=np.uint8)
    lift = ((S ^ trx[:, None]) == 0)
    lift[0, :] = True                                # x = 0
    cum = np.cumsum(lift, axis=0)
    for ci, l in enumerate(all_labels):
        counts[l][sname] = {str(k): int(cum[(1 << k) - 1, ci]) for k in range(1, KMAX + 1)}
    np.save(OUT + "raw/lift_%s.npy" % sname, np.packbits(lift, axis=0))
    print("subspace %s done in %.1fs" % (sname, time.time() - ts), flush=True)

# ---- validation against Sage directly -----------------------------------------
def direct_liftable(b, x):
    if x == 0:
        return True
    xv = ecc2k.dec(x)
    return (xv + ecc2k.dec(b) / (xv * xv)).trace() == 0


val = {}
vr = random.Random(77)
lifts = {s: np.unpackbits(np.load(OUT + "raw/lift_%s.npy" % s), axis=0)[: 1 << KMAX] for s in SUBSPACES}
mism = 0
NCHK = 4000
for _ in range(NCHK):
    s = vr.choice(list(SUBSPACES))
    ci = vr.randrange(len(all_labels))
    c = vr.randrange(1 << KMAX)
    if bool(lifts[s][c, ci]) != direct_liftable(all_b[ci], xs_store[s][c]):
        mism += 1
val["random_pairs_checked_trace"] = NCHK
val["random_pairs_mismatch_trace"] = mism
# lift_x check on a subset (independent of the trace criterion; Sage lift_x ~0.3 s/call here)
mism2 = 0
NCHK2 = 150
for _ in range(NCHK2):
    s = vr.choice(list(SUBSPACES))
    ci = vr.randrange(len(all_labels))
    c = vr.randrange(1, 1 << KMAX)
    E = EllipticCurve(K, [1, 0, 0, 0, ecc2k.dec(all_b[ci])])
    has = len(E.lift_x(ecc2k.dec(xs_store[s][c]), all=True)) > 0
    if bool(lifts[s][c, ci]) != has:
        mism2 += 1
val["random_pairs_checked_lift_x"] = NCHK2
val["random_pairs_mismatch_lift_x"] = mism2
# full recount of k = 10 with Sage's own trace (no Hankel matrix, no BLAS) for 14 curves x 4 subspaces
full = []
for l in ["E0", "A000", "A001", "A090", "A130", "B000", "B021", "B067", "B095", "B130", "R000", "R001", "R131", "R262"]:
    ci = all_labels.index(l)
    for s in SUBSPACES:
        cnt = sum(1 for c in range(1024) if direct_liftable(all_b[ci], xs_store[s][c]))
        full.append({"curve": l, "subspace": s, "k": 10, "direct_trace_count": cnt,
                     "vectorised_count": counts[l][s]["10"], "match": cnt == counts[l][s]["10"]})
val["full_k10_recount"] = full
# Codex run-03 fingerprints (factor_base_x_count, polynomial basis), copied from
# ground_truth/build_log.json step codex_run03_fingerprints
bl = json.load(open("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/build_log.json"))
fp = [s for s in bl["steps"] if s["step"] == "codex_run03_fingerprints"][0]["rows"]
val["codex_run03"] = [{"curve": r["curve"], "k": r["k"], "codex": r["codex_x_count"],
                       "ours_incl_x0": counts[r["curve"]]["canon"][str(r["k"])],
                       "ours_excl_x0": counts[r["curve"]]["canon"][str(r["k"])] - 1} for r in fp]
print(json.dumps(val, indent=1), flush=True)
assert mism == 0 and mism2 == 0 and all(r["match"] for r in full)

log["validation"] = val
log["elapsed_s"] = time.time() - t0
json.dump({"meta": {"KMAX": KMAX, "subspaces": list(SUBSPACES), "count_definition":
                    "C = #{x in V_k : x = 0 or Tr(x + b/x^2) = 0}; density d = C/2^k",
                    "class_labels": labels, "null_labels": null_labels},
           "log": log, "null_curves": null_info, "counts": counts},
          open(OUT + "raw_counts.json", "w"), indent=0)
print("done %.1fs" % (time.time() - t0))
