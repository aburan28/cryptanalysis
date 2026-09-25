# bigfield41v2.sage ROLE SEED NINST -- (checkpointed, one level-1721 curve per process; ROLE A also does the
# E0 rank-2 check, the rank-1 check on its E1 and the E0 instances)  "large conductor prime" test on a second toy, n = 41 (mirror of the p-level of ECC2K-130).
#
#   E0: y^2 + xy = x^3 + 1 over F_q, q = 2^41 = F_2[z]/(z^41+z^3+1)  (Koblitz, a2 = 0, like ECC2K-130's E0)
#   #E0(F_q) = 4 * N41, N41 = 549756390943 (prime, 39.0 bits)
#   t^2 - 4q = -7 f^2, f = 409 * 1721, both primes INERT in Q(sqrt(-7))  (ECC2K-130's p is inert too)
#   P = 1721: lambda = t/2 mod P has order k = 215 = (P-1)/8  (ECC2K-130: k_p = (p-1)/12)
#   => E0[1721] and the ascending kernel of every level-1721 curve live over F_{q^215} = F_{2^8815}.
#   rho costs: sqrt(pi N/4) = 2^19.2 (negation), sqrt(pi N/(4*41)) = 2^16.5 (tau+negation); P = 2^10.75.
#   (ECC2K-130: 2^64.33, 2^60.81, p = 2^57.02 -- similar ratios P/rho.)
# Steps: build F_{2^8815} (PARI ffgen) and an explicit embedding F_q -> F_{2^8815}; construct level-1721 curves by
# descending 1721-isogenies from E0 (Velu over F_{2^8815}); compute the ascending kernel of each; transport planted
# DLP instances back to E0; time every step.  Output: ../raw/bigfield41.json, ../raw/nb_tables41.txt,
# ../raw/instances41.txt (input lines for toyrho41).
import json, time, sys
ROLE = sys.argv[1]; SEED = int(sys.argv[2]); NINST = int(sys.argv[3])
def _dflt(o):
    try: return int(o)
    except Exception:
        try: return float(o)
        except Exception: return str(o)
set_random_seed(SEED)
pari.allocatemem(2*10^9)
OUT = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/'
T0 = time.time()
LOG = []; TIM = {}
CK = OUT + 'bigfield41_%s.json' % ROLE
def checkpoint(**extra):
    json.dump(dict(role=ROLE, seed=SEED, timings=TIM, log=LOG, **extra), open(CK, 'w'), indent=0, default=_dflt)
def chk(name, cond, info=None):
    LOG.append(dict(check=name, ok=bool(cond), info=info, t=round(time.time()-T0, 2)))
    print(('OK   ' if cond else 'FAIL ') + name + ('' if info is None else '  ' + str(info)), flush=True)
    assert cond, name

n = 41; q = 2^n; P = 1721
RZ.<Z> = GF(2)[]
F.<z> = GF(2^n, modulus=Z^41+Z^3+1)
def I(u): return int(u.to_integer())
def Fi(i): return F.from_integer(int(i))
def lucas(m, t1, qq=2):
    a, b = 2, t1
    for i in range(m-1): a, b = b, t1*b - qq*a
    return b if m >= 1 else a
t = lucas(n, -1); card = q + 1 - t
N41 = 549756390943
chk('#E0(F_q) = 4*N41 (Lucas), N41 prime', card == 4*N41 and ZZ(N41).is_prime(proof=True), dict(t=int(t)))
E0 = EllipticCurve(F, [1, 0, 0, 0, 1])
chk('PARI ellcard(E0) = 4*N41', E0.cardinality(algorithm='pari') == card)
f = isqrt((t*t - 4*q)//(-7)); chk('f = 409*1721, both inert', f == 409*1721 and kronecker(-7, 409) == -1 and kronecker(-7, 1721) == -1)
lam = Mod(t, P)/2; k = lam.multiplicative_order()
chk('k = ord_1721(t/2) = 215 = (P-1)/8', k == 215)

def halftrace(c, m):
    h = c; u = c
    for i in range((m-1)//2):
        u = u^4; h += u
    return h
def rpoint(E):
    a2 = E.a2(); b = E.a6()
    while True:
        x = F.random_element()
        if x == 0: continue
        c = x + a2 + b/x^2
        if c.trace() != 0: continue
        Pt = E(x, x*halftrace(c, n))
        return Pt if randint(0, 1) else -Pt
cof = card // N41
def rand_order_N(E):
    while True:
        Q = cof*rpoint(E)
        if not Q.is_zero():
            assert (N41*Q).is_zero(); return Q
G0 = rand_order_N(E0)
s_roots = [int(r) for r in PolynomialRing(GF(N41), 'x')('x^2 + x + 2').roots(multiplicities=False)]
s41 = [r for r in s_roots if r*G0 == E0(G0[0]^2, G0[1]^2)]
chk('tau acts on <G> as s (root of s^2+s+2 mod N41), ord 41', len(s41) == 1 and Mod(s41[0], N41).multiplicative_order() == 41, s41)
s41 = s41[0]

# normal-basis tables for toyrho41
while True:
    beta = F.random_element(); conj = [beta]
    for i in range(1, n): conj.append(conj[-1]^2)
    M = matrix(GF(2), [[(I(c) >> bit) & 1 for bit in range(n)] for c in conj])
    if M.is_invertible(): break
Minv = M.inverse()
def rowint(r): return sum(int(r[i]) << i for i in range(n))
with open(OUT + 'nb_tables41_%s.txt' % ROLE, 'w') as fo:
    for i in range(n): fo.write(hex(rowint(Minv.row(i))) + '\n')
    for i in range(n): fo.write(hex(rowint(M.row(i))) + '\n')

# ---- the big field F_{q^215} = F_{2^8815} and an explicit embedding of F_q --------------------------------
t1 = time.time()
KBIG = n*k
Lg = pari('ffgen(2^%d, \'b)' % KBIG)
topol = pari('(x)->Vecrev(lift(x.pol), %d)' % KBIG)
def bits(e): return [int(c) for c in topol(e)]
ONE = Lg^0; ZERO = 0*Lg
def frob_q(e):                 # e -> e^(2^41)
    for i in range(n): e = e^2
    return e
def reltrace(r):
    acc = r; u = r
    for j in range(1, k):
        u = frob_q(u); acc = acc + u
    return acc
gamma = reltrace(pari.random(Lg))
while gamma == ZERO or gamma == ONE: gamma = reltrace(pari.random(Lg))
chk('gamma = Tr_{L/F_q}(r) lies in the subfield (gamma^(2^41) = gamma)', frob_q(gamma) == gamma)
gp = [ONE]
for i in range(n): gp.append(gp[-1]*gamma)
Mg = matrix(GF(2), [bits(e) for e in gp])
ker = Mg.left_kernel()
mvec = ker.basis()[0]
mg = RZ(list(mvec))
chk('minimal polynomial of gamma over F_2 has degree 41 and is irreducible', mg.degree() == 41 and mg.is_irreducible())
FF.<y> = GF(2^n, modulus=mg)
rho_ = (Z^41+Z^3+1).change_ring(FF).roots(multiplicities=False)[0]
rc = rho_.polynomial().list()
alpha = ZERO
for i, c in enumerate(rc):
    if c: alpha = alpha + gp[i]
chk('alpha = rho(gamma) is a root of z^41+z^3+1 in F_{2^8815}', alpha^41 + alpha^3 + 1 == ZERO)
ap = [ONE]
for i in range(1, n): ap.append(ap[-1]*alpha)
def emb(u):                     # F_q -> L
    v = I(u); acc = ZERO
    for i in range(n):
        if (v >> i) & 1: acc = acc + ap[i]
    return acc
A = matrix(GF(2), [bits(e) for e in ap]).transpose()        # 8815 x 41
piv = A.transpose().pivots()
B = A.matrix_from_rows(piv); Binv = B.inverse()
def unemb(e):                   # subfield element of L -> F_q (checked)
    bv = bits(e)
    c = Binv * vector(GF(2), [bv[r] for r in piv])
    u = F.from_integer(sum(int(c[i]) << i for i in range(n)))
    assert emb(u) == e, 'element not in the subfield'
    return u
uu = F.random_element(); vv = F.random_element()
chk('embedding is a ring homomorphism (random test) and unemb inverts it', emb(uu*vv) == emb(uu)*emb(vv) and emb(uu+vv) == emb(uu)+emb(vv) and unemb(emb(uu)) == uu)
TIM['build_big_field_and_embedding'] = time.time() - t1

# ---- E0 over L: #E0(L), the 1721-torsion (full rank: pi acts as the scalar lambda) --------------------------
tL = lucas(KBIG, -1)
cardL = 2^KBIG + 1 - tL
v1721 = valuation(cardL, P)
chk('v_1721(#E0(F_{2^8815})) >= 2', v1721 >= 2, dict(v=int(v1721)))
cofL = cardL // P^v1721
E0L = pari.ellinit(pari([1, 0, 0, 0, 1])*ONE, Lg)
def order_P_point(EL):
    """random point of E(L), times the prime-to-P cofactor, then reduced to exact order P"""
    while True:
        R = pari.random(EL)
        Q = pari.ellmul(EL, R, cofL)
        if Q == pari([0]): continue
        while True:
            Q2 = pari.ellmul(EL, Q, P)
            if Q2 == pari([0]): return Q
            Q = Q2
def kernel_x(EL, K):
    xs = []; Q = K
    for i in range((P-1)//2):
        xs.append(Q[0]); Q = pari.elladd(EL, Q, K)
    return xs
if ROLE == 'A':
    t1 = time.time(); R = pari.random(E0L)
    chk('#E0(L) (Lucas) annihilates a random point of E0(L)', pari.ellmul(E0L, R, cardL) == pari([0]))
    TIM['E0L_order_check_one_scalar_mult'] = time.time() - t1
t1 = time.time()
Pa = order_P_point(E0L); TIM['E0_find_order_1721_point'] = time.time() - t1
t1 = time.time(); xa = kernel_x(E0L, Pa); TIM['E0_kernel_860_additions'] = time.time() - t1
if ROLE == 'A':
    Pb = order_P_point(E0L)
    chk('E0(L)[1721] has rank 2 (second random order-1721 point not in <Pa>)', not any(Pb[0] == x for x in xa))
TIM['log2_cofactor_scalar'] = float(RR(log(cofL, 2)))
checkpoint()

# ---- level-1721 curves: E1 = E0/<K> for 3 kernels -----------------------------------------------------------
kernels = {'E1'+ROLE: Pa}
level_curves = {}
for name, K in kernels.items():
    t1 = time.time()
    xs = xa
    v = sum(xs[1:], xs[0])
    b1L = 1 + v + v^2
    b1 = unemb(b1L)
    TIM['descend_%s_velu' % name] = time.time() - t1
    E1 = EllipticCurve(F, [1, 0, 0, 0, b1])
    level_curves[name] = dict(b=b1, E=E1)
    chk('%s: codomain of E0 -> E0/<K> is defined over F_q, j = 1/b not in F_2' % name, b1 != 0 and b1 != 1, hex(I(b1)))
    chk('%s: #E1(F_q) = #E0(F_q) (PARI SEA)' % name, E1.cardinality(algorithm='pari') == card)
TIM['descend_total_find_point_plus_velu'] = TIM['E0_find_order_1721_point'] + TIM['E0_kernel_860_additions'] + TIM['descend_E1%s_velu' % ROLE]
checkpoint(level_curve_b=hex(I(level_curves['E1'+ROLE]['b'])))

# ---- ascending kernel on E1 (rank-1 1721-torsion over L), codomain must be E0 ------------------------------
asc = {}
for name in kernels:
    b1 = level_curves[name]['b']; b1L = emb(b1)
    E1L = pari.ellinit(pari([1, 0, 0, 0, 0])*ONE + pari([0, 0, 0, 0, 1])*b1L, Lg)
    t1 = time.time(); K1 = order_P_point(E1L); ta = time.time() - t1
    t1 = time.time(); xs1 = kernel_x(E1L, K1); tb = time.time() - t1
    v1 = sum(xs1[1:], xs1[0])
    if ROLE == 'A':
        K1b = order_P_point(E1L)
        chk('%s: E1(L)[1721] is cyclic (a second random order-1721 point lies in <K1>): not on the crater' % name, any(K1b[0] == x for x in xs1))
    chk('%s: Velu of <K1> lands exactly on E0 = [1,0,0,0,1]  (b1 + v + v^2 = 1)' % name, b1L + v1 + v1^2 == ONE)
    asc[name] = dict(xs=xs1, t_find_point=ta, t_860_additions=tb)
    TIM['ascend_%s_find_order_1721_point' % name] = ta; TIM['ascend_%s_860_additions' % name] = tb
    checkpoint(level_curve_b=hex(I(level_curves['E1'+ROLE]['b'])))

def transport(name, Pt):
    """x-only image under the ascending 1721-isogeny E1 -> E0 via Velu sums over the kernel (in L), Y by half-trace"""
    xs = asc[name]['xs']
    x = emb(Pt[0]); num = ZERO; den = ONE
    for xq in xs:
        d2 = (x + xq)^2
        num = num*d2 + xq*den; den = den*d2
    XL = x + x*num/den
    X = unemb(XL)
    c = X + 1/X^2
    assert c.trace() == 0
    Y = X*halftrace(c, n)
    return E0(X, Y)

# ---- planted DLP instances on the level-1721 curves; transport; checks ---------------------------------------
counts = {'E1'+ROLE: NINST}
inst = []; tev = []
for name, cnt in counts.items():
    E1 = level_curves[name]['E']
    for r in range(cnt):
        G = rand_order_N(E1); kk = ZZ.random_element(1, N41); H = kk*G
        t1 = time.time(); Gt = transport(name, G); Ht = transport(name, H); te = time.time() - t1
        tev.append(te)
        ok = (N41*Gt).is_zero() and not Gt.is_zero() and (Ht == kk*Gt or Ht == -kk*Gt)
        assert ok, (name, r)
        inst.append(dict(curve=name, idx=r, k=int(kk), b=hex(I(E1.a6())), Gx=hex(I(G[0])), Gy=hex(I(G[1])), Hx=hex(I(H[0])), Hy=hex(I(H[1])),
                         tGx=hex(I(Gt[0])), tGy=hex(I(Gt[1])), tHx=hex(I(Ht[0])), tHy=hex(I(Ht[1])), sign=(1 if Ht == kk*Gt else -1), t_eval_two_points=te))
        if r % 10 == 9: checkpoint(level_curve_b=hex(I(level_curves['E1'+ROLE]['b'])), instances=inst)
chk('all %d transported instances satisfy phi(H) = +-k phi(G) on E0 with phi(G) of order N41' % len(inst), True)
TIM['transport_eval_two_points_median'] = sorted(tev)[len(tev)//2]
TIM['log2_cofactor_scalar'] = float(RR(log(cofL, 2)))
inst_E0 = []
for r in range(60 if ROLE == 'A' else 0):
    G = rand_order_N(E0); kk = ZZ.random_element(1, N41); H = kk*G
    inst_E0.append(dict(curve='E0', idx=r, k=int(kk), Gx=hex(I(G[0])), Gy=hex(I(G[1])), Hx=hex(I(H[0])), Hy=hex(I(H[1]))))
# input lines for toyrho41
with open(OUT + 'instances41_%s.txt' % ROLE, 'w') as fo:
    for x in inst:
        iid = '%s_%d' % (x['curve'], x['idx'])
        fo.write('R L41i_%s 0 0x0 %s %d %d %s %s %s %s 16 8 %d\n' % (iid, x['b'], N41, s41, x['Gx'], x['Gy'], x['Hx'], x['Hy'], 1000 + len(iid) + x['idx']))
        fo.write('R L41iii_%s 1 0x0 0x1 %d %d %s %s %s %s 8 5 %d\n' % (iid, N41, s41, x['tGx'], x['tGy'], x['tHx'], x['tHy'], 2000 + x['idx']))
    for x in inst_E0:
        fo.write('R L41ii_E0_%d 1 0x0 0x1 %d %d %s %s %s %s 8 5 %d\n' % (x['idx'], N41, s41, x['Gx'], x['Gy'], x['Hx'], x['Hy'], 3000 + x['idx']))
meta = dict(n=n, modulus='z^41+z^3+1', t=int(t), card=int(card), N=N41, s=s41, f='409*1721', P=P, k=int(k), big_field_degree=KBIG,
            big_modulus=str(pari('(x)->x.mod')(Lg)).replace(' ', '')[:200] + '...', v1721_cardL=int(v1721),
            level_curves={nm: dict(b_int=str(I(level_curves[nm]['b'])), j_int=str(I(1/level_curves[nm]['b']))) for nm in level_curves}, role=ROLE, seed=SEED,
            log2_rho_neg=float(RR(log(sqrt(pi*N41/4), 2))), log2_rho_tau=float(RR(log(sqrt(pi*N41/(4*n)), 2))))
checkpoint(meta=meta, instances=inst, instances_E0=inst_E0, complete=True)
print(json.dumps(TIM, indent=1, default=_dflt))
print('done in %.1f s' % (time.time() - T0))
