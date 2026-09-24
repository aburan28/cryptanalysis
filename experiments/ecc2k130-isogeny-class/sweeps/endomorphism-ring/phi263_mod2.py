# Compute the classical modular polynomial Phi_263(X,Y) over Z with PARI polmodular,
# reduce it mod 2 and save the F_2 coefficient support (bivariate, as exponent pairs).
from sage.all import *
import time, json, hashlib
pari.allocatemem(8*10**9)
t0=time.time()
P = pari.polmodular(263)          # in variables x (outer) and y
dt=time.time()-t0
print("polmodular(263) time %.1fs"%dt, flush=True)
# Coefficient layout: P = sum_i P_i(y) x^i
deg_x = int(P.poldegree('x'))
terms=[]
maxbits=0
for i in range(deg_x+1):
    Pi = P.polcoef(i,'x')
    dy = int(Pi.poldegree('y')) if Pi != 0 else -1
    for jj in range(dy+1):
        c = Integer(Pi.polcoef(jj,'y'))
        maxbits=max(maxbits,c.nbits())
        if c % 2:
            terms.append((i,jj))
print("deg_x",deg_x,"maxbits",maxbits,"odd terms",len(terms), flush=True)
# sanity: symmetry Phi(X,Y)=Phi(Y,X)
S=set(terms); assert all((b,a) in S for (a,b) in terms)
# sanity: Phi_263(1,Y) mod 2 vs PARI polmodular(263,0,Mod(1,2))
R = PolynomialRing(GF(2),'Y'); Y=R.gen()
phi1 = sum(Y**b for (a,b) in terms if True)  # X=1: sum over all terms of Y^b
direct = R(str(pari.polmodular(263,0,pari('Mod(1,2)')).lift()).replace('y','Y').replace('x','Y'))
print("Phi(1,Y) mod 2 equals polmodular(263,0,Mod(1,2)):", phi1==direct, flush=True)
blob=json.dumps(sorted(terms)).encode()
json.dump({"level":263,"polmodular_time_s":dt,"deg_x":deg_x,"max_coeff_bits":maxbits,
           "odd_terms_xy":sorted(terms),"sha256_of_terms_json":hashlib.sha256(blob).hexdigest(),
           "phi_1_Y_matches_polmodular_mod2":bool(phi1==direct)},
          open("/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/phi263_mod2.json","w"))
print("total %.1fs"%(time.time()-t0))
