# Number-theoretic part of the endomorphism-ring certification (items 1-algebra, 4, 5).
# Independent of the curve data: only q = 2^131 and #E0(F_2) = 4 are inputs.
from sage.all import *
import json, time, sys
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
out = {}
def rec(k, v):
    out[k] = v; print(k, "=", v, flush=True)

q = 2**131
# --- tau^2 - t1 tau + 2 with t1 = 2+1-#E0(F_2) = -1 ; brute-force #E0(F_2)
F2 = GF(2)
cnt = 1 + sum(1 for x in F2 for y in F2 if y*y + x*y == x**3 + 1)
rec("E0_F2_count_bruteforce", int(cnt))
t1 = 2 + 1 - cnt
assert t1 == -1
# tau in O_K: disc(x^2+x+2) = 1-8 = -7 = d_K  => Z[tau] = O_K
rec("disc_tau_minpoly", int(t1**2 - 4*2))
K = QuadraticField(-7, 'r'); r = K.gen()
tau = (t1 + r)/2               # a root of x^2 + x + 2 (sign choice irrelevant)
assert tau**2 + tau + 2 == 0
OK = K.maximal_order()
rec("Z[tau]_is_maximal_order", bool(K.order(tau) == OK))
rec("h(O_K)_sage", int(K.class_number()))
rec("units_O_K", [str(u) for u in [1, -1]] if K.unit_group().order() == 2 else "unexpected")
rec("unit_group_order_O_K", int(K.unit_group().order()))

# --- tau^k = a_k + b_k tau ;  tau^{k+1} = -2 b_k + (a_k - b_k) tau
a, b = [1], [0]
for k in range(1, 132):
    a.append(-2*b[-1]); b.append(a[-2] - b[-1])
pi_a, pi_b = a[131], b[131]
t = 2*pi_a + t1*pi_b          # trace(a + b tau) = 2a + b*trace(tau) = 2a - b
rec("trace_pi_from_tau131", int(t))
assert t == ecc2k.t
rec("pi = tau^131 = a + b*tau, (a,b)", [int(pi_a), int(pi_b)])
f = abs(pi_b)                 # conductor of Z[pi] in O_K = Z[tau] is |b|
rec("conductor_Z[pi]_=|b_131|", int(f))
assert f == ecc2k.f and t*t - 4*q == -7*f*f
rec("factor_f", str(factor(f)))
p = Integer(ecc2k.p)
assert f == 263*p

# item 5: tau^k in O_263 = Z + 263 O_K  <=>  263 | b_k
bad = [k for k in range(1, 131) if b[k] % 263 == 0]
rec("k in 1..130 with tau^k in O_263 (263|b_k)", bad)
rec("263 | b_131", bool(b[131] % 263 == 0))
badp = [k for k in range(1, 131) if b[k] % p == 0]
rec("k in 1..130 with tau^k in O_p (p|b_k)", badp)
rec("p | b_131", bool(b[131] % p == 0))
# order of tau's image in (O_K/263)^*/(Z/263)^*: 263 splits, O_K/263 = F_263 x F_263,
# tau -> (u1,u2) roots of x^2+x+2 mod 263; quotient by scalars ~ u1/u2 in F_263^*
Fl = GF(263); X = polygen(Fl)
roots = sorted(int(z) for z, _ in (X**2 + X + 2).roots())
rec("roots_x^2+x+2_mod_263", roots)
u1, u2 = Fl(roots[0]), Fl(roots[1])
rec("order_of_u1/u2_in_F263^*", int((u1/u2).multiplicative_order()))
rec("(O_K/263)^*/(Z/263)^* order (=263-1 since split)", 262)
# also mod p
Fp = GF(p); Xp = polygen(Fp)
rp = [z for z, _ in (Xp**2 + Xp + 2).roots()]
rec("kronecker(-7,p)", int(kronecker(-7, p)))
rec("x^2+x+2 roots mod p count", len(rp))
if len(rp) == 2:
    rec("order_of_tau_image_in_(O_K/p)^*/(Z/p)^*", int((rp[0]/rp[1]).multiplicative_order()))
else:
    # p inert: O_K/p = F_{p^2}; (F_{p^2})^*/F_p^* is cyclic of order p+1; tau -> root T of x^2+x+2
    Fp2 = GF(p**2, 'T', modulus=Xp**2 + Xp + 2); T = Fp2.gen()
    # image of tau modulo scalars <-> T^(p-1) (kills F_p^*), an element of the norm-1 group of order p+1
    u = T**(p-1)
    fac1 = factor(p + 1)
    rec("factor(p+1)", str(fac1))
    o = p + 1
    for ell, e in fac1:
        for _ in range(e):
            if u**(o//ell) == 1: o //= ell
            else: break
    rec("order_of_tau_image_in_(O_K/p)^*/(Z/p)^* (p inert, group cyclic of order p+1)", int(o))

# item 4: primality of p (three ways) + Pratt/Lucas certificate
rec("p", int(p)); rec("log2(p)", float(log(p, 2)))
rec("p_is_prime_proof_True", bool(p.is_prime(proof=True)))
rec("p_pari_isprime_APRCL(flag=2)", bool(pari(p).isprime(2)))
fac = factor(p - 1)
rec("factor(p-1)", str(fac))
assert all(Integer(ell).is_prime(proof=True) for ell, _ in fac)
g = next(g for g in range(2, 1000)
         if power_mod(g, p-1, p) == 1 and all(power_mod(g, (p-1)//ell, p) != 1 for ell, _ in fac))
rec("Lucas_witness_g (g^(p-1)=1, g^((p-1)/l)!=1 for all l|p-1)", int(g))
rec("263_prime", bool(is_prime(263)))
rec("kronecker(-7,263)", int(kronecker(-7, 263)))
rec("p mod 7", int(p % 7))

# class numbers of the four orders O_c = Z + c O_K, c | f
kp = kronecker(-7, p)
def h_formula(c):
    # h(O_c) = h(O_K) c / [O_K^*:O_c^*] prod_{l|c} (1 - (d_K/l)/l); here h(O_K)=1, unit index=1
    val = QQ(c)
    for ell, _ in factor(c):
        val *= (1 - QQ(kronecker(-7, ell))/ell)
    return ZZ(val)
res = {}
for name, c in [("1", 1), ("263", 263), ("p", p), ("263p", 263*p)]:
    D = -7*c*c
    entry = {"c": str(c), "D": str(D), "unit_index": 1, "h_formula": str(h_formula(c)) if c > 1 else "1"}
    t0 = time.time()
    qcu = pari(D).quadclassunit()
    entry["pari_quadclassunit_h(GRH)"] = str(qcu[0]); entry["pari_quadclassunit_cyc"] = str(qcu[1])
    entry["quadclassunit_time_s"] = round(time.time()-t0, 2)
    if abs(D) < 10**12:
        entry["pari_qfbclassno"] = str(pari(D).qfbclassno())
    # Sage's order class number for the order of conductor c (maximal order when c=1)
    try:
        O = K.order(c*tau) if c > 1 else OK
        entry["O_c_contains_pi"] = bool(pi_a + pi_b*tau in O)
        entry["unit_group_O_c"] = "{+1,-1}"   # O_K^* = {+-1} so every suborder has the same units
    except Exception as e:
        entry["sage_order_err"] = str(e)
    res[name] = entry
    print(name, entry, flush=True)
rec("class_numbers", res)
tot = sum(ZZ(res[k]["h_formula"]) for k in res)
rec("sum_h = total F_q-iso classes with trace t", str(tot))
rec("sum_h == 263*(p - kronecker(-7,p) + 1)", bool(tot == 263*(p - kp + 1)))
rec("log2 h(O_p), log2 h(O_263p)", [float(log(ZZ(res["p"]["h_formula"]), 2)), float(log(ZZ(res["263p"]["h_formula"]), 2))])
# item: min degree of a non-scalar endomorphism in O_263 = Z + 263 O_K:
# N(x + y*tau) = x^2 - x*y + 2*y^2 (tau^2 = -tau - 2, tr(tau) = -1)
def normxy(x, y): return x*x - x*y + 2*y*y
best = min((normxy(x, 263*y), x, y) for y in range(1, 3) for x in range(-600, 601))
rec("min_norm_nonscalar_in_O_263 (x+263y*tau, y!=0)", [int(v) for v in best])
best_OK = min((normxy(x, y), x, y) for y in range(1, 3) for x in range(-10, 11))
rec("min_norm_nonscalar_in_O_K", [int(v) for v in best_OK])
# E0 tau eigenvalue order on the N-subgroup
s = Integer(ecc2k.TAU_EIGEN); N = Integer(ecc2k.N)
rec("tau_eigen_order_mod_N", int(Mod(s, N).multiplicative_order()))
json.dump(out, open("/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/algebra_output.json", "w"), indent=1, default=str)
