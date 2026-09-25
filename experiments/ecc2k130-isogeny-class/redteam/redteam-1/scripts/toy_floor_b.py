# Toy Koblitz classes with a small floor level, in the pdp-scaling field basis.
# n=37 (a=0, level 73, inert -> 74 floor curves), n=43 (a=0, level 257, inert -> 258).
# Output: b-values (ints, bit i = z^i, modulus = gf2n.modulus(n)) for E0, floor curves
# (j = root of H_{-7 l^2} mod 2, b = 1/j) and random Tr-matched controls.
import sys, json
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/redteam-1/scripts/pdp")
from sage.all import *
import random as pyrandom
import gf2n
out = {}
for n, l in [(37, 73), (43, 257)]:
    modint = gf2n.modulus(n)
    R = PolynomialRing(GF(2), 'z'); z = R.gen()
    mpoly = sum(((modint >> i) & 1) * z**i for i in range(n + 1))
    K = GF(2**n, 'z', modulus=mpoly); zz = K.gen()
    def enc(u): return int(u.to_integer())
    D = -7 * l**2
    H = pari(f"polclass({D})")
    h = int(pari(f"qfbclassno({D})"))
    assert H.poldegree() == h
    Hy = PolynomialRing(K, 'Y')(str(H).replace('x', 'Y'))
    roots = [r for r, e in Hy.roots()]
    assert len(roots) == h, (len(roots), h)
    E0 = EllipticCurve(K, [1, 0, 0, 0, 1]); card0 = E0.cardinality()
    floor = []
    for j in roots:
        assert j != 0 and j != 1
        b = 1 / j
        c = [EllipticCurve(K, [1, a2, 0, 0, b]).cardinality() for a2 in (0, 1)]
        a2 = [0, 1][c.index(card0)] if card0 in c else None
        floor.append(dict(b=enc(b), a2=a2, trb=int(b.trace()), deg=int(j.minpoly().degree())))
    rng = pyrandom.Random(1000 + n)
    trs = {f['trb'] for f in floor}
    ctrl = []
    while len(ctrl) < 16:
        b = K.from_integer(rng.getrandbits(n))
        if b != 0 and int(b.trace()) in trs:
            ctrl.append(dict(b=enc(b), trb=int(b.trace())))
    out[str(n)] = dict(n=n, l=l, modulus=modint, card_E0=int(card0), h=h,
                       floor=floor, controls=ctrl,
                       floor_a2_counts={str(a): sum(1 for f in floor if f['a2'] == a) for a in (0, 1, None)},
                       floor_trb=sorted(trs))
    print(n, l, 'h', h, 'a2 counts', out[str(n)]['floor_a2_counts'], 'Tr(b) set', trs,
          'degs', sorted({f['deg'] for f in floor}))
json.dump(out, open(sys.argv[1], 'w'), indent=1)
