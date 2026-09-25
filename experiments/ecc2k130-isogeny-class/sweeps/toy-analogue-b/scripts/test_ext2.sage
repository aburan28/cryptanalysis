import time
R.<Z>=GF(2)[]
K.<a>=GF(2^41, modulus=Z^41+Z^3+1)
t0=time.time()
L = K.extension(215, 'w')
print('extension', type(L), L.degree(), time.time()-t0, flush=True)
t0=time.time()
emb = L.coerce_map_from(K)
print('coerce map', emb, time.time()-t0, flush=True)
t0=time.time()
x = L(a)
print('image of a computed', time.time()-t0, (x^41+x^3+1)==0, flush=True)
u=L.random_element(); v=L.random_element()
t0=time.time()
for i in range(200): w=u*v
print('mult', (time.time()-t0)/200)
t0=time.time()
for i in range(20): w=1/u
print('inv', (time.time()-t0)/20)
