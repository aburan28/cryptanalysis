# Positive / negative controls for the pairing-transfer methodology (toy sizes only).
#   export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; sage -python toy_mov_controls.py
# (a) supersingular y^2+y = x^3+x over F_(2^m) (m odd): the same embedding-degree routine must
#     report k <= 4, and a Frey-Rueck/MOV transfer must actually solve a toy ECDLP that we plant.
# (b) Koblitz curves y^2+xy = x^3+1 over F_(2^m), m prime in 101..163 with #E = 4*prime: the routine
#     must report a huge embedding degree (same phenomenon as ECC2K-130).
# (c) on the real twists E0' and A000' over F_q (263 | q-1, embedding degree 1 for the 263-part),
#     a toy DLP of order 263 that we plant is solved by the Tate pairing into mu_263 in F_q:
#     pairings DO work on the 263-part -- which is exactly the part that is useless for the ECDLP.
import json, sys, time
from pathlib import Path
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import (GF, EllipticCurve, Integer, factor, Mod, set_random_seed, randint,
                      discrete_log, is_prime, log)

HERE = Path(__file__).resolve().parent
set_random_seed(424242)
res = {"script": "toy_mov_controls.py"}


def emb_deg(n, qq):
    return Mod(qq, n).multiplicative_order()


# ---------------- (a) supersingular positive control ----------------
sup = []
for m in [31, 37, 41, 43, 47]:
    F = GF(2**m, "a")
    E = EllipticCurve(F, [0, 0, 1, 1, 0])
    c = E.cardinality()
    n = max(r for r, e in factor(c))
    k = emb_deg(n, 2**m)
    row = {"m": m, "#E": str(c), "n": str(n), "n_bits": int(n.nbits()), "k": int(k)}
    if n.nbits() >= 20 and k <= 4:
        # plant a toy ECDLP and solve it by MOV (Tate pairing into F_(2^(m k)))
        t0 = time.time()
        Fk = GF(2**(m * k), "b")
        emb = F.hom([F.modulus().change_ring(Fk).roots()[0][0]], Fk)
        Ek = EllipticCurve(Fk, [0, 0, 1, 1, 0])
        h = c // n
        while True:
            P = h * E.random_point()
            if not P.is_zero():
                break
        secret = randint(1, n - 1)
        Q = secret * P
        Pk = Ek(emb(P[0]), emb(P[1])); Qk = Ek(emb(Q[0]), emb(Q[1]))
        # find R in E(F_(q^k))[n] independent of P (full n-torsion is rational over F_(q^k))
        ck = E.cardinality(extension_degree=k)
        while True:
            R = (ck // n**(ck.valuation(n))) * Ek.random_point()
            while not (n * R).is_zero():
                R = n * R
            if R.is_zero():
                continue
            w = Pk.weil_pairing(R, n)
            if w != 1:
                break
        w1 = Pk.weil_pairing(R, n); w2 = Qk.weil_pairing(R, n)
        x = discrete_log(w2, w1, ord=n)
        row["mov_solved"] = bool(Integer(x) == secret)
        row["mov_seconds"] = round(time.time() - t0, 2)
        assert row["mov_solved"]
    sup.append(row)
    print("supersingular", row, flush=True)
res["a_supersingular_positive_control"] = sup
assert all(r["k"] <= 4 for r in sup)

# ---------------- (b) Koblitz negative control ----------------
kob = []
for m in range(101, 164):
    if not Integer(m).is_prime():
        continue
    F = GF(2**m, "a")
    E = EllipticCurve(F, [1, 0, 0, 0, 1])
    c = E.cardinality()
    if c % 4 == 0 and (c // 4).is_prime():
        n = c // 4
        k = emb_deg(n, 2**m)
        kob.append({"m": m, "n_bits": int(n.nbits()), "k_bits": int(k.nbits()),
                    "k_log2": round(float(log(k, 2).n(40)), 2), "k_is_(n-1)/" : str((n - 1) // k)})
        print("koblitz", kob[-1], flush=True)
res["b_koblitz_negative_control"] = kob

# ---------------- (c) 263-part of the real twists: pairing works, but only on the 263-part ----------------
K = ecc2k.field()
q = Integer(ecc2k.q); TW = Integer(ecc2k.TWIST_CARD)
ELL = Integer(263)
tw_rows = []
for lab in ["E0", "A000", "B000"]:
    b = ecc2k.dec(ecc2k.RECORDS[lab]["b_int"])
    Et = EllipticCurve(K, [1, 1, 0, 0, b])            # the quadratic twist over F_q
    h = TW // ELL**2
    # generator of the 263-part
    while True:
        T = h * Et.random_point()
        if not T.is_zero():
            break
    order_T = ELL**2 if not (ELL * T).is_zero() else ELL
    P = (order_T // ELL) * T                          # order 263
    secret = randint(1, 262)
    Q = secret * P
    # choose the second argument R with t(P,R) != 1
    while True:
        R = Et.random_point()
        tPR = P.tate_pairing(R, ELL, 1, q=q)               # k = 1: values in mu_263 subset F_q^*
        if tPR != 1:
            break
    tQR = Q.tate_pairing(R, ELL, 1, q=q)
    x = discrete_log(tQR, tPR, ord=ELL)
    row = {"curve_twist": lab + "'", "263_part_generator_order": str(order_T), "planted": int(secret),
           "recovered": int(x), "ok": bool(Integer(x) == secret)}
    assert row["ok"]
    tw_rows.append(row)
    print("twist-263", row, flush=True)
res["c_real_twist_263_part_k1"] = tw_rows
(HERE / "toy_mov_controls.json").write_text(json.dumps(res, indent=1))
print("wrote toy_mov_controls.json")
