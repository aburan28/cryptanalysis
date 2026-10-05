import time
RZ.<Z> = GF(2)[]
K.<z> = GF(2^179, modulus=Z^179+Z^4+Z^2+Z+1)
b = K.random_element()
E = EllipticCurve(K,[1,1,0,0,b])
t0=time.time(); c0=cputime()
for i in range(20): R=E.random_point()
print('random_point', (time.time()-t0)/20, cputime(c0)/20)
k=2^170+12345
t0=time.time(); c0=cputime()
for i in range(20): S=k*R
print('scalar mult 170b', (time.time()-t0)/20, cputime(c0)/20)
t0=time.time(); c0=cputime()
Q=R
for i in range(179): Q=Q+R
print('179 adds', (time.time()-t0), cputime(c0))
e = pari.ellinit([1,1,0,0,b])
Rp = pari([R[0],R[1]])
t0=time.time(); c0=cputime()
for i in range(20): Sp=pari.ellmul(e,Rp,k)
print('pari ellmul 170b', (time.time()-t0)/20, cputime(c0)/20)
t0=time.time(); c0=cputime()
c=E.cardinality(algorithm='pari')
print('SEA', time.time()-t0, cputime(c0))
