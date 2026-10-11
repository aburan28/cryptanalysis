# Toy analogue of the p-level structure, on the Koblitz curve y^2+xy=x^3+1 over F_{2^m}.
#  inert case (analogue of p, (-7|p) = -1):  m = 37, l = 73 | f_37, (-7|73) = -1
#  split case (analogue of 263, (-7|263)=+1): m = 11, l = 23 | f_11, (-7|23) = +1
# Verifies, by explicit Velu isogenies over the extension field where the l-torsion lives:
#  (a) Frobenius pi acts on E0[l] as the scalar t/2 mod l (crater), so E0[l] lives over F_{q^r}, r = ord(t/2);
#  (b) inert: all l+1 l-isogenies from E0 are F_q-rational and descending (no j = 1), l+1 distinct j in F_q,
#      forming (l+1)/m Frobenius orbits of size m; split: 2 horizontal (j=1) + l-1 descending;
#  (c) on a level-l curve E1, E1(F_{q^r})[l] is ONE line (so pi is a nontrivial Jordan block on E1[l]),
#      the l-primary part of E1(F_{q^r}) is cyclic Z/l^2, the line is the pi-eigenline with eigenvalue t/2
#      and the isogeny with that kernel goes back up to j = 1;
#  (d) no l-torsion at all over F_{q^k} for k < r (both curves), and kernel x-coordinates have degree r_x.
# Also cross-checks the set of descended j against Phi_l(1, Y) mod 2 from PARI polmodular.
import json, time, sys
set_random_seed(20260923)
results = {}

def trace_koblitz(m):
    t0, t1 = 2, -1
    for k in range(1, m):
        t0, t1 = t1, -t1 - 2*t0
    return t1

def tk_of(t, q, k):
    a, b = 2, t
    for i in range(1, k):
        a, b = b, t*b - q*a
    return b if k >= 1 else 2

def run_case(m, l, twist_for_ext):
    T = time.time()
    res = {"m": m, "l": l}
    q = 2^m
    t = trace_koblitz(m)
    D = t^2 - 4*q; f = isqrt(D // -7); assert -7*f^2 == D and f % l == 0
    res["t"] = int(t); res["f"] = int(f); res["kronecker(-7,l)"] = int(kronecker(-7, l))
    Fl = GF(l); c = Fl(t)/2; assert c^2 == Fl(q)
    r = c.multiplicative_order(); rtw = (-c).multiplicative_order()
    res["c"] = int(c); res["r=ord(c)"] = int(r); res["ord(-c)"] = int(rtw)
    # (d) point counts mod l over F_{q^k}: E0 has Frobenius pi (trace t), twist has -pi.
    def Nk(k, tw):
        tt = (-t if tw else t)
        return q^k + 1 - tk_of(tt, q, k)
    res["E0: k<=2r with l | #E0(F_q^k)"] = [k for k in range(1, 2*r+1) if Nk(k, False) % l == 0]
    res["twist: k<=2*ord(-c) with l | #E0'(F_q^k)"] = [k for k in range(1, 2*rtw+1) if Nk(k, True) % l == 0]
    assert res["E0: k<=2r with l | #E0(F_q^k)"] == [r, 2*r]
    # choose the extension: E0 over F_{q^r} or the twist over F_{q^rtw}
    ext = rtw if twist_for_ext else r
    a2 = 1 if twist_for_ext else 0
    L = GF(2^(m*ext), 'w')
    if twist_for_ext:
        assert (m*ext) % 2 == 1   # Tr(1) = 1 in L, so [1,1,0,0,1] is still the nontrivial twist over L
    E = EllipticCurve(L, [1, a2, 0, 0, 1])
    eig = (-c if twist_for_ext else c)          # eigenvalue of the F_q-Frobenius of this model on E[l]
    nL = Nk(ext, twist_for_ext)
    assert E.random_point() * nL == E(0)
    vl = valuation(nL, l); res["v_l(#E(F_q^ext))"] = int(vl); res["ext_degree_over_F_q"] = int(ext)
    cof = nL // l^vl
    def frob(P):
        if P.is_zero(): return P
        return E(P[0]^(2^m), P[1]^(2^m))
    # basis of E[l]
    pts = []
    while True:
        P = E.random_point() * cof
        while not (P * l).is_zero():
            P = P * l
        if P.is_zero(): continue
        if not pts: pts.append(P); continue
        if P.weil_pairing(pts[0], l) != 1:
            pts.append(P); break
    P1, P2 = pts
    # (a) scalar action of Frobenius on E[l]
    res["(a) pi = eig*id on P1,P2,P1+P2"] = bool(frob(P1) == int(eig)*P1 and frob(P2) == int(eig)*P2 and frob(P1+P2) == int(eig)*(P1+P2))
    assert res["(a) pi = eig*id on P1,P2,P1+P2"]
    # (b) all l+1 isogenies
    gens = [P1] + [P2 + i*P1 for i in range(l)]
    js = []
    t_iso = time.time()
    for G in gens:
        phi = E.isogeny(G)
        j = phi.codomain().j_invariant()
        js.append(j)
    res["time_isogenies_s"] = round(time.time() - t_iso, 1)
    in_Fq = [bool(j^(2^m) == j) for j in js]
    res["(b) all codomain j in F_q"] = all(in_Fq)
    n_hor = sum(1 for j in js if j == 1)
    res["(b) number of j = 1 (horizontal)"] = n_hor
    res["(b) distinct j"] = len(set(js))
    desc = [j for j in js if j != 1]
    mp = {}
    for j in desc:
        g = j.minpoly()
        mp.setdefault(str(g), []).append(j)
    res["(b) Frobenius-orbit sizes (min poly degrees) of descended j"] = sorted(Integer(len(v)) for v in mp.values())
    res["(b) min poly degrees"] = sorted(set(int(j.minpoly().degree()) for j in desc))
    # Phi_l(1, Y) mod 2 cross-check
    Phi = pari(f"polmodular({l}, 0, Mod(1,2), 'y)")
    Ry = PolynomialRing(GF(2), 'y')
    PhiY = Ry(str(pari(f"lift({Phi})")).replace('y', 'y'))
    RL = PolynomialRing(L, 'Y')
    prodY = prod(RL.gen() - j for j in js)
    res["(b) prod(Y - j) == Phi_l(1,Y) mod 2"] = bool(prodY == RL(PhiY.change_ring(L)))
    assert res["(b) prod(Y - j) == Phi_l(1,Y) mod 2"]
    # (c) level-l curve: take the first descending codomain
    idx = next(i for i, j in enumerate(js) if j != 1)
    phi = E.isogeny(gens[idx]); C = phi.codomain()
    j1 = js[idx]; b1 = 1/j1
    # the model over L with the same a2-class as C
    E1 = None
    for a in (0, 1):
        cand = EllipticCurve(L, [1, a, 0, 0, b1])
        if cand.is_isomorphic(C):
            E1 = cand; res["(c) E1 model a2"] = a
    assert E1 is not None
    # image of a point: order preserved
    n1 = nL
    assert E1.random_point() * n1 == E1(0)
    def frob1(P):
        if P.is_zero(): return P
        return E1(P[0]^(2^m), P[1]^(2^m))
    # collect l-torsion of E1(L)
    lpts = []; has_l2 = False
    for _ in range(12):
        R = E1.random_point() * (n1 // l^vl)
        Rl = R
        # order of R is l^e
        e = 0
        while not Rl.is_zero():
            Rl = Rl * l; e += 1
        if e >= 2: has_l2 = True
        if e >= 1:
            lpts.append(R * l^(e-1))
    res["(c) E1(F_q^ext) has a point of order l^2"] = has_l2
    res["(c) all sampled l-torsion points pairwise Weil-trivial (one line)"] = all(A.weil_pairing(B, l) == 1 for A in lpts for B in lpts)
    Pasc = lpts[0]
    res["(c) pi(Pasc) = eig*Pasc"] = bool(frob1(Pasc) == int(eig)*Pasc)
    res["(c) j(E1/<Pasc>)"] = str(E1.isogeny(Pasc).codomain().j_invariant())
    assert res["(c) j(E1/<Pasc>)"] == "1"
    # (d) field of definition of the kernel point / its x-coordinate over F_q
    x0 = Pasc[0]; y0 = Pasc[1]
    kx = next(k for k in range(1, ext+1) if x0^(2^(m*k)) == x0)
    kp = next(k for k in range(1, 2*ext+1) if (x0^(2^(m*k)) == x0 and y0^(2^(m*k)) == y0))
    res["(d) degree over F_q of x(Pasc)"] = int(kx); res["(d) degree over F_q of Pasc (point, within L)"] = int(kp)
    res["(d) predicted x-degree = min k with eig^k = +-1"] = int(next(k for k in range(1, l) if eig^k in (Fl(1), Fl(-1))))
    res["time_s"] = round(time.time() - T, 1)
    for k, v in res.items(): print(f"  {k}: {v}")
    return res

print("== inert case m=37, l=73 (analogue of p) =="); sys.stdout.flush()
results["inert_m37_l73"] = run_case(37, 73, True)
print("== split case m=11, l=23 (analogue of 263) =="); sys.stdout.flush()
results["split_m11_l23"] = run_case(11, 23, False)
json.dump(results, open("raw/toy_volcano.json", "w"), indent=1, default=str)
print("ALL TOY CHECKS DONE")
