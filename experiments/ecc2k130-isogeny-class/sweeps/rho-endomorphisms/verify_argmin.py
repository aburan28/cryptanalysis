# Independent PARI check of the CVP argmin (O_263) and of a few table entries
import sys, json
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms")
import common_rho as C
from sage.all import pari, Integer, log
c = json.load(open("cvp_O263.json"))
N = C.N
res = {}
b = c["smallest_norm_over_all_orders_3..2^20_y_nonzero"]
x, y = b["argmin_y_nonzero_xy"]
w = C.W_O263
e = pari("Mod(%d,%d)" % ((x + y * w) % N, N))
res["argmin_norm_log2"] = float(log(Integer(x * x + x * y + 121046 * y * y), 2))
res["argmin_eigen_order_pari_znorder"] = int(pari.znorder(e))
res["argmin_norm_factored"] = str(pari.factor(x * x + x * y + 121046 * y * y))
# reduced basis vector b1: is it pi - 1 (norm 4N)?
b1 = c["reduced_basis"][0]
res["b1_norm_over_N"] = (b1[0] ** 2 + b1[0] * b1[1] + 121046 * b1[1] ** 2) / N
# pi in O_263 coordinates: pi = (t - f)/2 + f*omega  (sign check), omega = (omega_263 + 131)/263
t, f = C.t, C.f
for sgn in (1, -1):
    # pi = (t + sgn f sqrt(-7))/2 ; x + y*omega_263 with omega_263 = (1 + 263 sqrt(-7))/2 -> y = sgn f / 263 = sgn p ; x = (t - y)/2
    yy = sgn * C.p; xx = (t - yy) // 2
    ev = (xx + yy * w) % N
    res["pi_sign_%d_eigenvalue_is_1" % sgn] = ev == 1
    res["pi_sign_%d_minus1_equals_pm_b1" % sgn] = [xx - 1, yy] in ([b1[0], b1[1]], [-b1[0], -b1[1]])
print(res)
json.dump(res, open("verify_argmin.json", "w"), indent=1)
