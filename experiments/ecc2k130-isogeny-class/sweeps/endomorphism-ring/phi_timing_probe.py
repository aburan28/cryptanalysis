from sage.all import *
import sys, json, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
K = ecc2k.field()
phi = json.load(open("/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/phi263_mod2.json"))
byb = {}
for (a_, b_) in phi["odd_terms_xy"]: byb.setdefault(b_, []).append(a_)
RY = PolynomialRing(K, 'Y'); Y = RY.gen()
j = 1/ecc2k.dec(ecc2k.RECORDS["A000"]["b_int"])
pw = [K(1)]
for _ in range(264): pw.append(pw[-1]*j)
g = RY({b_: sum(pw[a_] for a_ in al) for b_, al in byb.items()})
print(type(g), flush=True)
t0 = time.time(); gp = g.__pari__(); print("to pari %.2f" % (time.time()-t0), flush=True)
t0 = time.time(); fr = pari('(g) -> my(Yq = Mod(y, g)); for(i=1,131, Yq = Yq^2); Yq')(gp.substpol(pari('Y'), pari('y')) if False else gp.subst(gp.variable(), pari('y'))); print("Y^q mod g in PARI %.2f s" % (time.time()-t0), flush=True)
