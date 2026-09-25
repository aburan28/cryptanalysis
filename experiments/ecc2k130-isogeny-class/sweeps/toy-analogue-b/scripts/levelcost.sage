# levelcost.sage -- the "large conductor prime" question, for the toy (n=179) and for ECC2K-130 (n=131).
# For every prime P | f: pi acts on E0[P] as the scalar lambda = t/2 mod P; the points of E0[P] (all P+1 kernels of
# P-isogenies out of E0) and of the kernel of the ascending P-isogeny from any level-P curve are defined over
# F_{q^k}, k = ord_P(lambda) exactly.  A second route (no kernel points) is the modular polynomial Phi_P(j, Y);
# we time PARI polmodular(L, 0, j) for growing L to measure its growth exponent.
import json, time, sys, math
def _dflt(o):
    try: return int(o) if o == int(o) else float(o)
    except Exception:
        try: return float(o)
        except Exception: return str(o)
OUT = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/levelcost.json'
res = {}
def lucas(n, t1):
    tt = [2, t1]
    for i in range(2, n+1): tt.append(t1*tt[-1] - 2*tt[-2])
    return tt[n]
for name, n, t1 in [('ECC2K-130 (n=131, a2=0)', 131, -1), ('toy-b (n=179, a2=1)', 179, 1)]:
    t = lucas(n, t1); q = 2^n
    f = isqrt((t*t - 4*q)//(-7)); assert -7*f^2 == t*t - 4*q
    rows = []
    for P, e in factor(f):
        lam = Mod(t, P)/2
        k = lam.multiplicative_order()
        kind = 'other'
        if (P-1) % k == 0: kind = '(P-1)/%d' % ((P-1)//k)
        rows.append(dict(P=str(P), log2P=float(RR(log(P, 2))), kron=int(kronecker(-7, P)), lam=str(lam), k=str(k),
                         log2k=float(RR(log(k, 2))), k_is=kind, kernel_poly_degree=str((P-1)//2),
                         log2_bits_one_elt_of_F_q_k=float(RR(log(k*n, 2))),
                         log2_bits_kernel_poly_over_Fq=float(RR(log((P-1)//2*n, 2)))))
    Nl = max(pp for pp, ee in factor(q+1-t))
    res[name] = dict(n=n, t=str(t), f=str(f), primes=rows, dlp_prime=str(Nl),
                     log2_rho_negation=float(RR(log(sqrt(pi*Nl/4), 2))), log2_rho_tau_negation=float(RR(log(sqrt(pi*Nl/(4*n)), 2))))
    print(name, json.dumps(res[name], indent=1, default=_dflt), flush=True)
json.dump(dict(levels=res), open(OUT, 'w'), indent=1, default=_dflt)

# modular polynomial route: time Phi_L(j, Y) for j = 1 (E0, mod 2) and for a random j in F_{2^179}
timings = []
Fq = GF(2^179, 'z', modulus=GF(2)['Z']('Z^179+Z^4+Z^2+Z+1'))
set_random_seed(5)
jr = Fq.random_element()
for L in [53, 101, 151, 211, 263, 359, 503, 701, 1009, 1409, 1721, 2003, 2663]:
    t0 = cputime(); w0 = time.time()
    phi = pari('polmodular(%d, 0, Mod(1,2))' % L)
    c1 = cputime(t0); w1 = time.time() - w0
    deg = int(phi.poldegree())
    # (PARI polmodular only evaluates at x in the prime field, so j = 1 (E0) is the only evaluation point available)
    c2 = 0.0
    timings.append(dict(L=L, cpu_j1=float(c1), wall_j1=w1, deg=deg))
    print(timings[-1], flush=True)
    json.dump(dict(levels=res, polmodular=timings), open(OUT, 'w'), indent=1, default=_dflt)
    if c1 > 600: break
fit = {}
for key in ['cpu_j1']:
    pts = [(math.log(x['L']), math.log(max(x[key], 1e-3))) for x in timings if x['L'] >= 200]
    if len(pts) >= 3:
        xs = [a for a, b in pts]; ys = [b for a, b in pts]; mx = sum(xs)/len(xs); my = sum(ys)/len(ys)
        alpha = sum((a-mx)*(b-my) for a, b in pts)/sum((a-mx)**2 for a in xs); c = math.exp(my - alpha*mx)
        fit[key] = dict(alpha=alpha, c=c, log2_extrapolated_cpu_seconds={str(L): math.log2(c) + alpha*math.log2(L)
                        for L in [77761, 146505763881528721, 513035439254495356843057]})
print('fit', fit)
json.dump(dict(levels=res, polmodular=timings, fit=fit), open(OUT, 'w'), indent=1, default=_dflt)
