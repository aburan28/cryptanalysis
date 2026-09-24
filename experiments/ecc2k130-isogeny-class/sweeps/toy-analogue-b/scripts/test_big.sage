import time, sys
R.<Z>=GF(2)[]
t0=time.time()
L.<b> = GF(2^8815)
print('GF(2^8815) built', time.time()-t0, L.modulus().hamming_weight() if hasattr(L.modulus(),'hamming_weight') else len(L.modulus().exponents()), flush=True)
t0=time.time()
rts = (Z^41+Z^3+1).roots(ring=L, multiplicities=False)
print('roots of z^41+z^3+1 in L:', len(rts), time.time()-t0, flush=True)
u=L.random_element(); v=L.random_element()
t0=time.time()
for i in range(200): x=u*v
print('mult', (time.time()-t0)/200, flush=True)
t0=time.time()
for i in range(50): x=~u
print('inv', (time.time()-t0)/50, flush=True)
E=EllipticCurve(L,[1,0,0,0,1])
t0=time.time()
P=E.lift_x(u) if False else None
x0=L.random_element()
print('done', flush=True)
