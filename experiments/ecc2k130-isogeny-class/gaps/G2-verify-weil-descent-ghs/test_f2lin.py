"""Cross-check own f2lin arithmetic against Sage GF(2^131) (same modulus) on random data."""
import sys, random, json
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/gaps/G2-verify-weil-descent-ghs")
import ecc2k, f2lin
from sage.all import GF, PolynomialRing
K = ecc2k.field()
assert int(K.modulus().change_ring(__import__('sage.all',fromlist=['ZZ']).ZZ)(2)) == f2lin.MOD
rng = random.Random(20260924)
n = 0
for _ in range(300):
    a, b = rng.getrandbits(131), rng.getrandbits(131)
    A, B = K.from_integer(a), K.from_integer(b)
    assert f2lin.fmul(a, b) == (A*B).to_integer()
    assert f2lin.fsqr(a) == (A*A).to_integer()
    assert f2lin.fsqrt(a) == A.sqrt().to_integer()
    assert f2lin.ftrace(a) == int(A.trace())
    if a:
        assert f2lin.finv(a) == (1/A).to_integer()
    n += 1
# polynomial ops vs Sage
R = PolynomialRing(GF(2), 'x'); X = R.gen()
def toR(v): return R([ (v>>i)&1 for i in range(max(1,v.bit_length())) ])
for _ in range(200):
    u, v = rng.getrandbits(40) | 1, rng.getrandbits(30) | 1
    assert toR(f2lin.clmul(u, v)) == toR(u)*toR(v)
    qq, rr = f2lin.pdivmod(u, v)
    assert toR(qq) == toR(u)//toR(v) and toR(rr) == toR(u) % toR(v)
    assert toR(f2lin.pgcd(u, v)) == toR(u).gcd(toR(v))
    w = rng.getrandbits(12) | (1 << 12)
    assert f2lin.is_irreducible_f2(w) == toR(w).is_irreducible()
print(json.dumps({"field_ops_checked": n, "poly_ops_checked": 200, "ok": True}))
