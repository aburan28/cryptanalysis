# Driver for weightenum.c : exhaustive low-weight tau-adic strings with eigenvalue order dividing L32.
import sys, json, subprocess, time, random, math
from gmpy2 import mpz, powmod
N = mpz(680564733841876926932320129493409985129); s = mpz(196511074115861092422032515080945363956)
wmax = int(sys.argv[1]); nth = int(sys.argv[2]) if len(sys.argv) > 2 else 14
L32 = 2**3 * 3 * 11 * 109 * 131 * 263 * 32326729
assert (N - 1) % L32 == 0
C = json.load(open('constants.json'))
assert all(L32 % d == 0 for d in C['divisors_lt_2^20'] + C['divisors_2^20_to_2^32'])
R = mpz(2) ** 192
hx = lambda v: format(int(v), 'x')
# planted tests: small-order elements must pass, random must fail
planted = []
for d in (3, 4, 131, 263, 32326729, 4234801499):
    planted.append((hx(powmod(17, (N - 1) // d, N)), 1))
for _ in range(20):
    planted.append((hx(random.randrange(2, int(N) - 1)), 0))
inp = '%s %d %d %d\n' % (hx(N), L32, wmax, nth) + '\n'.join(hx(powmod(s, i, N)) for i in range(131)) + '\n'
inp += '%s %s\n' % (hx(R * R % N), hx(R % N)) + ' '.join(p for p, _ in planted) + ' END\n'
t0 = time.time()
r = subprocess.run(['./weightenum'], input=inp.encode(), capture_output=True, check=True)
el = time.time() - t0
lines = r.stdout.decode().splitlines()
tests = [l.split() for l in lines if l.startswith('T ')]
planted_ok = all(int(t[2]) == exp for t, (_, exp) in zip(tests, planted)) and len(tests) == len(planted)
counts = {l.split()[1]: int(l.split()[2].split('=')[1]) for l in lines if l.startswith('C ')}
surv = [l for l in lines if l.startswith('S ')]
# exact analysis of survivors
def order(e):
    o = N - 1
    for pr, ex in [(2, 3), (3, 1), (11, 1), (109, 1), (131, 1), (263, 1), (32326729, 1), (21234899465981031419669, 1)]:
        for _ in range(ex):
            if powmod(e, o // pr, N) == 1: o //= pr
            else: break
    return int(o)
sv = []
for l in surv:
    f = l.split()[2:]
    e = mpz(0)
    for t in f:
        sg = 1 if t[0] == '+' else -1; e += sg * powmod(s, int(t[1:]), N)
    sv.append({'string': f, 'order': order(e % N)})
out = {'wmax': wmax, 'L32': L32, 'elapsed_s': el, 'planted_tests_ok': planted_ok, 'counts_normalised_strings': counts,
       'expected_counts': {'w=%d' % w: math.comb(130, w - 1) * 2 ** (w - 1) for w in range(2, wmax + 1)},
       'survivors': sv, 'stderr': r.stderr.decode()}
json.dump(out, open('weightenum_w%d.json' % wmax, 'w'), indent=1)
print(json.dumps(out, indent=1)[:3000])
