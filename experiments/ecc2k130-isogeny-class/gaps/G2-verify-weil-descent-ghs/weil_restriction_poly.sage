# G2 item (9): Frobenius polynomial of Res_{F_q/F_2}(E), q = 2^131, for the class of E0.
#  - P(T) = T^2 + T + 2 (tau on E0/F_2);  t = alpha^131 + alphabar^131 by the Lucas recurrence,
#    cross-checked with PARI ellcard on E0/F_q;  P_131(T) = T^2 - t T + q.
#  - P_R(T) = P_131(T^131) (degree 262).  A = P_R / P, deg 260, A(1) = N, irreducible over Q.
#  - A computed a second way as the norm N_{Q(sqrt-7)/Q} of (T^131 - alpha^131)/(T - alpha).
#  - A_d := char poly of Frob^d on A (via Newton identities from power sums): irreducible for
#    d = 1..24 and a few larger d with 131 !| d; for d = 131 and 262, A_d = (T^2 - t_d T + 2^d)^130.
#  - Toy check of P_R(T) = P_E(T^n) against #Res(E)(F_{2^k}) = #E(F_{2^lcm(n,k)})^gcd(n,k), n = 5, 7.
# Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; timeout 2400 sage weil_restriction_poly.sage
import json, time, sys
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
OUT = "/Volumes/SSD990/ecdlp-hardness-work/gaps/G2-verify-weil-descent-ghs"
T0 = time.time()
set_random_seed(20260924)
res = {}
N = Integer(ecc2k.N); q = Integer(2)**131; t_gt = Integer(ecc2k.t)
R.<T> = ZZ[]
P = T^2 + T + 2

# Lucas sequence L_k = alpha^k + alphabar^k, alpha root of T^2 + T + 2:  L_{k+1} = -L_k - 2 L_{k-1}
def lucas(kmax, s1, pr):          # roots of T^2 - s1 T + pr
    L = [Integer(2), Integer(s1)]
    for k in range(2, kmax + 1):
        L.append(s1 * L[-1] - pr * L[-2])
    return L
Ltau = lucas(262 * 262, -1, 2)
t = Ltau[131]
res["t_from_lucas"] = str(t)
res["t_equals_ground_truth"] = (t == t_gt)
K = ecc2k.field()
E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
card_pari = Integer(pari(E0).ellcard())
res["E0_card_pari"] = str(card_pari)
res["card_equals_q+1-t"] = (card_pari == q + 1 - t)
res["card_equals_4N"] = (card_pari == 4 * N)
res["#E0(F_2)"] = int(pari(EllipticCurve(GF(2), [1, 0, 0, 0, 1])).ellcard())
res["P(1)"] = int(P(1))
P131 = T^2 - t * T + q
res["P_131(T)"] = str(P131)
PR = P131(T^131)
res["deg_P_R"] = int(PR.degree())
A, rem = PR.quo_rem(P)
res["P_divides_P_R"] = (rem == 0)
res["deg_A"] = int(A.degree())
res["P_R(1)"] = str(PR(1)); res["P_R(1)==4N"] = (PR(1) == 4 * N)
res["A(1)"] = str(A(1)); res["A(1)==N"] = (A(1) == N)
res["A(0)==2^130"] = (A(0) == 2**130)
res["A_leading_coeff"] = int(A.leading_coefficient())
t1 = time.time()
res["A_irreducible_pari_polisirreducible"] = bool(pari(A).polisirreducible())
res["A_irreducible_sage"] = bool(A.is_irreducible())
res["irreducibility_secs"] = round(time.time() - t1, 2)
res["gcd(A, P)"] = str(gcd(A, P))
# second route: A = N_{Q(sqrt-7)/Q}( sum_{i=0}^{130} T^i alpha^(130-i) )
K7.<al> = NumberField(P)
S7.<U> = K7[]
fa = sum(U^i * al^(130 - i) for i in range(131))
assert fa * (U - al) == U^131 - al^131
nf = fa * fa.map_coefficients(lambda c: c.galois_conjugate())
A2 = R([ZZ(c) for c in nf.list()])
res["A_norm_route_equals_A"] = (A2 == A)
# A_d via Newton identities; power sums of roots of A: p_k(A) = p_k(P_R) - p_k(P)
Lpi = lucas(600, t, q)                   # pi^j + pibar^j
def p_A(k):
    pr = 131 * Lpi[k // 131] if k % 131 == 0 else 0
    return pr - Ltau[k]
def char_poly_power(d, deg=260):
    ps = [None] + [p_A(d * k) for k in range(1, deg + 1)]
    e = [Integer(1)]
    for k in range(1, deg + 1):
        s = sum((-1)^(i - 1) * e[k - i] * ps[i] for i in range(1, k + 1))
        assert s % k == 0
        e.append(s // k)
    return R([(-1)^(deg - j) * e[deg - j] for j in range(deg + 1)])
Ad1 = char_poly_power(1)
res["A_d(d=1)_equals_A"] = (Ad1 == A)
irr = {}
t2 = time.time()
for d in list(range(1, 25)) + [65, 130]:
    Ad = char_poly_power(d)
    irr[str(d)] = bool(pari(Ad).polisirreducible())
res["A_d_irreducible"] = irr
res["A_d_irreducible_secs"] = round(time.time() - t2, 1)
split = {}
for d in (131, 262):
    Ad = char_poly_power(d)
    # trace of pi^(d/131) on E over F_q^(d/131)
    td = Lpi[d // 131]
    target = (T^2 - td * T + 2**d)^130
    split[str(d)] = {"A_d == (T^2 - t_d T + 2^d)^130": (Ad == target), "t_d": str(td)}
res["A_d_split"] = split
res["galois_argument"] = ("Roots of A are zeta^j*alpha, zeta^j*alphabar (zeta a primitive 131st root of 1, 1<=j<=130). "
    "Q(zeta_131) has unique quadratic subfield Q(sqrt(-131)) (131 = 3 mod 4), so Q(zeta_131, sqrt(-7)) has degree 260 and "
    "Galois group (Z/131)^* x Z/2; alpha/alphabar is not a root of unity ((alpha),(alphabar) are distinct primes over 2), "
    "so the 260 conjugates of (zeta*alpha)^d are distinct whenever 131 !| d: A_d irreducible, A simple over F_{2^d}. "
    "For 131 | d, A_d = (T^2 - t_d T + 2^d)^130: over F_q, Res(E) = prod_i E^(sigma^i) ~ E^131.")
# toy check of the Weil-restriction formula P_R(T) = P_E(T^n)
toy = []
for n in (5, 7):
    k.<g> = GF(2^n)
    for trial in range(3):
        while True:
            b = k.random_element()
            if b != 0:
                break
        E = EllipticCurve(k, [1, 0, 0, 0, b])
        cE = E.cardinality()
        tE = 2^n + 1 - cE
        PE = T^2 - tE * T + 2^n
        PRt = PE(T^n)
        rows = []
        ok = True
        for kk in range(1, 2 * n + 2):
            L = lcm(n, kk); G = gcd(n, kk)
            KL = GF(2^L, 'h')
            rt = k.modulus().change_ring(KL).roots()[0][0]
            emb = lambda c: sum(KL(int(cc)) * rt^i for i, cc in enumerate(c.polynomial().list()))
            EL = EllipticCurve(KL, [emb(c) for c in E.a_invariants()])
            direct = Integer(pari(EL).ellcard())^G          # direct PARI count over F_{2^lcm}
            # #R(F_{2^kk}) = prod over the 2n roots beta of P_R of (1 - beta^kk) = Res(P_R, T^kk - 1)
            val = PRt.resultant(T^kk - 1)
            rows.append((int(kk), int(direct), int(val)))
            ok = ok and (direct == val)
        toy.append({"n": int(n), "b": str(b), "t_E": int(tE), "all_k_match": ok, "k_range": [1, int(2 * n + 1)]})
res["toy_weil_restriction_formula"] = toy
res["elapsed_s"] = round(time.time() - T0, 1)
json.dump(res, open(OUT + "/weil_restriction_poly.json", "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
