"""Check cvp_lib.OrderLattice.cvp against exhaustive enumeration on toy moduli."""
import random, math, sys, json
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms")
from cvp_lib import OrderLattice
from sympy import isprime, nextprime
rng = random.Random(7)
report = []
for (bits, c) in [(13, 121046), (15, 121046), (16, 121046), (17, 2), (19, 2), (20, 2)]:
    n = nextprime(rng.getrandbits(bits) | (1 << (bits - 1)))
    w = rng.randrange(n)
    L = OrderLattice(n, w, c)
    # exhaustive: min Q per eigenvalue over all (x,y) with Q <= X, X large enough to cover every class
    D = 4 * c - 1
    X = int(2.2 * n * math.sqrt(D))       # covering radius bound for index-n lattice (generous)
    best = {}
    ymax = math.isqrt(4 * X // D) + 1
    for y in range(-ymax, ymax + 1):
        disc = 4 * X - D * y * y
        if disc < 0:
            continue
        s = math.isqrt(disc)
        for x in range(-((y + s) // 2), (s - y) // 2 + 1):
            qv = x * x + x * y + c * y * y
            e = (x + y * w) % n
            if e not in best or qv < best[e]:
                best[e] = qv
    hs = list(range(n)) if n < 70000 else [rng.randrange(n) for _ in range(20000)]
    covered = sum(1 for h in hs if h in best)
    mism = sum(1 for h in hs if h in best and L.cvp(h)[0] != best[h])
    # uncovered h must have cvp norm > X
    unc_bad = sum(1 for h in hs if h not in best and L.cvp(h)[0] <= X)
    rec = dict(bits=bits, c=c, n=n, targets=len(hs), covered_by_enum=covered, mismatches=mism, uncovered_but_cvp_le_X=unc_bad)
    print(rec); report.append(rec)
    assert mism == 0 and unc_bad == 0
json.dump(report, open("cvp_selftest.json", "w"), indent=1)
print("CVP self-test passed")
