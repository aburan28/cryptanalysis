"""Frobenius polynomial of the Weil restriction Res_{F_q/F_2}(E), q = 2^131, for any E in the
isogeny class (all have the same F_q-Frobenius polynomial P(T) = T^2 - t T + q).

Res_{K/k}(E) has k-Frobenius characteristic polynomial P(T^n) (n = [K:k] = 131).  We check:
  * P(T^131) = (T^2 + T + 2) * A(T) over Z, with T^2+T+2 the F_2-Frobenius polynomial of E0/F_2,
  * A(T) (degree 260) is irreducible over Q  =>  the complement A of E0/F_2 in Res(E) is F_2-simple,
  * A(1) = N, (T^2+T+2)(1) = 4: the whole order-N part of E(F_q) = Res(E)(F_2) lives in A(F_2).
Consequence: any F_2-curve C with a morphism of abelian varieties Res(E) -> J_C (or J_C -> Res(E))
that is non-zero on the N-part has A as an isogeny factor of J_C, so genus(C) >= 130.
Also prints illustrative L(1/2) costs.
Run: sage -python weil_restriction.py
"""
import sys, json, time, math
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import ZZ, PolynomialRing, pari, QQ

OUT = "/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs/"
t0 = time.time()
R = PolynomialRing(ZZ, "T"); T = R.gen()
t, q, N = ecc2k.t, ecc2k.q, ecc2k.N
P = T ** 2 - t * T + q
Pres = P(T ** 131)
E0F2 = T ** 2 + T + 2
Aq, rem = Pres.quo_rem(E0F2)
assert rem == 0
out = {"P_E(T)": str(P), "deg_Pres": Pres.degree(), "E0F2_divides": True,
       "deg_A": Aq.degree(), "A(1)": str(Aq(1)), "A(1)==N": Aq(1) == N,
       "Pres(1)==4N": Pres(1) == 4 * N, "E0F2(1)": int(E0F2(1))}
assert Aq(1) == N and Pres(1) == 4 * N
t1 = time.time()
irr = bool(pari(Aq).polisirreducible())
out["A_irreducible_over_Q_pari"] = irr
out["irreducibility_time_s"] = round(time.time() - t1, 1)
print(json.dumps(out, indent=1, default=str), flush=True)
assert irr
# also: full factorisation of Pres over Z (independent call)
t1 = time.time()
fac = Pres.factor()
out["Pres_factor_degrees"] = sorted(int(f.degree()) for f, e in fac)
out["Pres_factor_time_s"] = round(time.time() - t1, 1)
assert out["Pres_factor_degrees"] == [2, 260]


def L_half_log2(log2Q, c=math.sqrt(2)):
    lnQ = log2Q * math.log(2)
    return c * math.sqrt(lnQ * math.log(lnQ)) / math.log(2)


out["illustrative_L_half_sqrt2_log2_cost_o1_ignored"] = {
    "g=2^130 (GHS genus, floor curves)": L_half_log2(2.0 ** 130),
    "g=2^130-1 (min gGHS genus)": L_half_log2(2.0 ** 130 - 1),
    "g=2^128+1 (Hess Thm 2 lower bound, any Artin-Schreier construction)": L_half_log2(2.0 ** 128 + 1),
    "g=130 (abelian-variety lower bound, hypothetical cover)": L_half_log2(130.0),
}
out["hyperelliptic_model_size_bits_for_g=2^130"] = "about 2g+2 = 2^131+2 coefficients in F_2 (~2^131 bits = 2^128 bytes)"
out["elapsed_s"] = round(time.time() - t0, 1)
json.dump(out, open(OUT + "weil_restriction.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str))
