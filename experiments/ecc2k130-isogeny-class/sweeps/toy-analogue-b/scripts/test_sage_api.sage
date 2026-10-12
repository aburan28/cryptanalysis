R.<Z>=GF(2)[]
K.<z>=GF(2^179, modulus=Z^179+Z^4+Z^2+Z+1)
print(type(K))
a=K.from_integer(5); print(a, a.to_integer())
E=EllipticCurve(K,[1,1,0,0,1])
import time; t0=time.time(); c=E.cardinality(algorithm='pari'); print(c, time.time()-t0)
print(pari('polclass(-7*359^2)').poldegree())
