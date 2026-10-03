# G1 (a) argmin interpretation, (c) Codex psi eigenvalue order, (d) tau^k membership in O_263 and min non-scalar degree.
from sage.all import Integer, GF, pari, gcd, log, matrix, ZZ
import json, math
N = Integer(680564733841876926932320129493409985129); s = Integer(196511074115861092422032515080945363956)
p = Integer(146505763881528721); f = 263 * p
F = GF(N); S = F(s)
out = {}
def order(e):
    e = F(e)
    return int(e.multiplicative_order()) if e != 0 else None
def normK(a, b):   # norm of a + b*tau
    return a * a - a * b + 2 * b * b
# (a) claimed argmin (x, y) = (-128163312801734517, 358685138569453)
xc, yc = Integer(-128163312801734517), Integer(358685138569453)
lit = {'basis': '(1, 263*tau) [task text]', 'norm': str(normK(xc, 263 * yc)), 'log2_norm': float(log(normK(xc, 263 * yc), 2)),
       'eig_order': order(xc + 263 * yc * s)}
# basis (1, omega_263), omega_263 = (1 + 263 sqrt(-7))/2 = 132 + 263 tau
a_om, b_om = xc + 132 * yc, 263 * yc
om = {'basis': '(1, omega_263 = 132 + 263 tau)', 'norm': str(normK(a_om, b_om)), 'log2_norm': float(log(normK(a_om, b_om), 2)),
      'eig_order': order(a_om + b_om * s), 'as_1_263tau_coords': [str(a_om), str(yc)]}
mine = json.load(open('sweep_py.json'))['per_d']['315337']['O263']
out['a_claimed_argmin_interpretations'] = {'literal': lit, 'omega_basis': om, 'my_argmin_xy_1_263tau': mine['argmin_xy'],
                                           'my_min_norm': mine['min'], 'my_log2_min': mine['log2_min']}
# (c) psi = +-(774 + omega_263); sqrt(-7) = 2s+1 mod N
sq7 = F(2 * s + 1)
out['c_sqrt_minus7_check'] = bool(sq7 ** 2 == F(-7))
omega = (1 + 263 * sq7) / 2
psi = F(774) + omega
out['c_psi_eigen'] = str(psi)
out['c_psi_eq_906_plus_263s'] = bool(psi == F(906 + 263 * s))
out['c_psi_norm_906_263tau'] = int(normK(906, 263))
out['c_psi_norm_factor'] = str(Integer(normK(906, 263)).factor())
o1 = order(psi); o2 = order(-psi)
out['c_order_plus'] = str(o1); out['c_order_minus'] = str(o2)
out['c_order_plus_eq_(N-1)/3'] = bool(o1 == (N - 1) // 3); out['c_order_minus_eq_(N-1)/3'] = bool(o2 == (N - 1) // 3)
out['c_index_plus'] = str((N - 1) // o1); out['c_index_minus'] = str((N - 1) // o2)
# (d) tau^k = a_k + b_k tau
a, b = Integer(1), Integer(0)
rows = []
div263 = []
for k in range(1, 132):
    a, b = -2 * b, a - b
    if b % 263 == 0:
        div263.append(k)
    rows.append((k, a, b))
a131, b131 = rows[-1][1], rows[-1][2]
out['d_k_with_263_div_bk_1_to_131'] = div263
out['d_b131'] = str(b131); out['d_a131'] = str(a131)
out['d_b131_eq_f'] = bool(b131 == f); out['d_b131_eq_minus_f'] = bool(b131 == -f)
out['d_trace_of_tau131'] = str(2 * a131 - b131)  # tau + taubar = -1: trace(a+b tau) = 2a - b
out['d_norm_tau131_eq_2^131'] = bool(normK(a131, b131) == 2 ** 131)
out['d_tau131_eigen_is_1'] = bool(F(a131 + b131 * s) == 1)
# order of tau in (O_K/263)^*/(Z/263)^* : ratio of tau images at the two primes 123, 139
R = GF(263)
out['d_order_of_123/139_mod_263'] = int((R(123) / R(139)).multiplicative_order())
# min degree (norm) of non-scalar elements of O_263 = {x + y*263 tau}: exact by completing the square and by PARI qfminim
best = None
for y in (1, -1):
    for x in range(-2000, 2000):
        v = x * x - 263 * x * y + 2 * 263 ** 2 * y * y
        if best is None or v < best[0]:
            best = (v, x, y)
# |y| >= 2 gives norm >= (7/4)*263^2*4 = 484183 > 121046, so y = +-1 suffices
out['d_min_nonscalar_norm_bruteforce_y_pm1'] = [int(best[0]), int(best[1]), int(best[2])]
out['d_lower_bound_|y|>=2'] = float(7 / 4 * 263 ** 2 * 4)
Gm = matrix(ZZ, [[2, -263], [-263, 4 * 263 ** 2]])  # Gram of 2Q in (x,y)
qm = pari(Gm).qfminim(2 * 121046)  # all vectors with x^T G x = 2Q <= 2*121046 (one of each +-pair)
vecs = qm[2].sage()
lst = []
for j in range(vecs.ncols()):
    x, y = vecs[0, j], vecs[1, j]
    lst.append([int(x), int(y), int(x * x - 263 * x * y + 2 * 263 ** 2 * y * y)])
out['d_qfminim_count_with_signs'] = int(qm[0]); out['d_qfminim_columns'] = int(vecs.ncols())
out['d_qfminim_nonscalar_vectors_Q_le_121046'] = [v for v in lst if v[1] != 0]
out['d_qfminim_scalar_count'] = len([v for v in lst if v[1] == 0])
qm2 = pari(Gm).qfminim(2 * 121045)
V2 = qm2[2].sage()
out['d_qfminim_nonscalar_Q_le_121045'] = [[int(V2[0, j]), int(V2[1, j])] for j in range(V2.ncols()) if V2[1, j] != 0]
out['d_norm_131_plus_263tau'] = int(normK(131, 263))
out['d_norm_132_plus_263tau'] = int(normK(132, 263))
out['d_121046_factor'] = str(Integer(121046).factor())
json.dump(out, open('checks_acd.json', 'w'), indent=1)
for k, v in out.items():
    print(k, v)
