"""Matched null + the Tr(b) observation.

Every class curve has #E = 4N, N odd, so E(F_q)[2^inf] = Z/4 (no point of order 8).  For
y^2+xy = x^3+b (a2 = 0) the order-4 points have x = b^(1/4), and they halve (=> order-8
points exist) iff Tr(b^(1/4)) = Tr(b) = 0.  Hence all 263 class curves have Tr(b) = 1, and
then x = 1 is always liftable (Tr(1 + b) = Tr(1) + Tr(b) = 1 + 1 = 0; n = 131 odd => Tr(1) = 1).
The canonical subspace contains x = 1, so its count carries a deterministic +1 for every class
curve versus a uniform-b null (a z-shift of 1/sqrt(2^k - 1)).  The first null (R000..R262,
density.py) has Tr(b) uniform.  This script builds a MATCHED null: 263 random b with Tr(b) = 1
(=> #E = 4 mod 8), point-counted with PARI to confirm #E = 4 mod 8 and #E != 4N, and
recomputes the counts with the same subspaces/pipeline as density.py.
Also records Tr(b) and #E mod 8 for the class and the first null.
Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; sage -python density_null2.py
"""
import sys, json, time, random
import numpy as np
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import EllipticCurve

OUT = "/Volumes/SSD990/ecdlp-hardness-work/index-calculus/"
NB, KMAX = 131, 16
K = ecc2k.field()
z = K.gen()
t0 = time.time()
raw = json.load(open(OUT + "raw_counts.json"))
SUB = {s: [int(v) for v in raw["log"]["subspace_bases"][s]] for s in raw["meta"]["subspaces"]}
TM = int(raw["log"]["trace_mask_int"])


def par(v):
    return bin(v).count("1") & 1


def ints_to_bits(vals):
    a = np.zeros((len(vals), NB), dtype=np.uint8)
    for r, v in enumerate(vals):
        a[r] = np.unpackbits(np.frombuffer(int(v).to_bytes(17, "little"), dtype=np.uint8), bitorder="little")[:NB]
    return a


tr_pow = []
u = K(1)
for e in range(2 * NB - 1):
    tr_pow.append(int(u.trace()))
    u *= z
H = np.array([[tr_pow[i + j] for j in range(NB)] for i in range(NB)], dtype=np.float32)
assert TM == sum(tr_pow[j] << j for j in range(NB))

obs = {}
cls_tr = {l: par(int(ecc2k.RECORDS[l]["b_int"]) & TM) for l in ecc2k.LABELS}
obs["class_Tr_b_values"] = sorted(set(cls_tr.values()))
obs["class_card_mod8"] = ecc2k.CARD % 8
n1 = raw["null_curves"]
obs["null1_Tr_b_counts"] = {str(v): sum(1 for r in n1.values() if par(int(r["b_int"]) & TM) == v) for v in (0, 1)}
obs["null1_Tr_b_vs_order_mod8"] = sorted(set((par(int(r["b_int"]) & TM), int(r["order_pari"]) % 8) for r in n1.values()))
print(obs, flush=True)

rng = random.Random(20260924)
bs, orders = [], []
while len(bs) < 263:
    b = rng.getrandbits(NB)
    if b in (0, 1) or par(b & TM) != 1:
        continue
    n = int(EllipticCurve(K, [1, 0, 0, 0, ecc2k.dec(b)]).cardinality(algorithm="pari"))
    assert n % 8 == 4, (b, n % 8)          # Tr(b) = 1  =>  #E = 4 mod 8
    if n in (ecc2k.CARD, ecc2k.TWIST_CARD):
        continue
    bs.append(b)
    orders.append(n)
labels = ["S%03d" % i for i in range(263)]
obs["null2_all_order_4_mod_8"] = all(n % 8 == 4 for n in orders)
obs["null2_order_eq_4N"] = sum(1 for n in orders if n == ecc2k.CARD)
Bbits = ints_to_bits(bs).astype(np.float32)
counts = {l: {} for l in labels}
for s, basis in SUB.items():
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
    for ci, l in enumerate(labels):
        counts[l][s] = {str(k): int(cum[(1 << k) - 1, ci]) for k in range(1, KMAX + 1)}
    # spot-check 300 pairs directly
    vr = random.Random(5)
    for _ in range(300):
        ci, c = vr.randrange(263), vr.randrange(1, 1 << KMAX)
        xv = ecc2k.dec(xs[c])
        assert bool(lift[c, ci]) == ((xv + ecc2k.dec(bs[ci]) / (xv * xv)).trace() == 0)
    print(s, "done %.1fs" % (time.time() - t0), flush=True)
obs["spot_checks_per_subspace"] = 300
json.dump({"meta": {"labels": labels, "definition": "random b with Tr(b)=1 (#E = 4 mod 8), a2 = 0"},
           "observations": obs, "null_curves": {l: {"b_int": str(b), "order_pari": str(n)}
                                                for l, b, n in zip(labels, bs, orders)},
           "counts": counts, "elapsed_s": time.time() - t0},
          open(OUT + "raw_counts_null2.json", "w"), indent=0)
print(json.dumps(obs), "done %.1fs" % (time.time() - t0))
