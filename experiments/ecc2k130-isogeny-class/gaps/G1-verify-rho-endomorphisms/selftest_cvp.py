# Self-tests of cvp2d.py: (1) brute force on small moduli, (2) fpylll CVP on the real lattices, (3) wide-window check.
import random, json, sys, math
sys.path.insert(0, '.')
from cvp2d import NormLattice, S_EIGEN, N_ORDER
from sage.all import next_prime
random.seed(20260924)
res = {}
# (1) small primes Np where x^2+x+2 has a root s' mod Np; brute force all (x,y) in a big box
bad = 0; tested = 0
from sage.all import GF as _GF
for trial in range(40):
    Np = int(next_prime(random.randint(10**5, 10**6)))
    F = _GF(Np)
    R = F['X']; X = R.gen()
    rts = (X**2 + X + 2).roots(multiplicities=False)
    if not rts:
        continue
    sp = int(rts[0])
    for m in (1, 263):
        L = NormLattice(m, N=Np, s=sp)
        # brute-force bound: min norm of any coset <= Q(b2) <= ... ; enumerate box large enough
        # Q(x,y) >= (7/4) m^2 y^2 and Q >= (7/8)... use: Q(x,y) >= (7/(4*2)) * x^2? exact: Q >= 7 x^2 / (4*2)?? use generic bound below
        bound = int(L.Q2) + 1  # every coset has an element of norm <= Q(b2)
        ymax = int(math.isqrt(4 * bound // (7 * m * m))) + 1
        best = {}
        for y in range(-ymax, ymax + 1):
            # Q = (x - m y/2)^2 + 7 m^2 y^2/4 <= bound  => |x - m y/2| <= sqrt(bound)
            r = int(math.isqrt(bound)) + 1
            xc = (m * y) // 2
            for x in range(xc - r - 1, xc + r + 2):
                v = x * x - m * x * y + 2 * m * m * y * y
                if v > bound:
                    continue
                e = (x + y * int(L.c)) % Np
                if e not in best or v < best[e]:
                    best[e] = v
        for _ in range(300):
            z = random.randrange(Np)
            got = L.cvp(z)[0]
            tested += 1
            if z not in best or int(got) != best[z]:
                bad += 1
res['bruteforce_small_moduli'] = {'tested': tested, 'mismatches': bad}
print('bruteforce', tested, bad)
# (2) fpylll CVP (independent library) on the real lattices via an integral embedding
from fpylll import IntegerMatrix, CVP, LLL
bad2 = 0; tested2 = 0; worse2 = 0
for m in (1, 263):
    L = NormLattice(m)
    # embed: Q(x,y) = (x - m y/2)^2 + 7 m^2 y^2 / 4  ; scale by 2: (2x - m y, m*sqrt7*y) -> use integer approx with big scale
    # Use exact Euclidean embedding in Z^3 after scaling: 4Q = (2x - m y)^2 + 7 (m y)^2 ; realise sqrt7 via
    # the form 4Q = u^2 + 7 v^2 which is not Euclidean integral; instead check fpylll result exactly by re-evaluating Q
    SC = 2**40
    s7 = int(math.isqrt(7 * SC * SC))
    def emb(x, y):
        return [ (2 * x - m * y) * SC, m * y * s7 ]
    B = IntegerMatrix.from_matrix([emb(int(L.b1[0]), int(L.b1[1])), emb(int(L.b2[0]), int(L.b2[1]))])
    LLL.reduction(B)
    for _ in range(2000):
        z = random.randrange(N_ORDER)
        t = emb(z, 0)
        v = CVP.closest_vector(B, t)
        # recover lattice vector in (x,y): solve emb^{-1}
        vy = v[1] // (m * s7) if v[1] % (m * s7) == 0 else None
        vx = (v[0] // SC + m * vy) // 2
        ax, ay = z - vx, -vy
        assert (ax + ay * int(L.c) - z) % N_ORDER == 0
        qf = ax * ax - m * ax * ay + 2 * m * m * ay * ay
        got = int(L.cvp(z)[0])
        tested2 += 1
        if got != qf:
            bad2 += 1
        if got > qf:
            worse2 += 1
            print('CVP2D WORSE than fpylll', m, z, got, qf)
res['fpylll_cvp_real_lattices'] = {'tested': tested2, 'mismatches': bad2, 'cvp2d_worse_than_fpylll': worse2}
print('fpylll', tested2, bad2)
# (3) wide window vs default window on the real lattices
bad3 = 0; tested3 = 0
for m in (1, 263):
    L = NormLattice(m)
    for _ in range(20000):
        z = random.randrange(N_ORDER)
        a = L.cvp(z)[0]; b = L.cvp(z, window=(-12, 12))[0]
        tested3 += 1
        bad3 += (a != b)
res['wide_window'] = {'tested': tested3, 'mismatches': bad3}
print('wide', tested3, bad3)
for m in (1, 263):
    L = NormLattice(m)
    res['lattice_m%d' % m] = {'b1': [str(L.b1[0]), str(L.b1[1])], 'b2': [str(L.b2[0]), str(L.b2[1])],
                              'Q_b1': str(L.Q1), 'log2_Q_b1': math.log2(int(L.Q1)), 'log2_Q_b2': math.log2(int(L.Q2)),
                              'D': str(L.D)}
json.dump(res, open('selftest_cvp.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
