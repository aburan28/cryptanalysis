"""Floor instances + transport for families where Sage's Velu object is too slow (T59: kernel of
5783 points over F_{2^2891}).  The ascending isogeny E_f -> E0 is evaluated over F_q from its
kernel polynomial psi (degree (l-1)/2, coefficients in F_q) with the characteristic-2 Velu
formulas for y^2 + xy = x^3 + a2 x^2 + b written in terms of psi:
  d_Q = x + x_Q,  e1 = psi'(x)/psi(x), e2 = psi^[2](x)/psi(x), e3 = psi^[3](x)/psi(x)  (Hasse derivatives)
  s1 = sum 1/d_Q = e1,  s2 = s1^2,  s3 = sum 1/d_Q^3 = e1^3 + e1 e2 + e3
  X = x + A + A^2,  A = x s1 + |S|                  (|S| = (l-1)/2)
  Y = y + x^3 s3 + x s1 + (x + y + x^2)(x s2 + s1) + v,  v = sigma_1 = sum x_Q
  codomain y^2 + xy = x^3 + a2 x^2 + v x + (b + v);  (X, Y) -> (X, Y + v) lands on [1, a2, 0, 0, b + v + v^2]
(the x_Q*y_Q terms of Velu's Y cancel in characteristic 2).  Checked against Sage's Velu on
the T19/T23/T109 transported points (up to the automorphism -1) with --crosscheck.

usage: sage -python make_floor_fast.py <family> <M_floor> <M_transport> [--crosscheck | --only <label> | --merge]
"""
import sys, json, time, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toylib import *
from sage.all import (set_random_seed, GF, EllipticCurve, Integer, randint, PolynomialRing, prod, binomial)

fam = sys.argv[1]
M_FL, M_TR = int(sys.argv[2]), int(sys.argv[3])
CROSS = '--crosscheck' in sys.argv
set_random_seed(999 + sum(map(ord, fam)))
T0 = time.time()
F = load_family(fam)
meta = F['meta']
a, n, l = meta['a'], meta['n'], meta['l']
N, h, t, q = Integer(meta['N']), Integer(meta['cofactor']), Integer(meta['t']), Integer(meta['q'])
s = Integer(meta['tau_eigen_s'])
t1 = -1 if a == 0 else 1
K, tail = make_field(n, meta['modulus_tail'])
E0 = EllipticCurve(K, [1, a, 0, 0, 1])
OUT = os.path.join(WORK, 'raw', fam)
os.makedirs(os.path.join(OUT, 'inputs'), exist_ok=True)
half = (l - 1) // 2
RK = PolynomialRing(K, 'X')


def expected(c):
    return math.sqrt(math.pi * float(N) / (2 * c))


def dpbits_for(c):
    return max(2, int(round(math.log2(max(1.0, expected(c) / 32)))))


def header(mode, c, b_int, a2, rbits):
    return (f"n {n}\ntail {tail:x}\na2 {a2}\nb {b_int:x}\nN {N}\ns {s if mode == 'negtau' else 0}\nmode {mode}\n"
            f"rbits {rbits}\ndpbits {dpbits_for(c)}\nmaxwalk 20\nseed {1000 + sum(map(ord, fam))}\n")


RBITS = 10 if N > 10**5 else 4
lam = GF(l)(t) / 2
kT = int(lam.multiplicative_order())
LT, emb, down = make_ext(K, n, kT)
cardLT = Integer(2)**(n * kT) + 1 - lucas_t(t1, n * kT)
vT = cardLT.valuation(l)
cofT = cardLT // l**vT
print('ext field ready', n * kT, round(time.time() - T0, 1), flush=True)


def hasse_coeffs(psi, k):
    """coefficients of the k-th Hasse derivative (sum_m binom(m,k) c_m X^(m-k)) over F_2 binomials."""
    cl = psi.list()
    return RK([cl[m] if (binomial(m, k) % 2) else K(0) for m in range(k, len(cl))])


def make_transport(Ef, b):
    """returns (map P -> phi(P) on E0, info) for the ascending l-isogeny of E_f."""
    EfL = EllipticCurve(LT, [1, a, 0, 0, emb(b)])

    def lpt():
        while True:
            U = cofT * EfL.random_point()
            if U == 0:
                continue
            while l * U != 0:
                U = l * U
            return U
    tb = time.time()
    T1, T2 = lpt(), lpt()
    frob_ok = EfL(T1[0]**q, T1[1]**q) == int(lam) * T1
    cyclic_ok = T1.weil_pairing(T2, l) == 1
    xs = []
    S = T1
    for i in range(half):
        xs.append(S[0])
        S = S + T1
    RL = PolynomialRing(LT, 'X')
    X = RL.gen()
    # psi = prod over Frobenius orbits of kernel indices (i -> lambda*i mod l, up to sign) of
    # the orbit polynomials, each of which has coefficients in K (much cheaper than one big
    # product over L).  Spot-check that x(iT)^q == x(lambda i T).
    lam_i = int(lam)
    rep_ = lambda i: min(i % l, (-i) % l)
    for i in (1, 2, 3):
        assert xs[i - 1]**q == xs[rep_(lam_i * i) - 1]
    seen, orbit_polys = set(), []
    for i0 in range(1, half + 1):
        if i0 in seen:
            continue
        orb, i = [], i0
        while i not in seen:
            seen.add(i)
            orb.append(i)
            i = rep_(lam_i * i)
        polL = prod([X - xs[i - 1] for i in orb])
        orbit_polys.append(RK([down(cc) for cc in polL.list()]))
    assert len(seen) == half
    psi = prod(orbit_polys)
    v = sum(xs)
    vK = down(v)
    assert psi.list()[half - 1] == vK            # sigma_1 = coefficient of X^(half-1) (char 2)
    b_cod = b + vK + vK * vK
    j_ok = (b_cod == 1)                          # codomain is exactly E0 = [1, a, 0, 0, 1]
    d1, d2, d3 = psi.derivative(), hasse_coeffs(psi, 2), hasse_coeffs(psi, 3)
    Smod = K(half % 2)
    build_s = time.time() - tb

    def phi(P):
        x, y = P[0], P[1]
        p0 = psi(x)
        e1, e2, e3 = d1(x) / p0, d2(x) / p0, d3(x) / p0
        s1 = e1
        s2 = s1 * s1
        s3 = e1**3 + e1 * e2 + e3
        A = x * s1 + Smod
        Xn = x + A + A * A
        Yn = y + x**3 * s3 + x * s1 + (x + y + x * x) * (x * s2 + s1) + vK
        return E0(Xn, Yn + vK)
    info = dict(frob_eigen_ok=bool(frob_ok), floor_l_torsion_cyclic=bool(cyclic_ok), codomain_j_is_1=bool(j_ok),
                build_s=round(build_s, 2), kernel_poly_degree=int(psi.degree()), ext_degree_kT=kT, L_bits=n * kT)
    return phi, info


if CROSS:
    # compare with the Sage-Velu transported points of this family (instances.json from make_instances.py)
    inst = json.load(open(os.path.join(OUT, 'instances.json')))
    tr = json.load(open(os.path.join(OUT, 'transport.json')))
    res = {}
    for lab in tr['floor_labels']:
        c = F['curves'][lab]
        b = int2fe(K, c['b_int'])
        Ef = EllipticCurve(K, [1, a, 0, 0, b])
        phi, info = make_transport(Ef, b)
        agree = tot = 0
        for iid, r in inst.items():
            if r['curve'] != lab or 'P_E0' not in r:
                continue
            P = Ef(int2fe(K, r['P'][0]), int2fe(K, r['P'][1]))
            Pv = E0(int2fe(K, r['P_E0'][0]), int2fe(K, r['P_E0'][1]))
            mine = phi(P)
            agree += (mine == Pv or mine == -Pv)
            tot += 1
            if tot >= 20:
                break
        res[lab] = dict(info, agree_with_sage_velu_up_to_sign=agree, compared=tot)
        print(lab, res[lab], flush=True)
    json.dump(res, open(os.path.join(OUT, 'crosscheck_fast_transport.json'), 'w'), indent=1)
    sys.exit(0)

# floor curves: O00, O01 x {0, 1, n//2}; '--only <label>' builds one curve into a part file
floor_labels = [f'{o}-{kk:03d}' for o in ('O00', 'O01') for kk in (0, 1, n // 2)]
ONLY = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
MERGE = '--merge' in sys.argv
PARTS = os.path.join(OUT, 'parts')
os.makedirs(PARTS, exist_ok=True)
inst_rec = {}
# E0 records from the existing E0 input file (instances already planted by make_instances.py)
for line in open(os.path.join(OUT, 'inputs', 'E0__negtau.txt')):
    if line.startswith('inst '):
        _, iid, px, py, qx, qy, k = line.split()
        inst_rec[iid] = dict(curve='E0', P=[int(px, 16), int(py, 16)], Q=[int(qx, 16), int(qy, 16)], k=int(k))
transport = {}
if MERGE:
    for lab in floor_labels:
        part = json.load(open(os.path.join(PARTS, f'{lab}.json')))
        inst_rec.update(part['inst'])
        transport[lab] = part['transport']
    json.dump(inst_rec, open(os.path.join(OUT, 'instances.json'), 'w'))
    json.dump(dict(family=fam, floor_labels=floor_labels, M_E0=sum(1 for r in inst_rec.values() if r['curve'] == 'E0'), M_floor=M_FL,
                   M_transport=M_TR, rbits=RBITS, transport=transport, secs=None), open(os.path.join(OUT, 'transport.json'), 'w'), indent=1)
    print('merged', len(inst_rec))
    sys.exit(0)
if ONLY:
    floor_labels = [ONLY]
    set_random_seed(999 + sum(map(ord, fam)) + 7919 * sum(map(ord, ONLY)))
for lab in floor_labels:
    c = F['curves'][lab]
    b = int2fe(K, c['b_int'])
    Ef = EllipticCurve(K, [1, a, 0, 0, b])
    phi, info = make_transport(Ef, b)
    flines, tlines, eval_times, tr_ok = [], [], [], 0
    for i in range(max(M_FL, M_TR)):
        while True:
            P = h * Ef.random_point()
            if P != 0:
                break
        assert N * P == 0
        k = randint(1, int(N) - 1)
        Q = k * P
        iid = f'{fam}:{lab}:{i:04d}'
        rec = dict(curve=lab, P=[fe2int(P[0]), fe2int(P[1])], Q=[fe2int(Q[0]), fe2int(Q[1])], k=int(k))
        if i < M_FL:
            flines.append(f"inst {iid} {rec['P'][0]:x} {rec['P'][1]:x} {rec['Q'][0]:x} {rec['Q'][1]:x} {k}\n")
        if i < M_TR:
            te = time.time()
            Pt_, Qt_ = phi(P), phi(Q)
            eval_times.append(time.time() - te)
            ok = (Pt_ != 0 and N * Pt_ == 0 and k * Pt_ == Qt_)
            tr_ok += ok
            rec['P_E0'] = [fe2int(Pt_[0]), fe2int(Pt_[1])]
            rec['Q_E0'] = [fe2int(Qt_[0]), fe2int(Qt_[1])]
            tlines.append(f"inst {iid}:tr {rec['P_E0'][0]:x} {rec['P_E0'][1]:x} {rec['Q_E0'][0]:x} {rec['Q_E0'][1]:x} {k}\n")
        inst_rec[iid] = rec
    with open(os.path.join(OUT, 'inputs', f'{lab}__neg.txt'), 'w') as fh:
        fh.write(header('neg', 2, c['b_int'], a, RBITS))
        fh.writelines(flines)
    with open(os.path.join(OUT, 'inputs', f'{lab}__transport_negtau.txt'), 'w') as fh:
        fh.write(header('negtau', 2 * n, 1, a, RBITS))
        fh.writelines(tlines)
    transport[lab] = dict(info, isogeny_degree=l, method='kernel polynomial over F_q + char-2 Velu formulas (make_floor_fast.py)',
                          eval_s_per_instance_mean=sum(eval_times) / len(eval_times) if eval_times else None,
                          transported=len(eval_times), transported_log_preserved=tr_ok, kernel_points_used_per_eval=half)
    print(lab, transport[lab], round(time.time() - T0, 1), flush=True)
    assert info['frob_eigen_ok'] and info['floor_l_torsion_cyclic'] and info['codomain_j_is_1'] and tr_ok == len(eval_times)
    if ONLY:
        json.dump(dict(inst={k: v for k, v in inst_rec.items() if v['curve'] == lab}, transport=transport[lab]),
                  open(os.path.join(PARTS, f'{lab}.json'), 'w'))
        print('part written', lab)
        sys.exit(0)
json.dump(inst_rec, open(os.path.join(OUT, 'instances.json'), 'w'))
json.dump(dict(family=fam, floor_labels=floor_labels, M_E0=sum(1 for r in inst_rec.values() if r['curve'] == 'E0'), M_floor=M_FL,
               M_transport=M_TR, rbits=RBITS, transport=transport, secs=round(time.time() - T0, 1)),
          open(os.path.join(OUT, 'transport.json'), 'w'), indent=1)
print('done', fam, round(time.time() - T0, 1))
