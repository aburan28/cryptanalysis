"""Extra: exact CVP sweep (orders 3 <= d < 2^20) for the orders O_p = Z + p O_K and O_f = Z + 263p O_K = Z[pi]
(the End rings at volcano levels p and 263p), plus their minimum non-scalar degree."""
import sys, json, time, math
from multiprocessing import Pool
sys.path.insert(0, '.')
from cvp2d import NormLattice, N_ORDER
from gmpy2 import mpz, powmod, gcd
N = mpz(N_ORDER); G = 17
p = 146505763881528721
MS = {'O_p': p, 'O_263p': 263 * p}
DIVS = [d for d in json.load(open('constants.json'))['divisors_lt_2^20'] if d >= 3]
LAT = {}
def work(item):
    name, d, h, k0, k1 = item
    if name not in LAT:
        LAT[name] = NormLattice(MS[name])
    Lt = LAT[name]
    h = mpz(h); z = powmod(h, k0, N)
    best = None; cnt = 0
    for k in range(k0, k1):
        if gcd(k, d) == 1:
            v, x, y, t = Lt.cvp(z)
            cnt += 1
            if best is None or v < best[0]:
                best = (int(v), int(x), int(y), k)
        z = z * h % N
    return name, d, cnt, best
if __name__ == '__main__':
    t0 = time.time()
    items = []
    for name in MS:
        for d in DIVS:
            h = int(powmod(mpz(G), (N - 1) // d, N))
            for k0 in range(0, d, 20000):
                items.append((name, d, h, k0, min(d, k0 + 20000)))
    agg = {}
    with Pool(13) as pool:
        for name, d, cnt, best in pool.imap_unordered(work, items):
            a = agg.setdefault(name, {}).setdefault(d, {'count': 0, 'best': None})
            a['count'] += cnt
            if best and (a['best'] is None or best[0] < a['best'][0]):
                a['best'] = best
    out = {}
    for name, m in MS.items():
        Lt = NormLattice(m)
        per = agg[name]
        gm = min((v['best'][0], d) for d, v in per.items())
        b = per[gm[1]]['best']
        # minimum non-scalar degree: min over y != 0 of x^2 - m x y + 2 m^2 y^2 ; attained at |y| = 1, x = floor(m/2) or ceil
        mn = min(x * x - m * x + 2 * m * m for x in (m // 2, m // 2 + 1))
        out[name] = {'m': str(m), 'n_eigenvalues': sum(v['count'] for v in per.values()),
                     'min_norm_log2': math.log2(gm[0]), 'min_norm': str(gm[0]), 'at_order_d': gm[1],
                     'argmin_xy_basis_1_mtau': [str(b[1]), str(b[2])],
                     'kernel_lattice_lambda1_log2': math.log2(int(Lt.Q1)), 'kernel_lattice_Q_b2_log2': math.log2(int(Lt.Q2)),
                     'min_nonscalar_degree': str(mn), 'min_nonscalar_degree_log2': math.log2(mn),
                     'per_d_log2_min': {str(d): math.log2(v['best'][0]) for d, v in sorted(per.items())}}
        print(name, out[name]['n_eigenvalues'], out[name]['min_norm_log2'], out[name]['at_order_d'], out[name]['min_nonscalar_degree_log2'])
    out['elapsed_s'] = time.time() - t0
    json.dump(out, open('sweep_levels.json', 'w'), indent=1)
