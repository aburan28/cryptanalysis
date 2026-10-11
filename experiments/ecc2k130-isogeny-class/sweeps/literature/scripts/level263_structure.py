# Checks, for every curve in the ground truth, the facts that the literature statements rely on:
#  (a) level-263 connectivity by small-degree HORIZONTAL isogenies (JMV same-level graph, Kohel Prop 23):
#      l = 2  (Kronecker congruence Phi_2 = (X^2-Y)(X-Y^2) mod 2: Frobenius / Verschiebung)
#      l = 11 (split in K, (11/263)=+1: stays in the same genus = same Frobenius orbit)
#      l = 29 (split in K, (29/263)=-1: crosses between orbits A and B)
#  (b) GHS magic number m(b) (Gaudry-Hess-Smart / Menezes-Qu) for all 263 curves
#  (c) p-isogeny kernel field degrees (why the p-levels are unreachable)
#  (d) rho iteration counts
# Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; sage -python level263_structure.py
import sys, json, time
sys.path.insert(0, '/Volumes/SSD990/ecdlp-hardness-work/ground_truth')
import ecc2k
from sage.all import (ZZ, Integer, GF, PolynomialRing, pari, Mod, factor, RealField, pi, matrix,
                      kronecker, vector)
R = RealField(100)
t0 = time.time()
K, curves = ecc2k.load()
labels = ecc2k.LABELS
jval = {lab: curves[lab].j_invariant() for lab in labels}
jinv = {jval[lab]: lab for lab in labels}
out = {'per_curve': {lab: {} for lab in labels}, 'global': {}}
PK = PolynomialRing(K, 'Y'); Y = PK.gen()

def phi_mod2(l):
    P = pari(f'polmodular({l})')          # classical modular polynomial in x,y over Z
    Rxy = PolynomialRing(GF(2), 'X,Yv')
    return Rxy(str(P).replace('x', 'X').replace('y', 'Yv'))

for l in [2, 11, 29]:
    tl = time.time()
    Phi = phi_mod2(l)
    Xv, Yv = Phi.parent().gens()
    # coefficients c_{a,b} X^a Y^b; evaluate at X = j
    terms = Phi.dict()
    shifts = {}
    for lab in labels:
        j = jval[lab]
        g = sum(K(c) * j**a * Y**b for (a, b), c in terms.items())
        rts = g.roots(multiplicities=True)
        rts_in_F = [(r, m) for r, m in rts]
        neigh = []
        for r, m in rts_in_F:
            neigh.append((jinv.get(r, 'OUTSIDE_GT'), int(m)))
        out['per_curve'][lab][f'phi{l}_rational_roots'] = neigh
        out['per_curve'][lab][f'phi{l}_degree_in_Y'] = int(g.degree())
        if lab != 'E0':
            for nb, m in neigh:
                if nb.startswith(('A', 'B')):
                    key = (lab[0], nb[0], (int(nb[1:]) - int(lab[1:])) % 131)
                    shifts[key] = shifts.get(key, 0) + 1
    out['global'][f'phi{l}_shift_pattern'] = {f'{a}->{b} shift {s}': n for (a, b, s), n in sorted(shifts.items())}
    out['global'][f'phi{l}_seconds'] = round(time.time() - tl, 1)
    print('l =', l, 'done', round(time.time() - tl, 1), 's', out['global'][f'phi{l}_shift_pattern'], flush=True)

# (b) GHS magic number m(b) = dim_F2 span{(1, sigma^i(b^{1/2})) : i = 0..130}
def ghs_m(b):
    c = b.sqrt()
    rows = []
    x = c
    for i in range(131):
        v = [1] + [int(u) for u in x.polynomial().padded_list(131)]
        rows.append(v); x = x**2
    return int(matrix(GF(2), rows).rank())
for lab in labels:
    b = curves[lab].a6()
    out['per_curve'][lab]['ghs_m'] = ghs_m(b)
    m = out['per_curve'][lab]['ghs_m']
    out['per_curve'][lab]['ghs_genus_bound'] = f'2^{m-1} or 2^{m-1}-1'
print('ghs m values:', sorted(set(v['ghs_m'] for v in out['per_curve'].values())), flush=True)

# (c) p-isogeny kernel field degrees
p = Integer(ecc2k.p); t = Integer(ecc2k.t); q = Integer(2)**131
lam = Mod(t, p) / 2
k = lam.multiplicative_order()
kx = k // 2 if (k % 2 == 0 and lam**(k // 2) == -1) else k      # Frobenius orbit length on x-coordinates
out['global']['p_plus_1_factor'] = str(factor(p + 1))
out['global']['p_minus_1_factor'] = str(factor(p - 1))
out['global']['ord_lambda_mod_p'] = str(k)
out['global']['lambda^(k/2) == -1'] = bool(k % 2 == 0 and lam**(k // 2) == -1)
out['global']['x_coord_field_degree_over_Fq'] = str(kx)
out['global']['log2_bits_one_kernel_x_coordinate'] = float((R(kx) * 131).log2())
out['global']['kernel_poly_degree'] = str((p - 1) // 2)
out['global']['kernel_poly_irreducible_factors'] = str(((p - 1) // 2) // kx)
out['global']['log2_bits_kernel_polynomial'] = float((R((p - 1) // 2) * 131).log2())
# same for 263
lam263 = Mod(t, 263) / 2
out['global']['lambda_mod_263'] = int(lam263.lift())
# (d) rho iteration counts (log2)
Nn = R(ecc2k.N)
out['global']['log2_rho_neg_frob'] = float((R(pi) * Nn / (4 * 131)).sqrt().log2())
out['global']['log2_rho_neg_frob_BBB_walk_factor_1.069993'] = float(((R(pi) * Nn / (4 * 131)).sqrt() * R('1.069993')).log2())
out['global']['log2_rho_certicom_style_pi2^131/(2*2*4*131)'] = float((R(pi) * R(2)**131 / (2 * 2 * 4 * 131)).sqrt().log2())
out['global']['log2_rho_neg_only'] = float((R(pi) * Nn / 4).sqrt().log2())
# probability that a uniformly random F_q-isomorphism class of ordinary curves lies in levels p or 263p
H = 1 + 262 + (p + 1) + 262 * (p + 1)
out['global']['hurwitz_class_number_sum'] = str(H)
out['global']['log2_prob_random_curve_in_p_levels'] = float((R(263 * (p + 1)) / (2 * (q - 1))).log2())
out['global']['seconds_total'] = round(time.time() - t0, 1)
json.dump(out, open('/Volumes/SSD990/ecdlp-hardness-work/literature/raw/level263_structure.json', 'w'), indent=1)
print(json.dumps(out['global'], indent=1))
