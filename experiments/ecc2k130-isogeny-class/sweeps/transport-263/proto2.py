import sys, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import EllipticCurve, PolynomialRing, set_random_seed, GF, prod
set_random_seed(2)
K, cs = ecc2k.load(["E0","A000"])
E = cs["A000"]; b = E.a6()
N=ecc2k.N; q=ecc2k.q; tw=ecc2k.TWIST_CARD
t0=time.process_time()
K2 = GF(2**262, 'w')
print(K2.modulus())
zpol = PolynomialRing(GF(2),'Z')([int(c) for c in K.modulus().list()])
r = zpol.change_ring(K2).roots()[0][0]
print("root find", time.process_time()-t0)
pw = [K2(1)]
for i in range(130): pw.append(pw[-1]*r)
def emb(u):
    n = u.to_integer(); s = K2(0); i=0
    while n:
        if n&1: s += pw[i]
        n >>= 1; i += 1
    return s
# homomorphism sanity
a = K.random_element(); c = K.random_element()
assert emb(a*c) == emb(a)*emb(c) and emb(a+c)==emb(a)+emb(c)
t0=time.process_time()
E2 = EllipticCurve(K2, [1,0,0,0,emb(b)])
cof2 = 4*N*tw // 263**2
Q2 = cof2*E2.random_point()
print("scalar mult F_q2", time.process_time()-t0)
print("order 263^2:", (263**2*Q2).is_zero(), not (263*Q2).is_zero())
P2 = 263*Q2
fr = E2(P2[0]**(2**131), P2[1]**(2**131))
print("frob = -P", fr == -P2, "y in Fq?", P2[1]**(2**131)==P2[1], "x in Fq?", P2[0]**(2**131)==P2[0])
xs=[]; R=P2
for i in range(131): xs.append(R[0]); R=R+P2
print("F_q2 total", time.process_time()-t0)
