# Red team 2, script 3: quick numbers for the remaining attack ideas.
import json
q = 2^131
tk = [2, -1]
for k in range(2, 132): tk.append(-tk[-1] - 2*tk[-2])
t = tk[131]; N = (q + 1 - t)//4; f = isqrt((t^2 - 4*q)//(-7)); p = f//263
s = 196511074115861092422032515080945363956   # tau eigenvalue on E0[N] (ground truth meta)
assert (s^2 + s + 2) % N == 0 and power_mod(s, 131, N) == 1
out = {}
# ---- (a) E0's own small-norm endomorphisms: eigenvalue orders (horizontal l-endomorphisms, l split) ----
K.<w> = NumberField(x^2 - x + 2)      # w = (1+sqrt(-7))/2 ; tau = w - 1 satisfies tau^2+tau+2=0
tau = w - 1
assert tau^2 + tau + 2 == 0
# eigenvalue map O_K -> F_N sending tau -> s
def ev(alpha):
    u, v = alpha.vector()           # alpha = u + v*w = (u+v) + v*tau
    return Mod(ZZ(u + v) + ZZ(v)*s, N)
Nm1 = factor(N - 1)
def order_mod_N(z):
    return z.multiplicative_order()
rows = []
for l in [11, 23, 29, 37, 43, 263]:
    I = K.ideal(l).factor()[0][0]
    g = I.gens_reduced()[0]
    for a in [g, g.conjugate()]:
        o = order_mod_N(ev(a))
        rows.append(dict(norm=int(a.norm()), elt=str(a), log2_eig_order=float(log(o, 2))))
out['E0_small_norm_endo_eigen_orders'] = rows
# ---- (b) canonicalisation cost inequality for an endomorphism class of size r with eval cost c (in adds) ----
# speed-up factor = sqrt(r) / (1 + r*c) (need all r images to pick a canonical rep); gain iff c < (sqrt(r)-1)/r.
def gain(r, c): return float(sqrt(r)/(1 + r*c))
out['canon_gain_r131_c_1e-2'] = gain(131, 0.01); out['canon_gain_r131_c_1'] = gain(131, 1.0)
out['canon_breakeven_c_r131'] = float((sqrt(131)-1)/131)
# heuristic norm needed for sigma^k o (horizontal chain) to hit an eigenvalue in <+-s> (262 values) on a
# level-c curve: #{alpha in O_c of shape 2^k * m, m <= X} ~ 131 * X / h(O_c); need that * 262/N >= 1
for c, h in [(263, 262), (p, p+1), (263*p, 262*(p+1))]:
    X = N * h / (131 * 262)
    # cheapest chain of total degree X built from l = 11 steps: log_11 X steps, each >= ~11*10 F_q mults
    steps = float(log(X, 11)); cost_M = steps * 11 * 10
    out['needed_chain_norm_log2_level_%s' % c] = float(log(X, 2))
    out['chain_eval_cost_M_level_%s' % c] = cost_M
    out['chain_gain_level_%s' % c] = gain(262, cost_M/6.0)   # one rho add ~ 6 M
# ---- (c) building a level-p / 263p curve by random search (a2=0, Tr(b)=1 forced) ----
class_size = 263*(p + 2)
out['class_size'] = str(class_size); out['class_size_log2'] = float(log(class_size, 2))
dens = class_size / 2^130
out['random_search_hit_log2'] = float(log(dens, 2))
# cheapest test per candidate: one scalar multiplication by 4N (~131 doublings + ~65 adds, ~6 M each)
test_M = (131 + 65) * 6
out['random_search_cost_log2_M'] = float(log(test_M / dens, 2))
out['E0_rho_cost_log2_M'] = float(log(sqrt(pi*N/524) * 6, 2))
# ---- (d) pairings / anomalous ----
out['mu_2power_in_char2'] = 'x^(2^k) - 1 = (x - 1)^(2^k) in char 2: only the trivial 2-power root of unity'
out['gcd(N, 263*p*2)'] = int(gcd(N, 2*263*p))
out['N_mod_263'] = int(N % 263); out['N_mod_131'] = int(N % 131); out['q_mod_263'] = int(q % 263); out['t_mod_263'] = int(t % 263)
# ---- (e) Cheon: needs g^(x^d); Frobenius only provides [s]Q = x*(sP) (known multiplier) ----
out['N_minus_1_smooth_part_log2'] = float(log(prod(l^e for l, e in factor(N-1) if l < 2^40), 2))
out['N_plus_1_smooth_part_log2'] = float(log(prod(l^e for l, e in factor(N+1) if l < 2^40), 2))
json.dump(out, open('/Volumes/SSD990/ecdlp-hardness-work/redteam-2/raw/rt3_misc.json', 'w'), indent=1, default=str)
for k, v in out.items(): print(k, ':', v)
