# setup_toy.sage -- build the toy analogue of the ECC2K-130 359-volcano over F_{2^179}.
#
# Toy:  n = 179 (prime),  E0: y^2 + x y = x^3 + x^2 + 1  (Koblitz, a2 = 1, #E0(F_2) = 2, tau^2 - tau + 2 = 0)
#       #E0(F_q) = 2 * N * N2,  N = 60239283133 (35.81 bits, the DLP subgroup), N2 = 142-bit prime
#       t^2 - 4q = -7 f^2, f = 359 * P, P = 513035439254495356843057 (78.76 bits)
#       l = 359 = 2*179 + 1 splits in Q(sqrt(-7)); floor of the 359-volcano = 358 curves = 2 Frobenius orbits of 179
#       (exact structural analogue of 263 = 2*131 + 1 for ECC2K-130).
# Everything is re-verified here; the script stops on the first failed assertion.
# Output: ../raw/toy_ground_truth.json (curves, kernels, planted DLP instances), ../raw/nb_tables.json (normal basis).
import json, time, hashlib, sys
set_random_seed(20260923)
OUT = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/'
T0 = time.time()
LOG = []
def chk(name, cond, info=None):
    LOG.append(dict(check=name, ok=bool(cond), info=info, t=round(time.time()-T0, 2)))
    print(('OK   ' if cond else 'FAIL ') + name + ('' if info is None else '  ' + str(info)), flush=True)
    assert cond, name

n = 179; q = 2^n; L = 359
RZ.<Z> = GF(2)[]
modpoly = Z^179 + Z^4 + Z^2 + Z + 1
chk('modulus irreducible', modpoly.is_irreducible(), str(modpoly))
K.<z> = GF(2^n, modulus=modpoly)
def I(u): return int(u.to_integer())
def F(i): return K.from_integer(int(i))

# ---- E0 and its order ------------------------------------------------------------------------------
t1 = 1                           # a2 = 1: #E(F_2) = 2 = 2 + 1 - t1
tt = [2, t1]
for i in range(2, n+1): tt.append(t1*tt[-1] - 2*tt[-2])
t = tt[n]; card = q + 1 - t; twist_card = q + 1 + t
E0 = EllipticCurve(K, [1, 1, 0, 0, 1])
chk('#E0(F_2) = 2', EllipticCurve(GF(2), [1,1,0,0,1]).cardinality() == 2)
chk('PARI ellcard(E0) = q+1-t (Lucas)', E0.cardinality(algorithm='pari') == card, int(t))
N = 60239283133; N2 = 6360033939490742289168980201322563070730747
chk('#E0 = 2*N*N2', card == 2*N*N2)
chk('N prime (proof)', ZZ(N).is_prime(proof=True), float(RR(log(N,2))))
chk('N2 prime (proof)', ZZ(N2).is_prime(proof=True))
D = t^2 - 4*q
chk('t^2-4q = -7 f^2', D % 7 == 0 and (-D//7).is_square())
f = isqrt(-D//7); P_big = 513035439254495356843057
chk('f = 359 * P', f == L * P_big, int(f))
chk('P prime (proof)', ZZ(P_big).is_prime(proof=True), float(RR(log(P_big, 2))))
chk('kronecker(-7,359) = +1 (split)', kronecker(-7, L) == 1)
chk('kronecker(-7,P) = +1 (split)', kronecker(-7, P_big) == 1)
chk('h(-7*359^2) = 358', pari('qfbclassno(%d)' % (-7*L^2)) == 358)
chk('ord_359(2) = 179', Mod(2, L).multiplicative_order() == 179)
lam = Mod(t, L)/2
chk('pi acts on E0[359] as -1 (so E0[359] lives over F_{q^2}, twist has it over F_q)', lam == -1)
chk('v_359(#E0) = 0, v_359(#twist) = 2', card % L != 0 and twist_card % L^2 == 0 and twist_card % L^3 != 0)
lamP = Mod(t, P_big)/2
kP = lamP.multiplicative_order()
chk('k_P = ord_P(t/2) (extension degree of E0[P])', True, dict(kP=int(kP), log2_kP=float(RR(log(kP, 2)))))

# ---- tau eigenvalue on the N-subgroup --------------------------------------------------------------
cof = card // N
def rand_order_N(E, cofac):
    while True:
        Q = cofac * E.random_point()
        if not Q.is_zero():
            assert (N*Q).is_zero()
            return Q
G0 = rand_order_N(E0, cof)
roots = [int(r) for r in PolynomialRing(GF(N), 'x')('x^2 - x + 2').roots(multiplicities=False)]
tauG = E0(G0[0]^2, G0[1]^2)
s = [r for r in roots if r*G0 == tauG]
chk('tau acts on <G> as a root s of s^2 - s + 2 mod N', len(s) == 1, s)
s = s[0]
chk('ord_N(s) = 179', Mod(s, N).multiplicative_order() == 179)

# ---- floor curves, method 1: Velu from the twist E0'[359] = (Z/359)^2 over F_q ---------------------
E0t = EllipticCurve(K, [1, 0, 0, 0, 1])
chk('#E0twist = q+1+t', E0t.cardinality(algorithm='pari') == twist_card)
cof359 = twist_card // L^2
def rand_359(E):
    while True:
        Q = cof359 * E.random_point()
        if not Q.is_zero():
            return Q
P1 = rand_359(E0t); P2 = rand_359(E0t)
chk('P1,P2 have order 359', (L*P1).is_zero() and (L*P2).is_zero())
xs1 = set(); Q = P1
for i in range(1, L): xs1.add(I(Q[0])); Q += P1
chk('P2 not in <P1>  => E0twist[359] = (Z/359)^2 over F_q', I(P2[0]) not in xs1)
def halfkernel_x(Kp):
    xs = []; Q = Kp
    for i in range(1, (L-1)//2 + 1):
        xs.append(Q[0]); Q += Kp
    return xs
gens = [P1] + [P2 + i*P1 for i in range(L)]
kern = []
for g in gens:
    xs = halfkernel_x(g); v = sum(xs)
    bprime = 1 + v + v^2          # Velu codomain of [1,0,0,0,1] in the model [1,0,0,0,b'] (see report)
    kern.append(dict(v=v, b=bprime))
jvals = [1/k['b'] for k in kern]
horiz = [i for i, j in enumerate(jvals) if j == 1]
chk('exactly 2 of 360 kernels are horizontal (j=1)', len(horiz) == 2, horiz)
# the horizontal kernels are the tau-eigenlines
tau_ok = []
for i in horiz:
    g = gens[i]; tg = E0t(g[0]^2, g[1]^2)
    tau_ok.append(any(c*g == tg for c in range(1, L)))
chk('horizontal kernels are tau-eigenlines', all(tau_ok))
floor_b_velu = sorted(set(I(kern[i]['b']) for i in range(len(kern)) if i not in horiz))
chk('358 distinct floor b = 1/j from Velu', len(floor_b_velu) == 358)
# Sage cross-check of the hand Velu formula on 5 kernels
for i in [0, 1, 7, 100, 358]:
    phi = E0t.isogeny(gens[i])
    chk('hand Velu j == Sage isogeny j (kernel %d)' % i, phi.codomain().j_invariant() == jvals[i])

# ---- floor curves, method 2: roots of H_D mod 2, D = -7*359^2 --------------------------------------
Dring = -7*L^2
HD = pari('polclass(%d)' % Dring)
HZ = PolynomialRing(ZZ, 'Y')([ZZ(c) for c in HD.Vecrev()])
chk('deg H_D = 358', HZ.degree() == 358, dict(max_coeff_bits=int(max(abs(c) for c in HZ.coefficients()).nbits())))
H2 = HZ.change_ring(GF(2))
fac = H2.factor()
chk('H_D mod 2 = two distinct irreducible degree-179 factors', len(fac) == 2 and all(e == 1 and g.degree() == 179 for g, e in fac))
KY.<Y> = K[]
orbits = {}
for name, (g, e) in zip(['A', 'B'], fac):
    rts = sorted([I(r) for r in KY(g.change_ring(K)).roots(multiplicities=False)])
    assert len(rts) == 179
    j0 = F(rts[0])
    orb = [j0]
    for k in range(1, 179): orb.append(orb[-1]^2)
    chk('orbit %s: 179 distinct roots = Frobenius orbit of the smallest root' % name, sorted(I(u) for u in orb) == rts)
    orbits[name] = orb
floor_b_HD = sorted(I(1/j) for nm in 'AB' for j in orbits[nm])
chk('Velu floor set == H_D mod 2 root set (358/358)', floor_b_velu == floor_b_HD)
chk('no floor j in {0,1}', all(j != 0 and j != 1 for nm in 'AB' for j in orbits[nm]))

# ---- per floor curve: order, twist, a2, transport kernel (ascending 359-isogeny to E0) ---------------
curves = []
card_fact = [(2, 1), (N, 1), (N2, 1)]
tstart = time.time()
n_pari = 0
for nm in 'AB':
    for k, j in enumerate(orbits[nm]):
        lab = '%s%03d' % (nm, k)
        b = 1/j
        E = EllipticCurve(K, [1, 1, 0, 0, b])      # a2 = 1 twist (same class as E0 over F_q)
        # order proof: a point of order divisible by N*N2 => #E = 2*N*N2 (only multiple of N*N2 in Hasse interval)
        R = E.random_point()
        ok_order = (card*R).is_zero() and not ((2*N2)*R).is_zero() and not ((2*N)*R).is_zero()
        c_pari = E.cardinality(algorithm='pari') if k % 10 == 0 else None
        if c_pari is not None: n_pari += 1
        # ascending kernel: E'(F_q)[359], E' = [1,0,0,0,b] (x-coordinates of the kernel are twist invariant)
        Et = EllipticCurve(K, [1, 0, 0, 0, b])
        # a random point of the Sylow-359 subgroup has order 359^2 with prob. 1-1/359 when it is cyclic of order 359^2;
        # retry up to 30 times (an element of order 359^2 proves the Sylow-359 is cyclic, since |Sylow| = 359^2)
        for attempt in range(30):
            R1 = cof359 * Et.random_point()
            R359 = L*R1
            if not R359.is_zero(): break
        cyclic = not R359.is_zero()
        Kg = R359
        assert (L*Kg).is_zero() and not Kg.is_zero()
        xs = halfkernel_x(Kg)
        v = sum(xs)
        psi = prod(Y - u for u in xs)
        up_ok = (b + v + v^2 == 1)        # codomain [1,1,0,0,b+v+v^2] == E0 exactly
        curves.append(dict(label=lab, orbit=nm, frob_index=k, j_int=str(I(j)), b_int=str(I(b)), a2=1,
                           order_point_proof=bool(ok_order), order_pari=(str(c_pari) if c_pari else None),
                           twist_sylow359_cyclic=bool(cyclic), ascending_codomain_is_E0=bool(up_ok),
                           psi_coeffs_hex=[hex(I(c)) for c in psi.list()], v_int=str(I(v))))
        assert ok_order and up_ok and cyclic and (c_pari is None or c_pari == card), lab
chk('all 358 floor curves: #E = 2*N*N2 by point-order proof', all(c['order_point_proof'] for c in curves))
chk('PARI ellcard = 2*N*N2 on %d sampled floor curves (every 10th in each orbit)' % n_pari, True)
chk('all 358: twist Sylow-359 cyclic of order 359^2 (not on the crater)', all(c['twist_sylow359_cyclic'] for c in curves))
chk('all 358: Velu of the unique rational 359-subgroup lands exactly on E0=[1,1,0,0,1]', all(c['ascending_codomain_is_E0'] for c in curves), round(time.time()-tstart, 1))

# Sage cross-check of the x-only transport formula X = x + x u + (x u)^2, u = psi'(x)/psi(x)
def transport_x(c, x):
    psi = KY([F(int(h, 16)) for h in c['psi_coeffs_hex']])
    u = psi.derivative()(x) / psi(x)
    return x + x*u + (x*u)^2
for c in [curves[0], curves[1], curves[57], curves[179], curves[300]]:
    b = F(int(c['b_int'])); E = EllipticCurve(K, [1, 1, 0, 0, b])
    psi = KY([F(int(h, 16)) for h in c['psi_coeffs_hex']])
    phi = E.isogeny(psi)
    iso = phi.codomain().isomorphism_to(E0)
    Pt = rand_order_N(E, cof)
    Xs = (iso(phi(Pt)))[0]
    chk('x-only transport formula == Sage isogeny∘iso for %s' % c['label'], Xs == transport_x(c, Pt[0]))

# ---- normal basis tables (for Frobenius canonical forms in C) --------------------------------------
while True:
    beta = K.random_element()
    conj = [beta]
    for i in range(1, n): conj.append(conj[-1]^2)
    M = matrix(GF(2), [[(I(c) >> bit) & 1 for bit in range(n)] for c in conj])   # row i = poly coords of beta^(2^i)
    if M.is_invertible(): break
Minv = M.inverse()        # row i = NB coords of z^i
def rowint(r): return sum(int(r[i]) << i for i in range(n))
nb = dict(nb2poly=[hex(rowint(M.row(i))) for i in range(n)], poly2nb=[hex(rowint(Minv.row(i))) for i in range(n)], beta=hex(I(beta)))
json.dump(nb, open(OUT + 'nb_tables.json', 'w'))
# check: squaring = rotation in NB
def tonb(u):
    v = vector(GF(2), [(I(u) >> i) & 1 for i in range(n)]) * Minv
    return rowint(v)
u = K.random_element(); a = tonb(u); b2 = tonb(u^2)
rot = ((a << 1) | (a >> (n-1))) & ((1 << n) - 1)
chk('NB: squaring is rotation by one', rot == b2)

# ---- planted DLP instances ------------------------------------------------------------------------
def planted(E, lab, idx):
    G = rand_order_N(E, cof)
    k = ZZ.random_element(1, N)
    H = k*G
    return dict(curve=lab, idx=idx, k=int(k), Gx=hex(I(G[0])), Gy=hex(I(G[1])), Hx=hex(I(H[0])), Hy=hex(I(H[1])))
inst_floor = []
for c in curves:
    E = EllipticCurve(K, [1, 1, 0, 0, F(int(c['b_int']))])
    for r in range(3):
        inst_floor.append(planted(E, c['label'], r))
inst_E0 = [planted(E0, 'E0', r) for r in range(1000)]
chk('planted instances: %d floor (3 per floor curve), %d on E0' % (len(inst_floor), len(inst_E0)), True)

meta = dict(n=n, q=str(q), modulus='z^179+z^4+z^2+z+1', modulus_int=str((1 << 179) | (1 << 4) | (1 << 2) | (1 << 1) | 1),
            encoding='field element = integer, bit i = coefficient of z^i', curve_form='y^2+xy=x^3+a2 x^2+b',
            E0=dict(a2=1, b=1), t=str(t), card=str(card), twist_card=str(twist_card), N=str(N), N2=str(N2), cof=str(cof),
            cof359_twist=str(cof359), f=str(f), l=L, P=str(P_big), kP=str(kP), lam_l=int(lam), lam_P=str(int(lamP)),
            tau_eigen_s=str(s), D_ring=int(Dring), h_D=358, sage=version())
json.dump(dict(meta=meta, curves=curves, instances_floor=inst_floor, instances_E0=inst_E0, log=LOG),
          open(OUT + 'toy_ground_truth.json', 'w'), indent=0)
print('done in %.1f s' % (time.time() - T0))
