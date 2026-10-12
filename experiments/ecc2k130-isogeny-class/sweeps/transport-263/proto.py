import sys, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import EllipticCurve, PolynomialRing, set_random_seed
set_random_seed(1)
K, cs = ecc2k.load(["E0","A000"])
E = cs["A000"]; E0 = cs["E0"]
b = E.a6()
Et = EllipticCurve(K, [1,1,0,0,b])
tw = ecc2k.TWIST_CARD
cof = tw // 263**2
t0=time.process_time(); w0=time.time()
while True:
    Q = cof * Et.random_point()
    P = 263*Q
    if not P.is_zero(): break
print("find kernel pt", time.process_time()-t0, time.time()-w0)
xs=[]; R=P
for i in range(131):
    xs.append(R[0]); R = R+P
print("xs", time.process_time()-t0)
RX = PolynomialRing(K,"X"); X=RX.gen()
from sage.all import prod
h = prod([X - x for x in xs])
print("kerpoly", time.process_time()-t0)
t1=time.process_time(); w1=time.time()
phi = E.isogeny(h)
print("sage isogeny build", time.process_time()-t1, time.time()-w1)
t1=time.process_time()
C = phi.codomain(); print(C.a_invariants()[:2], C.j_invariant()==1)
iso = C.isomorphism_to(E0)
print("iso", time.process_time()-t1, iso)
Rp = 4*E.random_point()
t1=time.process_time(); w1=time.time()
img = iso(phi(Rp))
print("sage eval", time.process_time()-t1, time.time()-w1)
v = sum(xs)
print("v^2+v == b+1", v**2+v == b+1)
