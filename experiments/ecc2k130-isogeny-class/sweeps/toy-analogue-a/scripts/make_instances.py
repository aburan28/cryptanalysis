"""Plant DLP instances on E0 and on selected floor curves of a toy family, build the ascending
l-isogeny floor -> E0 for each selected floor curve (Velu over F_{q^k}, k = ord(lambda)), and
transport the floor instances to E0.  Writes rho-solver input files.

usage: sage -python make_instances.py <family> <M_E0> <M_floor> <M_transport> [--all-floor]
Output: raw/<family>/inputs/*.txt, raw/<family>/instances.json, raw/<family>/transport.json
"""
import sys, json, time, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toylib import *
from sage.all import set_random_seed, GF, EllipticCurve, Integer, randint, log

fam = sys.argv[1]
M_E0, M_FL, M_TR = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
ALL_FLOOR = '--all-floor' in sys.argv
set_random_seed(777 + sum(map(ord, fam)))
T0 = time.time()
F = load_family(fam)
meta = F['meta']
a, n, l = meta['a'], meta['n'], meta['l']
N, h, t, q = Integer(meta['N']), Integer(meta['cofactor']), Integer(meta['t']), Integer(meta['q'])
s = Integer(meta['tau_eigen_s'])
t1 = -1 if a == 0 else 1
K, tail = make_field(n, meta['modulus_tail'])
assert tail == meta['modulus_tail']
E0 = EllipticCurve(K, [1, a, 0, 0, 1])
OUT = os.path.join(WORK, 'raw', fam)
os.makedirs(os.path.join(OUT, 'inputs'), exist_ok=True)

# choice of floor curves
if ALL_FLOOR:
    floor_labels = [x for x in F['curves'] if x != 'E0']
else:
    floor_labels = []
    for o in ('O00', 'O01'):
        for kk in (0, 1, n // 2):
            floor_labels.append(f'{o}-{kk:03d}')


def rand_instance(E):
    while True:
        P = h * E.random_point()
        if P != 0:
            break
    assert N * P == 0
    k = randint(1, int(N) - 1)
    return P, k, k * P


def expected(c):
    return math.sqrt(math.pi * float(N) / (2 * c))


def dpbits_for(c):
    return max(2, int(round(math.log2(max(1.0, expected(c) / 32)))))


def header(mode, c, b_int, a2, rbits):
    return (f"n {n}\ntail {tail:x}\na2 {a2}\nb {b_int:x}\nN {N}\ns {s if mode == 'negtau' else 0}\nmode {mode}\n"
            f"rbits {rbits}\ndpbits {dpbits_for(c)}\nmaxwalk 20\nseed {1000 + sum(map(ord, fam))}\n")


RBITS = 10 if N > 10**5 else 4
inst_rec = {}

# E0 instances: used for (ii) negtau, (iv) neg-only control, (v) no-equivalence control
lines = []
for i in range(M_E0):
    P, k, Q = rand_instance(E0)
    iid = f'{fam}:E0:{i:04d}'
    lines.append(f"inst {iid} {fe2int(P[0]):x} {fe2int(P[1]):x} {fe2int(Q[0]):x} {fe2int(Q[1]):x} {k}\n")
    inst_rec[iid] = dict(curve='E0', P=[fe2int(P[0]), fe2int(P[1])], Q=[fe2int(Q[0]), fe2int(Q[1])], k=int(k))
for mode, c in (('negtau', 2 * n), ('neg', 2), ('none', 1)):
    with open(os.path.join(OUT, 'inputs', f'E0__{mode}.txt'), 'w') as fh:
        fh.write(header(mode, c, 1, a, RBITS))
        fh.writelines(lines)
print('E0 instances', M_E0, round(time.time() - T0, 1), flush=True)

# transport machinery: L_T = F_{q^kT}, kT = ord(lambda)
lam = GF(l)(t) / 2
kT = int(lam.multiplicative_order())
LT, emb, down = make_ext(K, n, kT)


cardLT = Integer(2)**(n * kT) + 1 - lucas_t(t1, n * kT)
vT = cardLT.valuation(l)
cofT = cardLT // l**vT
E0L = EllipticCurve(LT, [1, a, 0, 0, 1])

transport = {}
for lab in floor_labels:
    cinfo = F['curves'][lab]
    b = int2fe(K, cinfo['b_int'])
    Ef = EllipticCurve(K, [1, a, 0, 0, b])
    tb = time.time()
    EfL = EllipticCurve(LT, [1, a, 0, 0, emb(b)])
    assert cardLT * EfL.random_point() == 0

    def lpt():
        while True:
            U = cofT * EfL.random_point()
            if U == 0:
                continue
            while l * U != 0:
                U = l * U
            return U
    T1 = lpt()
    T2 = lpt()
    frob_ok = EfL(T1[0]**q, T1[1]**q) == int(lam) * T1
    cyclic_ok = T1.weil_pairing(T2, l) == 1   # E_f(F_{q^kT})[l] is a single line (floor), unlike E0[l]
    phi = EfL.isogeny(T1, algorithm='velu') if True else None
    cod = phi.codomain()
    j_ok = cod.j_invariant() == 1
    iso = cod.isomorphism_to(E0L)
    build_s = time.time() - tb

    def transport_pt(P):
        R = iso(phi(EfL(emb(P[0]), emb(P[1]))))
        return E0(down(R[0]), down(R[1]))
    # instances on this floor curve
    flines, tlines = [], []
    eval_times = []
    tr_ok = 0
    for i in range(max(M_FL, M_TR)):
        P, k, Q = rand_instance(Ef)
        iid = f'{fam}:{lab}:{i:04d}'
        rec = dict(curve=lab, P=[fe2int(P[0]), fe2int(P[1])], Q=[fe2int(Q[0]), fe2int(Q[1])], k=int(k))
        if i < M_FL:
            flines.append(f"inst {iid} {rec['P'][0]:x} {rec['P'][1]:x} {rec['Q'][0]:x} {rec['Q'][1]:x} {k}\n")
        if i < M_TR:
            te = time.time()
            Pt_ = transport_pt(P)
            Qt_ = transport_pt(Q)
            eval_times.append(time.time() - te)
            ok = (Pt_ != 0 and N * Pt_ == 0 and k * Pt_ == Qt_)
            tr_ok += ok
            rec['P_E0'] = [fe2int(Pt_[0]), fe2int(Pt_[1])]
            rec['Q_E0'] = [fe2int(Qt_[0]), fe2int(Qt_[1])]
            tlines.append(f"inst {iid}:tr {rec['P_E0'][0]:x} {rec['P_E0'][1]:x} {rec['Q_E0'][0]:x} {rec['Q_E0'][1]:x} {k}\n")
        inst_rec[iid] = rec
    with open(os.path.join(OUT, 'inputs', f'{lab}__neg.txt'), 'w') as fh:
        fh.write(header('neg', 2, cinfo['b_int'], a, RBITS))
        fh.writelines(flines)
    with open(os.path.join(OUT, 'inputs', f'{lab}__transport_negtau.txt'), 'w') as fh:
        fh.write(header('negtau', 2 * n, 1, a, RBITS))
        fh.writelines(tlines)
    transport[lab] = dict(ext_degree_kT=kT, L_bits=n * kT, frob_eigen_ok=bool(frob_ok), floor_l_torsion_cyclic=bool(cyclic_ok),
                          codomain_j_is_1=bool(j_ok), isogeny_degree=int(phi.degree()), build_s=round(build_s, 2),
                          eval_s_per_instance_mean=(sum(eval_times) / len(eval_times)) if eval_times else None,
                          transported=len(eval_times), transported_log_preserved=tr_ok,
                          kernel_points_used_per_eval=(l - 1) // 2)
    print(lab, transport[lab], round(time.time() - T0, 1), flush=True)
    assert frob_ok and cyclic_ok and j_ok and tr_ok == len(eval_times)

json.dump(inst_rec, open(os.path.join(OUT, 'instances.json'), 'w'))
json.dump(dict(family=fam, floor_labels=floor_labels, M_E0=M_E0, M_floor=M_FL, M_transport=M_TR, rbits=RBITS,
               transport=transport, secs=round(time.time() - T0, 1)), open(os.path.join(OUT, 'transport.json'), 'w'), indent=1)
print('done', fam, round(time.time() - T0, 1))
