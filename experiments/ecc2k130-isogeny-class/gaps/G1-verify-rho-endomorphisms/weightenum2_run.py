# weightenum2 driver: MODE=input W NTH -> writes weightenum2_w{W}.in ; MODE=analyze W -> reads weightenum2_w{W}.out
import sys, json, math, random
from gmpy2 import mpz, powmod
N = mpz(680564733841876926932320129493409985129); s = mpz(196511074115861092422032515080945363956)
mode, wmax = sys.argv[1], int(sys.argv[2])
L32 = 2**3 * 3 * 11 * 109 * 131 * 263 * 32326729
hx = lambda v: format(int(v), 'x')
R = mpz(2) ** 192
random.seed(7)
planted = [(hx(powmod(17, (N - 1) // d, N)), 1) for d in (3, 4, 131, 263, 32326729, 4234801499)]
planted += [(hx(random.randrange(2, int(N) - 1)), 0) for _ in range(20)]
def order(e):
    o = N - 1
    for pr, ex in [(2, 3), (3, 1), (11, 1), (109, 1), (131, 1), (263, 1), (32326729, 1), (21234899465981031419669, 1)]:
        for _ in range(ex):
            if powmod(e, o // pr, N) == 1: o //= pr
            else: break
    return int(o)
def canon(string):
    items = [(int(t[1:]), 1 if t[0] == '+' else -1) for t in string]
    best = None
    for r in range(131):
        for g in (1, -1):
            c = tuple(sorted(((p + r) % 131, g * sg) for p, sg in items))
            if best is None or c < best: best = c
    return best
if mode == 'input':
    nth = int(sys.argv[3])
    inp = '%s %d %d %d\n' % (hx(N), L32, wmax, nth) + '\n'.join(hx(powmod(s, i, N)) for i in range(131)) + '\n'
    inp += '%s %s\n' % (hx(R * R % N), hx(R % N)) + ' '.join(p for p, _ in planted) + ' END\n'
    open('weightenum2_w%d.in' % wmax, 'w').write(inp)
else:
    lines = open('weightenum2_w%d.out' % wmax).read().splitlines()
    tests = [l.split() for l in lines if l.startswith('T ')]
    planted_ok = len(tests) == len(planted) and all(int(t[2]) == e for t, (_, e) in zip(tests, planted))
    counts = {}
    for l in lines:
        if l.startswith('C '):
            f = l.split(); counts[f[1]] = {'visited': int(f[2].split('=')[1]), 'skipped_at_leaf': int(f[3].split('=')[1])}
    sv = []
    for l in lines:
        if l.startswith('S '):
            f = l.split()[2:]
            e = sum((1 if t[0] == '+' else -1) * powmod(s, int(t[1:]), N) for t in f) % N
            sv.append({'string': f, 'order': order(mpz(e)), 'canon': canon(f)})
    out = {'wmax': wmax, 'L32': L32, 'planted_tests_ok': planted_ok, 'counts': counts,
           'full_space_normalised_counts': {'w=%d' % w: math.comb(130, w - 1) * 2 ** (w - 1) for w in range(2, wmax + 1)},
           'n_survivors': len(sv), 'survivor_orders': sorted(set(x['order'] for x in sv)),
           'survivors': [{'string': x['string'], 'order': x['order']} for x in sv]}
    # cross-check against the full (non-canonical) enumeration up to weight 5
    try:
        W5 = json.load(open('weightenum_w5.json'))
        full = set(canon(x['string']) for x in W5['survivors'])
        mine = set(x['canon'] for x in sv if len(x['string']) <= 5)
        out['matches_full_enumeration_w_le_5_up_to_rotation_sign'] = (full == mine)
        out['n_classes_w_le_5'] = [len(full), len(mine)]
    except FileNotFoundError:
        pass
    json.dump(out, open('weightenum2_w%d.json' % wmax, 'w'), indent=1)
    print({k: v for k, v in out.items() if k != 'survivors'})
