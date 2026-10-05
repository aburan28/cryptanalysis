"""Driver for cvpsweep.c. Usage: sage -python sweep_c.py MODE M FLAGLOG2 [NTHREADS]
MODE = lt20 (3<=d<2^20 plus d=1,2) or 20to32 (2^20<=d<2^32); M = 1 or 263."""
import sys, json, math, subprocess, random, time
sys.path.insert(0, '.')
from gmpy2 import mpz, powmod, invert
from cvp2d import NormLattice
mode, m, flog = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
nth = int(sys.argv[4]) if len(sys.argv) > 4 else 14
C = json.load(open('constants.json'))
B = json.load(open('basis_pari.json'))[str(m)]
N = mpz(680564733841876926932320129493409985129)
G = mpz(17)
R192 = mpz(2) ** 192
PR = [2, 3, 11, 109, 131, 263, 32326729, 21234899465981031419669]
g11, g22, g12 = int(B['g11']), int(B['g22']), int(B['g12x2']) / 2.0
A1, A2 = mpz(B['A1']), mpz(B['A2'])
# window for k2 (see cvp2d.py docstring): |k2-u2| <= sqrt(r_babai / Q(b2*))
rb = (math.sqrt(g11) + math.sqrt(g22)) ** 2 / 4
qb2s = g22 - g12 * g12 / g11
W = int(math.ceil(math.sqrt(rb / qb2s))) + 1
hexs = lambda v: format(int(v), 'x')
# Montgomery self-test against gmpy2
tests = [(mpz(random.randrange(int(N))), mpz(random.randrange(int(N)))) for _ in range(20000)]
tests += [(N - 1, N - 1), (mpz(0), N - 1), (mpz(1), mpz(1))]
inp = '%s 1 %r %r %r %d %r\n' % (hexs(N), float(g11), g12, float(g22), W, flog) + ''.join('%s %s\n' % (hexs(a), hexs(b)) for a, b in tests)
outp = subprocess.run(['./cvpsweep', '--selftest'], input=inp.encode(), capture_output=True, check=True).stdout.decode().split()
Rinv = invert(R192, N)
bad = sum(1 for (a, b), o in zip(tests, outp) if mpz(int(o, 16)) != (a * b * Rinv) % N)
assert bad == 0 and len(outp) == len(tests), ('montgomery selftest failed', bad)
if mode == 'lt20':
    divs = [d for d in C['divisors_lt_2^20']]
    CH = 1 << 16
else:
    divs = C['divisors_2^20_to_2^32']
    CH = 1 << 24
jobs = []
for d in divs:
    h = powmod(G, (N - 1) // d, N)
    hm = (h * R192) % N
    pr = [p for p in PR if d % p == 0]
    for k0 in range(0, d, CH):
        k1 = min(d, k0 + CH)
        z0 = powmod(h, k0, N)
        jobs.append('%d %d %d %d %s %s %s %s' % (d, k0, k1, len(pr), ' '.join(map(str, pr)), hexs(z0 * A1 % N), hexs(z0 * A2 % N), hexs(hm)))
t0 = time.time()
inp = '%s %d %r %r %r %d %r\n' % (hexs(N), nth, float(g11), g12, float(g22), W, flog) + '\n'.join(jobs) + '\n'
res = subprocess.run(['./cvpsweep'], input=inp.encode(), capture_output=True, check=True).stdout.decode().splitlines()
elapsed = time.time() - t0
per_d = {}; flags = []; nflags = None
for line in res:
    f = line.split()
    if f[0] == 'J':
        d, k0, k1, cnt, ml, ak = int(f[1]), int(f[2]), int(f[3]), int(f[4]), float(f[5]), int(f[6])
        e = per_d.setdefault(d, {'count': 0, 'min_log2_float': None, 'argk': None, 'hist': {}})
        e['count'] += cnt
        if cnt and (e['min_log2_float'] is None or ml < e['min_log2_float']):
            e['min_log2_float'], e['argk'] = ml, ak
        for kv in f[7:]:
            b, c = kv.split(':'); e['hist'][int(b)] = e['hist'].get(int(b), 0) + int(c)
    elif f[0] == 'F':
        flags.append((int(f[1]), int(f[2]), float(f[3])))
    elif f[0] == 'NFLAGS':
        nflags = int(f[1])
# exact re-verification of every per-d argmin and every flagged zeta with cvp2d (exact integers)
L = NormLattice(m)
def exact(d, k):
    h = powmod(G, (N - 1) // d, N)
    z = powmod(h, k, N)
    v, x, y, ties = L.cvp(z)
    return int(v), int(x), int(y), int(z)
maxdev = 0.0
for d, e in per_d.items():
    v, x, y, z = exact(d, e['argk'])
    e['exact_norm_at_argk'] = str(v); e['exact_log2'] = math.log2(v); e['argmin_xy'] = [str(x), str(y)]
    e['zeta'] = str(z)
    maxdev = max(maxdev, abs(math.log2(v) - e['min_log2_float']))
fl_ex = []
for d, k, lf in flags:
    v, x, y, z = exact(d, k)
    maxdev = max(maxdev, abs(math.log2(v) - lf))
    fl_ex.append({'d': d, 'k': k, 'log2_float': lf, 'exact_norm': str(v), 'log2_exact': math.log2(v), 'xy': [str(x), str(y)]})
tot = sum(e['count'] for e in per_d.values())
gmin_d = min((e['exact_log2'], d) for d, e in per_d.items() if d >= 3)
out = {'mode': mode, 'm': m, 'W': W, 'flag_log2': flog, 'n_jobs': len(jobs), 'elapsed_c_s': elapsed, 'total_zetas': tot,
       'n_flagged': nflags, 'max_abs_dev_log2_float_vs_exact': maxdev,
       'global_min_d_ge_3': {'log2': gmin_d[0], 'd': gmin_d[1], 'argk': per_d[gmin_d[1]]['argk'],
                             'xy': per_d[gmin_d[1]]['argmin_xy'], 'norm': per_d[gmin_d[1]]['exact_norm_at_argk']},
       'per_d': {str(d): {kk: (vv if kk != 'hist' else {str(b): c for b, c in sorted(vv.items())}) for kk, vv in e.items()} for d, e in sorted(per_d.items())},
       'flagged': sorted(fl_ex, key=lambda r: r['log2_exact'])}
fn = 'sweep_c_%s_m%d.json' % (mode, m)
json.dump(out, open(fn, 'w'), indent=0)
print(fn, 'jobs', len(jobs), 'zetas', tot, 'c_time', round(elapsed, 1), 'W', W, 'nflags', nflags, 'maxdev', maxdev)
print('global min d>=3', out['global_min_d_ge_3'])
