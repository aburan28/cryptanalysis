# p-levels: arithmetic of the conductor-p and conductor-263p levels of the
# ECC2K-130 isogeny class. Run:  sage p_levels_numbers.sage
# Writes raw/p_levels_numbers.json and prints a log.
import json, time, os
T0 = time.time()
out = {}
def rec(k, v):
    out[k] = v
    print(k, "=", v)

# ---------------- constants, re-derived (not taken from ground truth) ----------------
q = 2^131
# Lucas recurrence for tau^2 + tau + 2 = 0 (t_1 = -1 since #E0(F_2) = 4 = 2+1-t_1)
t0, t1 = 2, -1
for k in range(1, 131):
    t0, t1 = t1, -t1 - 2*t0
t = t1
assert t == -22283658519494248867
N = (q + 1 - t) // 4
assert 4*N == q + 1 - t and ZZ(N).is_prime(proof=True)
D = t^2 - 4*q
assert D % 7 == 0
f2 = D // (-7); f = isqrt(f2); assert f*f == f2
assert f % 263 == 0
p = f // 263
assert ZZ(p).is_prime(proof=True) and is_prime(263)
assert factor(f) == factor(263) * factor(p)
rec("t", str(t)); rec("f", str(f)); rec("p", str(p)); rec("log2_p", float(log(p, 2)))

# Legendre symbols, two ways each
kp = kronecker(-7, p); e_p = power_mod(-7 % p, (p - 1)//2, p)
k263 = kronecker(-7, 263); e_263 = power_mod(-7 % 263, 131, 263)
assert (kp == 1 and e_p == 1) or (kp == -1 and e_p == p - 1)
assert (k263 == 1 and e_263 == 1)
rec("kronecker(-7,p)", int(kp)); rec("euler_criterion(-7,p)", "p-1" if e_p == p-1 else str(e_p))
rec("kronecker(-7,263)", int(k263))
# p mod 7 as a third check: (-7|p) = (p|7) by reciprocity for odd p
rec("p_mod_7", int(p % 7)); rec("(p|7)", int(kronecker(p, 7)))
assert kronecker(p, 7) == kp

# ---------------- (1) Frobenius on E0[p] ----------------
Fp = GF(p)
c = Fp(t) / 2
assert c^2 == Fp(q)                       # c is a (double) root of x^2 - t x + q mod p
R.<X> = Fp[]
assert X^2 - Fp(t)*X + Fp(q) == (X - c)^2
rec("c = t/2 mod p", int(c))
fac_pm1 = factor(p - 1)
rec("factor(p-1)", str(fac_pm1))
r = c.multiplicative_order()
# explicit certificate of the order
assert c^r == 1 and all(c^(r//l) != 1 for l, _ in factor(r))
rec("r = ord_p(c)", int(r)); rec("factor(r)", str(factor(r))); rec("log2_r", float(log(r, 2)))
rec("(p-1)/r", int((p - 1) // r))
half = (c^(r//2) == -1)
rec("c^(r/2) == -1", bool(half))
rx = r//2 if half else r
rec("r_x = min k with c^k = +-1 (degree of kernel x-coords over F_q)", int(rx))
rec("log2_r_x", float(log(rx, 2)))
rec("ord_p(2)", int(Fp(2).multiplicative_order()))
rec("ord_p(q)", int(Fp(q).multiplicative_order()))
rec("ord_p(-c) (twist)", int((-c).multiplicative_order()))

# ---------------- independent check via point counts of E0 over F_{q^k} ------------
# N_k = #E0(F_{q^k}) = q^k + 1 - t_k,  t_k = tr(M^k) with M the companion matrix of x^2 - t x + q.
def Nk_mod(k, m):
    M = matrix(Zmod(m), [[t, -q], [1, 0]])
    tk = (M^k).trace()
    return (Zmod(m)(q)^k + 1 - tk)
def Ntwist_mod(k, m):   # twist of E0 over F_q has Frobenius -pi
    M = matrix(Zmod(m), [[-t, -q], [1, 0]])
    tk = (M^k).trace()
    return (Zmod(m)(q)^k + 1 - tk)
p2 = p^2
chk = {}
chk["N_r mod p^2"] = int(Nk_mod(r, p2))
chk["N_(r/l) mod p for primes l|r"] = {str(l): int(Nk_mod(r//l, p)) for l, _ in factor(r)}
assert Nk_mod(r, p2) == 0
assert all(Nk_mod(r//l, p) != 0 for l, _ in factor(r))
# v_p(N_r) exactly 2?  (theory: N_k = (1-pi^k)(1-pibar^k); v_p can exceed 2 only if pi^r = 1 mod p^2 O_K)
chk["N_r mod p^3 == 0"] = bool(Nk_mod(r, p^3) == 0)
rt = (-c).multiplicative_order()
chk["twist: Ntw_(ord(-c)) mod p"] = int(Ntwist_mod(rt, p))
chk["twist: Ntw_(ord(-c)/l) mod p for l|ord(-c)"] = {str(l): int(Ntwist_mod(rt//l, p)) for l, _ in factor(rt)}
assert Ntwist_mod(rt, p) == 0 and all(Ntwist_mod(rt//l, p) != 0 for l, _ in factor(rt))
# brute scan: no k <= 2*10^6 with p | N_k (for either twist), by iterating the recurrence mod p
tk0, tk1 = Fp(2), Fp(t); qk = Fp(q); Q = Fp(q); first = None; first_tw = None
for k in range(1, 2*10^6 + 1):
    if first is None and qk + 1 - tk1 == 0: first = k
    sgn = 1 if k % 2 == 0 else -1
    if first_tw is None and qk + 1 - sgn*tk1 == 0: first_tw = k
    tk0, tk1 = tk1, Fp(t)*tk1 - Q*tk0
    qk *= Q
chk["first k<=2e6 with p | #E0(F_q^k)"] = first
chk["first k<=2e6 with p | #E0twist(F_q^k)"] = first_tw
assert first is None and first_tw is None
rec("pointcount_checks", chk)

# ---------------- class numbers of the orders ----------------
# h(O_f) = h(O_K) * f * prod_{l|f} (1 - (dK|l)/l) / [O_K^* : O_f^*];  h(O_K)=1, O_K^* = {+-1}
def h_formula(cond):
    h = QQ(cond)
    for l, _ in factor(cond):
        h *= (1 - QQ(kronecker(-7, l))/l)
    return ZZ(h)
hs = {"1": 1, "263": h_formula(263), "p": h_formula(p), "263p": h_formula(263*p)}
rec("h_formula", {k: str(v) for k, v in hs.items()})
assert hs["263"] == 262 and hs["p"] == p + 1 and hs["263p"] == 262*(p + 1)
tot = sum(hs.values())
rec("sum_h (number of F_q-classes with trace t)", str(tot)); rec("log2 sum_h", float(log(tot, 2)))
assert tot == 263*(p + 2)
rec("log2 h(O_p)", float(log(hs["p"], 2))); rec("log2 h(O_263p)", float(log(hs["263p"], 2)))
# PARI checks with binary quadratic forms: every prime form's order divides h; the class of
# the prime above 2 has order exactly 131 (=> sigma-orbits of size 131, 131 | h).
pari_chk = {}
for name, Dd, h in (("p", -7*p^2, hs["p"]), ("263p", -7*263^2*p^2, hs["263p"]), ("263", -7*263^2, 262)):
    one = pari(f"qfbpow(qfbprimeform({Dd},2),0)")
    g2 = pari(f"qfbprimeform({Dd},2)")
    o131 = pari(f"qfbred(qfbpow(qfbprimeform({Dd},2),131))") == pari(f"qfbred(qfbpow(qfbprimeform({Dd},2),0))")
    o1 = pari(f"qfbred(qfbprimeform({Dd},2))") == pari(f"qfbred(qfbpow(qfbprimeform({Dd},2),0))")
    # orders of prime forms for small split primes
    orders = []
    lcm_o = 1
    for l in prime_range(3, 400):
        if kronecker(Dd, l) != 1: continue
        ok = pari(f"qfbred(qfbpow(qfbprimeform({Dd},{l}),{h}))") == pari(f"qfbred(qfbpow(qfbprimeform({Dd},{l}),0))")
        assert ok, (name, l)
        # exact order
        o = h
        for ll, e in factor(h):
            while o % ll == 0 and pari(f"qfbred(qfbpow(qfbprimeform({Dd},{l}),{o//ll}))") == pari(f"qfbred(qfbpow(qfbprimeform({Dd},{l}),0))"):
                o //= ll
        orders.append((l, str(o)))
        lcm_o = lcm(lcm_o, o)
    pari_chk[name] = {"D": str(Dd), "h_formula": str(h), "ord(prime form above 2) == 131": bool(o131 and not o1),
                      "n_split_primes_checked(<400)": len(orders), "all prime-form orders divide h": True,
                      "lcm of prime-form orders": str(lcm_o), "lcm == h": bool(lcm_o == h),
                      "sample orders": orders[:8]}
    assert o131 and not o1
rec("pari_form_checks", pari_chk)
# direct PARI class number for the small ones (sanity) and attempt for D=-7p^2 (Shanks O(|D|^{1/4}))
rec("qfbclassno(-7)", int(pari("qfbclassno(-7)")))
rec("qfbclassno(-7*263^2)", int(pari("qfbclassno(-7*263^2)")))
t1_ = time.time()
try:
    hp = pari(f"qfbclassno({-7*p^2})")
    rec("qfbclassno(-7p^2)", str(hp)); rec("qfbclassno(-7p^2) time_s", round(time.time()-t1_, 1))
    assert ZZ(hp) == p + 1
except Exception as ex:
    rec("qfbclassno(-7p^2) error", str(ex))
assert (p + 1) % 131 == 0
rec("(p+1)/131 = sigma-orbits at level p", str((p + 1)//131))
rec("262(p+1)/131 = sigma-orbits at level 263p", str(262*(p + 1)//131))

# ---------------- minimal endomorphism degrees ----------------
# nonscalar elements of Z + g O_K (g = conductor) have norm >= 7 g^2 / 4
for g in (263, p, 263*p):
    rec(f"log2 min nonscalar endo degree, conductor {g}", float(log(7*g^2/4, 2)))

# ---------------- rho baselines ----------------
rhoE0 = sqrt(pi.n(200)*N/(4*131)); rho1 = sqrt(pi.n(200)*N/4)
rec("log2 rho E0 (neg+tau)", float(log(rhoE0, 2))); rec("log2 rho neg only", float(log(rho1, 2)))
rec("log2 speedup factor sqrt(131)", float(log(sqrt(131.0), 2)))

# ---------------- cost / size estimates for the transport ----------------
bits_ext_elt = 131 * rx
rec("bits per element of F_{q^{r_x}}", str(bits_ext_elt)); rec("bytes per element of F_{q^{r_x}}", float(bits_ext_elt/8))
rec("log2 bits per F_{q^{r_x}} element", float(log(bits_ext_elt, 2)))
rec("log2 bits of cofactor #E(F_{q^r})/p^2 (~131 r)", float(log(131*r, 2)))
kerdeg = (p - 1)//2
rec("kernel polynomial degree (p-1)/2", str(kerdeg)); rec("number of F_q-irreducible factors of kernel poly", int(kerdeg // rx))
rec("bytes to store kernel polynomial over F_q (131 bits/coeff)", float(kerdeg*131/8))
rec("log2 sqrt(p) (sqrt-Velu steps)", float(log(sqrt(p*1.0), 2)))
# lower bounds in F_q-multiplications, charging only r_x F_q-mults per F_{q^{r_x}} op (optimistic)
rec("log2 LB sqrtVelu cost in F_q ops (sqrt(p)*r_x)", float(log(sqrt(p*1.0)*rx, 2)))
rec("log2 LB cofactor scalar mult (131 r doublings * r F_q ops)", float(log(131.0*r*r, 2)))
rec("log2 Phi_p(1,Y) mod 2 size in bits (p+2 coeffs)", float(log(p + 2, 2)))
# random search for a curve of trace t at levels p / 263p among (b, a2 in {0,1})
rec("log2 Pr[random (b,a2) is level p]", float(log((p + 1)/(2*(q - 1)), 2)))
rec("log2 Pr[random (b,a2) is level p or 263p]", float(log(263*(p + 1)/(2*(q - 1)), 2)))
rec("log2 |D| for H_{-7p^2}", float(log(7*p^2, 2)))
rec("elapsed_s", round(time.time() - T0, 1))
os.makedirs("raw", exist_ok=True)
json.dump(out, open("raw/p_levels_numbers.json", "w"), indent=1, default=str)
print("ALL ASSERTIONS PASSED")
