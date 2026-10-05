"""G1 (a)+(b): exact CVP sweep over every eigenvalue zeta of exact order d, d | N-1, d < 2^20,
for O_263 (m=263) and O_K (m=1). Independent code (cvp2d.py). zeta = h_d^k, h_d = 17^((N-1)/d), gcd(k,d)=1."""
import sys, json, time, math
from multiprocessing import Pool
sys.path.insert(0, '.')
from cvp2d import NormLattice, N_ORDER, S_EIGEN
from gmpy2 import mpz, powmod, gcd

N = mpz(N_ORDER); s = mpz(S_EIGEN)
G = 17  # primitive root mod N (Sage multiplicative_generator), re-checked below
DIVS = json.load(open('constants.json'))['divisors_lt_2^20']
LAT = {}

def lat(m):
    if m not in LAT:
        LAT[m] = NormLattice(m)
    return LAT[m]

def tau_powers():
    """(x,y) coordinates of +-tau^j in basis (1,tau), j = 0..300, and their norms 2^j."""
    a, b = 1, 0
    out = {}
    for j in range(0, 301):
        out[(a, b)] = ('+', j)
        out[(-a, -b)] = ('-', j)
        a, b = -2 * b, a - b   # tau*(a+b tau) = a tau + b(-tau-2)
    return out
TAUP = tau_powers()
T100 = mpz(2) ** 100

def work(item):
    d, h, k0, k1 = item
    h = mpz(h)
    z = powmod(h, k0, N)
    res = {}
    for m in (263, 1):
        res[m] = {'min': None, 'arg': None, 'k': None, 'ties_at_min': 0, 'hist': {}, 'count': 0,
                  'nontau_min': None, 'nontau_arg': None, 'nontau_k': None, 'below2_100': [],
                  'tau_cosets': [], 'maxQ': None}
    L263 = lat(263); L1 = lat(1)
    for k in range(k0, k1):
        if gcd(k, d) == 1:
            for m, L in ((263, L263), (1, L1)):
                v, x, y, ties = L.cvp(z)
                r = res[m]
                r['count'] += 1
                bl = int(v).bit_length() - 1
                r['hist'][bl] = r['hist'].get(bl, 0) + 1
                if r['min'] is None or v < r['min']:
                    r['min'], r['arg'], r['k'], r['ties_at_min'] = v, (int(x), int(y)), k, ties
                if r['maxQ'] is None or v > r['maxQ']:
                    r['maxQ'] = v
                if m == 1:
                    if v < T100:
                        r['below2_100'].append((k, int(x), int(y), int(v)))
                    tp = TAUP.get((int(x), int(y)))
                    if tp is None:
                        cand, carg = v, (int(x), int(y))
                    else:
                        # coset minimum is +-tau^j; lower bound on its 2nd minimum:
                        # any other element beta has beta - alpha in L\{0}, so |beta| >= sqrt(lambda1) - |alpha|,
                        # and |beta| >= |alpha| (alpha is the minimum)
                        lam = int(L.Q1)
                        sa = math.sqrt(int(v)); sl = math.sqrt(lam)
                        lb2 = max(int(v), int(math.floor((sl - sa) ** 2 * (1 - 1e-12)))) if sl > sa else int(v)
                        r['tau_cosets'].append((k, tp[0], tp[1], int(v), lb2))
                        cand, carg = mpz(lb2), None
                    if r['nontau_min'] is None or cand < r['nontau_min']:
                        r['nontau_min'], r['nontau_arg'], r['nontau_k'] = cand, carg, k
        z = (z * h) % N
    for m in res:
        for key in ('min', 'nontau_min', 'maxQ'):
            if res[m][key] is not None:
                res[m][key] = int(res[m][key])
    return d, res

def main():
    t0 = time.time()
    # sanity: 17 is a primitive root mod N
    from sage.all import factor, Integer
    for pp, e in factor(Integer(N_ORDER) - 1):
        assert powmod(mpz(G), (N - 1) // int(pp), N) != 1
    items = []
    CH = 20000
    hs = {}
    for d in DIVS:
        h = powmod(mpz(G), (N - 1) // d, N)
        hs[d] = int(h)
        for k0 in range(0, d, CH):
            items.append((d, int(h), k0, min(d, k0 + CH)))
    agg = {}
    with Pool(13) as pool:
        for d, res in pool.imap_unordered(work, items, chunksize=1):
            A = agg.setdefault(d, {})
            for m, r in res.items():
                a = A.setdefault(m, {'min': None, 'arg': None, 'k': None, 'ties_at_min': 0, 'hist': {}, 'count': 0,
                                     'nontau_min': None, 'nontau_arg': None, 'nontau_k': None,
                                     'below2_100': [], 'tau_cosets': [], 'maxQ': None})
                a['count'] += r['count']
                for b, c in r['hist'].items():
                    a['hist'][b] = a['hist'].get(b, 0) + c
                if r['min'] is not None and (a['min'] is None or r['min'] < a['min']):
                    a['min'], a['arg'], a['k'], a['ties_at_min'] = r['min'], r['arg'], r['k'], r['ties_at_min']
                if r['maxQ'] is not None and (a['maxQ'] is None or r['maxQ'] > a['maxQ']):
                    a['maxQ'] = r['maxQ']
                if r['nontau_min'] is not None and (a['nontau_min'] is None or r['nontau_min'] < a['nontau_min']):
                    a['nontau_min'], a['nontau_arg'], a['nontau_k'] = r['nontau_min'], r['nontau_arg'], r['nontau_k']
                a['below2_100'] += r['below2_100']
                a['tau_cosets'] += r['tau_cosets']
    out = {'N': str(N_ORDER), 's': str(S_EIGEN), 'generator': G, 'elapsed_s': time.time() - t0,
           'h_d': {str(d): str(h) for d, h in hs.items()}, 'per_d': {}}
    for d in sorted(agg):
        out['per_d'][str(d)] = {}
        for m in (263, 1):
            a = agg[d][m]
            e = {'count': a['count'], 'min': str(a['min']), 'log2_min': math.log2(a['min']), 'argmin_xy': [str(a['arg'][0]), str(a['arg'][1])],
                 'argmin_k': a['k'], 'ties_at_min': a['ties_at_min'], 'log2_maxmin': math.log2(a['maxQ']),
                 'hist_floorlog2': {str(b): c for b, c in sorted(a['hist'].items())}}
            if m == 1:
                e['nontau_min'] = str(a['nontau_min']); e['log2_nontau_min'] = math.log2(a['nontau_min'])
                e['nontau_argmin_xy'] = None if a['nontau_arg'] is None else [str(a['nontau_arg'][0]), str(a['nontau_arg'][1])]
                e['nontau_argmin_k'] = a['nontau_k']
                e['below2_100'] = [[k, str(x), str(y), str(v)] for k, x, y, v in sorted(a['below2_100'])]
                e['tau_cosets'] = [[k, sg, j, str(v), str(lb)] for k, sg, j, v, lb in sorted(a['tau_cosets'])]
            out['per_d'][str(d)]['O263' if m == 263 else 'OK'] = e
    json.dump(out, open('sweep_py.json', 'w'), indent=0)
    print('done', time.time() - t0)

if __name__ == '__main__':
    main()
