"""G1 (e): recompute red-team RT0-1 (adding zeta_r to <-1,tau>) and RT0-9 (tau-adic low-weight MITM),
with independent code (cvp2d.py CVP + own TNAF)."""
import sys, json, math
sys.path.insert(0, '.')
from cvp2d import NormLattice
from gmpy2 import mpz, powmod
from math import comb, log2, lcm, gcd
N = mpz(680564733841876926932320129493409985129); s = mpz(196511074115861092422032515080945363956)
G = mpz(17)
LK = NormLattice(1)

def tnaf(r0, r1):
    """tau-adic NAF of r0 + r1*tau, tau^2 + tau + 2 = 0 (mu = -1). Returns digit list (LSB first)."""
    r0, r1 = int(r0), int(r1)
    out = []
    while r0 != 0 or r1 != 0:
        if r0 & 1:
            u = 2 - ((r0 - 2 * r1) % 4)
            r0 -= u
        else:
            u = 0
        out.append(u)
        r0, r1 = r1 - r0 // 2, -(r0 // 2)   # divide by tau: (r0 + r1 tau)/tau = r1 + mu*r0/2 - (r0/2) tau, mu = -1
    return out

def tau_eval(digits):
    a, b = 0, 0   # value = a + b tau ; Horner from the top: v = v*tau + d
    for d in reversed(digits):
        a, b = -2 * b + d, a - b
    return a, b

def check_tnaf(a, b):
    ds = tnaf(a, b)
    assert tau_eval(ds) == (int(a), int(b)), 'TNAF reconstruct failed'
    for i in range(len(ds) - 1):
        assert not (ds[i] != 0 and ds[i + 1] != 0), 'TNAF adjacency'
    return len(ds), sum(1 for d in ds if d)

U = set()
for k in range(131):
    U.add(int(powmod(s, k, N))); U.add(int((-powmod(s, k, N)) % N))
assert len(U) == 262

def mult_order(e):
    e = mpz(e)
    o = N - 1
    for pr, ex in [(2, 3), (3, 1), (11, 1), (109, 1), (131, 1), (263, 1), (32326729, 1), (21234899465981031419669, 1)]:
        for _ in range(ex):
            if powmod(e, o // pr, N) == 1:
                o //= pr
            else:
                break
    return int(o)

res = {'RT0_1': [], 'RT0_9': {}}
# ---------------- RT0-1 ----------------
for r in (3, 4, 8, 11, 109, 263, 393):
    M = lcm(262, r)
    cf = M // 262
    hM = powmod(G, (N - 1) // M, N)       # generator of H_r = <-1, s, zeta_r>, order M
    # (i) red-team style: min-norm element over eigenvalues of exact order r
    hr = powmod(G, (N - 1) // r, N)
    best_r = None
    for k in range(1, r):
        if gcd(k, r) != 1:
            continue
        v, x, y, _ = LK.cvp(powmod(hr, k, N))
        if best_r is None or v < best_r[0]:
            best_r = (int(v), int(x), int(y), k)
    L_r, w_r = check_tnaf(best_r[1], best_r[2])
    net_rt = 0.5 * log2(cf) - log2(1 + (cf - 1) * w_r)
    # (ii) all of H_r \ U, grouped by coset of U : per-coset min norm and min TNAF weight among coset minima
    cos = {}
    z = mpz(1)
    for k in range(M):
        zi = int(z)
        if zi not in U:
            key = int(powmod(z, 262, N))   # identifies the coset zU (x -> x^262 kills U, injective on H_r/U)
            v, x, y, _ = LK.cvp(z)
            L_, w_ = check_tnaf(x, y)
            c = cos.setdefault(key, {'min_norm': None, 'min_w': None, 'n': 0})
            c['n'] += 1
            if c['min_norm'] is None or v < c['min_norm'][0]:
                c['min_norm'] = (int(v), int(x), int(y), L_, w_)
            if c['min_w'] is None or w_ < c['min_w'][0]:
                c['min_w'] = (w_, int(v), int(x), int(y), L_)
        z = z * hM % N
    assert len(cos) == cf - 1 and all(c['n'] == 262 for c in cos.values())
    sum_minw = sum(c['min_w'][0] for c in cos.values())
    net_best_coset = 0.5 * log2(cf) - log2(1 + sum_minw)
    gen_minw = min(c['min_w'][0] for c in cos.values())
    min_norm_H = min(c['min_norm'][0] for c in cos.values())
    row = {'r': r, 'class_factor': cf, 'H_order': M,
           'exact_order_r_min_norm_log2': log2(best_r[0]), 'exact_order_r_argmin_ab': [str(best_r[1]), str(best_r[2])],
           'tnaf_len': L_r, 'tnaf_weight': w_r,
           'net_log2_gain_rt_model': net_rt,
           'rt_model': '0.5*log2(cf) - log2(1 + (cf-1)*w), w = TNAF weight of min-norm element of exact order r',
           'coset_min_norm_log2_over_H_minus_U': log2(min_norm_H),
           'min_tnaf_weight_over_coset_minima': gen_minw,
           'sum_over_cosets_of_min_weight': sum_min_w if False else sum_minw,
           'net_log2_gain_best_coset_weights': net_best_coset,
           'net_log2_gain_if_w31': 0.5 * log2(cf) - log2(1 + (cf - 1) * 31),
           'net_log2_gain_if_1_add_per_image': 0.5 * log2(cf) - log2(1 + (cf - 1) * 1)}
    res['RT0_1'].append(row)
    print(r, cf, round(log2(best_r[0]), 4), L_r, w_r, round(net_rt, 4), 'coset-best', gen_minw, round(net_best_coset, 4), 'Hmin', round(log2(min_norm_H), 3))
# ---------------- RT0-9 ----------------
n = 131
cnt = {w: comb(n, w) * 2 ** w for w in range(0, 60)}
wmin = min(w for w in cnt if cnt[w] >= N)
wmin_cum = min(w for w in cnt if sum(cnt[j] for j in range(w + 1)) >= N)
rows = []
for w in (wmin - 1, wmin, wmin + 2, wmin + 4):
    w1, w2 = w // 2, w - w // 2
    L1 = comb(65, w1) * 2 ** w1; L2 = comb(66, w2) * 2 ** w2
    L1b = comb(66, w1) * 2 ** w1; L2b = comb(65, w2) * 2 ** w2
    half = max(L1, L2)
    p_split = comb(65, w1) * comb(66, w2) / comb(131, w)   # a fixed rotation splits weight exactly (w1 | w2)
    rows.append({'w': w, 'log2_count_weight_w': log2(cnt[w]),
                 'P_random_k_has_weight_w_rep_heur': 1 - math.exp(-cnt[w] / int(N)),
                 'log2_list_first65_w1': log2(L1), 'log2_list_last66_w2': log2(L2),
                 'log2_list_alt_66_w1': log2(L1b), 'log2_list_alt_65_w2': log2(L2b),
                 'log2_half_list_max': log2(half),
                 'log2_time_131_rotations_x_maxlist': log2(half) + log2(131),
                 'log2_time_131_rotations_x_sumlists': log2(L1 + L2) + log2(131),
                 'P_fixed_rotation_splits_evenly': p_split,
                 'log2_time_expected_rotations_x_sumlists': log2(L1 + L2) + log2(1 / p_split),
                 'log2_memory_entries': log2(min(L1, L2))})
res['RT0_9'] = {'w_min_count_ge_N': wmin, 'w_min_cumulative_ge_N': wmin_cum,
                'log2_count_w_min_minus_1': log2(cnt[wmin - 1]), 'rows': rows,
                'log2_rho_E0_sqrt_piN_over_4x131': 0.5 * log2(math.pi * int(N) / (4 * 131)),
                'log2_sqrt_N_over_262': 0.5 * log2(int(N) / 262)}
for rrow in rows:
    print(rrow['w'], round(rrow['log2_count_weight_w'], 4), round(rrow['log2_list_first65_w1'], 4), round(rrow['log2_list_last66_w2'], 4),
          round(rrow['log2_half_list_max'], 4), round(rrow['log2_time_131_rotations_x_maxlist'], 4), round(rrow['log2_time_expected_rotations_x_sumlists'], 4))
print('wmin', wmin, 'wmin_cum', wmin_cum, res['RT0_9']['log2_rho_E0_sqrt_piN_over_4x131'], res['RT0_9']['log2_sqrt_N_over_262'])
json.dump(res, open('rt0_recompute.json', 'w'), indent=1)
# ---- RT0-9 refinement: store one half-list once (independent of Q), iterate the other for each of the 131 rotations.
# For a weight-w length-131 cyclic string, a window of n1 consecutive positions holding exactly w1 nonzeros exists
# for some rotation whenever w1 in {floor(w*n1/131), ceil(w*n1/131)} (window count moves by <=1 per shift).
opt = []
for w in (30, 31, 32, 33):
    best = None
    for n1 in range(1, 131):
        for w1 in {(w * n1) // 131, -((-w * n1) // 131)}:
            if not (0 <= w1 <= w):
                continue
            small = comb(n1, w1) * 2 ** w1          # re-enumerated for each rotation (depends on Q)
            big = comb(131 - n1, w - w1) * 2 ** (w - w1)  # stored once
            t = big + 131 * small
            if best is None or t < best[0]:
                best = (t, n1, w1, big, small)
    t, n1, w1, big, small = best
    opt.append({'w': w, 'best_n1': n1, 'best_w1': w1, 'log2_time': log2(t), 'log2_memory_stored_list': log2(big),
                'log2_per_rotation_list': log2(small), 'P_success_heur': 1 - math.exp(-cnt[w] / int(N))})
    print('opt', opt[-1])
# the red-team's own split: small = C(65,15)2^15 iterated 131 times, big = C(66,16)2^16 stored
rt_split = comb(66, 16) * 2 ** 16 + 131 * comb(65, 15) * 2 ** 15
res['RT0_9']['rt_split_total_log2_time'] = log2(rt_split)
res['RT0_9']['rt_split_memory_log2'] = log2(comb(66, 16) * 2 ** 16)
res['RT0_9']['optimised_split'] = opt
print('rt split total', log2(rt_split), 'memory', log2(comb(66, 16) * 2 ** 16))
json.dump(res, open('rt0_recompute.json', 'w'), indent=1)
