# stage2.sage START END -- per-floor-curve checks and planted DLP instances for curves[START:END] of stage1.json,
# plus (when START == 0) the E0 instances and the Sage cross-check of the x-only transport formula.
# Output: ../raw/stage2_<START>_<END>.json
import json, time, sys
def _dflt(o):
    try: return int(o) if o == int(o) else float(o)
    except Exception:
        try: return float(o)
        except Exception: return str(o)
START, END = int(sys.argv[1]), int(sys.argv[2])
OUT = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/'
S1 = json.load(open(OUT + 'stage1.json'))
meta = S1['meta']
set_random_seed(20260923 + 1000*START)
RZ.<Z> = GF(2)[]
K.<z> = GF(2^179, modulus=Z^179+Z^4+Z^2+Z+1)
KY.<Y> = K[]
def I(u): return int(u.to_integer())
def F(i): return K.from_integer(int(i))
N = ZZ(meta['N']); N2 = ZZ(meta['N2']); card = ZZ(meta['card']); twist_card = ZZ(meta['twist_card']); L = 359
cof = card // N; cof359 = twist_card // L^2
E0 = EllipticCurve(K, [1, 1, 0, 0, 1])

def halftrace(c):
    h = c; u = c
    for i in range(89):
        u = u^4; h += u
    return h
def rpoint(E):
    """uniform-ish random affine point on y^2+xy = x^3+a2 x^2+b via the half-trace (n odd)"""
    a2 = E.a2(); b = E.a6()
    while True:
        x = K.random_element()
        if x == 0: continue
        c = x + a2 + b/x^2
        if c.trace() != 0: continue
        y = x*halftrace(c)
        P = E(x, y)
        return P if randint(0, 1) else -P
def rand_order_N(E):
    while True:
        Q = cof * rpoint(E)
        if not Q.is_zero():
            assert (N*Q).is_zero()
            return Q
def halfkernel_x(Kp):
    xs = []; Q = Kp
    for i in range(1, (L-1)//2 + 1):
        xs.append(Q[0]); Q += Kp
    return xs
def planted(E, lab, idx):
    G = rand_order_N(E)
    k = ZZ.random_element(1, N)
    H = k*G
    return dict(curve=lab, idx=idx, k=int(k), Gx=hex(I(G[0])), Gy=hex(I(G[1])), Hx=hex(I(H[0])), Hy=hex(I(H[1])))

T0 = time.time()
out_curves = []; inst = []
for c in S1['curves'][START:END]:
    t0 = time.time()
    b = F(c['b_int']); j = F(c['j_int']); assert b*j == 1
    E = EllipticCurve(K, [1, 1, 0, 0, b])
    R = rpoint(E)
    ok_order = (card*R).is_zero() and not ((2*N2)*R).is_zero() and not ((2*N)*R).is_zero()
    c_pari = E.cardinality(algorithm='pari')                  # SEA is fast here (~0.05 s): do it for every curve
    Et = EllipticCurve(K, [1, 0, 0, 0, b])
    c_pari_tw = Et.cardinality(algorithm='pari')
    for attempt in range(30):
        R1 = cof359 * rpoint(Et); R359 = L*R1
        if not R359.is_zero(): break
    cyclic = not R359.is_zero()
    Kg = R359
    assert (L*Kg).is_zero() and not Kg.is_zero()
    xs = halfkernel_x(Kg); v = sum(xs)
    psi = prod(Y - u for u in xs)
    up_ok = (b + v + v^2 == 1)
    rec = dict(c)
    rec.update(order_point_proof=bool(ok_order), order_pari=str(c_pari), twist_order_pari=str(c_pari_tw),
               order_ok=bool(c_pari == card and ok_order), twist_ok=bool(c_pari_tw == twist_card),
               twist_sylow359_cyclic=bool(cyclic), ascending_codomain_is_E0=bool(up_ok),
               psi_coeffs_hex=[hex(I(u)) for u in psi.list()], v_int=str(I(v)), sage_seconds=float(round(time.time()-t0, 3)))
    out_curves.append(rec)
    for r in range(3):
        inst.append(planted(E, c['label'], r))
    assert ok_order and up_ok and cyclic and c_pari == card and c_pari_tw == twist_card, c['label']
    print(c['label'], 'ok', round(time.time()-t0, 2), flush=True)

extra = {}
if START == 0:
    extra['instances_E0'] = [planted(E0, 'E0', r) for r in range(1000)]
    # Sage cross-check of the x-only transport formula X = x + x u + (x u)^2, u = psi'(x)/psi(x)
    chk = []
    for rec in out_curves[:3]:
        b = F(rec['b_int']); E = EllipticCurve(K, [1, 1, 0, 0, b])
        psi = KY([F(int(h, 16)) for h in rec['psi_coeffs_hex']])
        phi = E.isogeny(psi); iso = phi.codomain().isomorphism_to(E0)
        for rep in range(3):
            Pt = rand_order_N(E)
            u = psi.derivative()(Pt[0]) / psi(Pt[0]); Xf = Pt[0] + Pt[0]*u + (Pt[0]*u)^2
            chk.append(dict(label=rec['label'], ok=bool(iso(phi(Pt))[0] == Xf)))
    extra['transport_formula_check'] = chk
    assert all(x['ok'] for x in chk)
json.dump(dict(curves=out_curves, instances_floor=inst, **extra), open(OUT + 'stage2_%d_%d.json' % (START, END), 'w'), default=_dflt)
print('stage2 %d..%d done in %.1f s' % (START, END, time.time()-T0))
