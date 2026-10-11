"""Bridge from the toys to the real ECC2K-130 class: build the ascending 263-isogeny
floor curve -> E0 for a sample of ground-truth floor curves (Velu over F_{q^2} with the
unique F_q-rational 263-subgroup, which is E(F_{q^2})[263]), check codomain j = 1, and check
that it transports planted toy-sized DLP relations Q = kP (P of order N) to E0, timing it.
No attempt is made to solve any ECC2K-130 DLP; k is planted by us.

usage: sage -python real_transport.py [labels...]
Writes results/real_transport.json (or results/real_transport_all.json with --all [nrel])
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/Volumes/SSD990/ecdlp-hardness-work/ground_truth')
import ecc2k
from toylib import make_ext, WORK
from sage.all import EllipticCurve, Integer, set_random_seed, randint

set_random_seed(4242)
args = sys.argv[1:]
NREL = 5
if args and args[0] == '--all':
    labels = [x for x in ecc2k.LABELS if x != 'E0']
    NREL = int(args[1]) if len(args) > 1 else 3
    OUTNAME = 'real_transport_all.json'
else:
    labels = args or ['A000', 'A001', 'A065', 'B000', 'B001', 'B065']
    OUTNAME = 'real_transport.json'
K = ecc2k.field()
N, q, t = Integer(ecc2k.N), Integer(ecc2k.q), Integer(ecc2k.t)
L, emb, down = make_ext(K, 131, 2)
E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
E0L = EllipticCurve(L, [1, 0, 0, 0, 1])
cardL = (q + 1 - t) * (q + 1 + t)
assert cardL.valuation(263) == 2
cof = cardL // 263**2
res = {}
for lab in labels:
    E = ecc2k.curve(lab)
    r = ecc2k.RECORDS[lab]
    t0 = time.time()
    EL = EllipticCurve(L, [1, int(r['a2']), 0, 0, emb(E.a6())])
    assert cardL * EL.random_point() == 0
    pts = []
    while len(pts) < 2:
        U = cof * EL.random_point()
        if U == 0:
            continue
        while 263 * U != 0:
            U = 263 * U
        pts.append(U)
    T1, T2 = pts
    frob = EL(T1[0]**q, T1[1]**q) == -T1           # pi acts as -1 on the kernel line
    xin_Fq = (emb(down(T1[0])) == T1[0])            # x(T) in F_q
    cyclic = T1.weil_pairing(T2, 263) == 1          # E(F_{q^2})[263] is one line
    phi = EL.isogeny(T1, algorithm='velu')
    cod = phi.codomain()
    jok = cod.j_invariant() == 1
    iso = cod.isomorphism_to(E0L)
    build = time.time() - t0
    ok, times = 0, []
    for i in range(NREL):
        P = 4 * E.random_point()
        while P == 0:
            P = 4 * E.random_point()
        k = randint(1, int(N) - 1)
        Q = k * P
        te = time.time()
        Pt = iso(phi(EL(emb(P[0]), emb(P[1]))))
        Qt = iso(phi(EL(emb(Q[0]), emb(Q[1]))))
        Pe = E0(down(Pt[0]), down(Pt[1]))
        Qe = E0(down(Qt[0]), down(Qt[1]))
        times.append(time.time() - te)
        ok += (Pe != 0 and N * Pe == 0 and k * Pe == Qe and Pe[0]**2 != Pe[0])
    res[lab] = dict(isogeny_degree=int(phi.degree()), pi_acts_as_minus_1_on_kernel=bool(frob), kernel_x_in_Fq=bool(xin_Fq),
                    E_Fq2_263_torsion_is_one_line=bool(cyclic), codomain_j_is_1=bool(jok),
                    planted_relations_transported_ok=ok, of=NREL, build_s=round(build, 2),
                    eval_s_per_instance_mean=sum(times) / len(times), kernel_terms_per_point=131)
    print(lab, res[lab], flush=True)
os.makedirs(os.path.join(WORK, 'results'), exist_ok=True)
json.dump(res, open(os.path.join(WORK, 'results', OUTNAME), 'w'), indent=1)
