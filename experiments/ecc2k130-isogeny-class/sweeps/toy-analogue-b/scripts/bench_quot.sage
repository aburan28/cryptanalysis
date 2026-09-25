import time
R.<Z>=GF(2)[]
K.<a>=GF(2^41, modulus=Z^41+Z^3+1)
# irreducible degree-215 polynomial over F_2 (stays irreducible over F_{2^41} since gcd(41,215)=1)
g=None
for k in range(1,108):
    if (Z^215+Z^k+1).is_irreducible(): g=Z^215+Z^k+1; break
if g is None:
    for k1 in range(3,30):
        for k2 in range(2,k1):
            for k3 in range(1,k2):
                if g is None and (Z^215+Z^k1+Z^k2+Z^k3+1).is_irreducible(): g=Z^215+Z^k1+Z^k2+Z^k3+1
print('g =', g)
KW.<w> = K[]
Lq = KW.quotient(KW(g), 'u')
print(type(Lq))
u = Lq.random_element(); v = Lq.random_element()
t0=time.time()
for i in range(200): x=u*v
print('mult', (time.time()-t0)/200)
t0=time.time()
for i in range(20): x=u^-1
print('inv', (time.time()-t0)/20, (x*u)==1)
t0=time.time()
for i in range(200): x=u^2
print('sqr', (time.time()-t0)/200)
# PARI version: Mod(pol in w over ffgen, g)
aa = pari('ffgen(Mod(1,2)*(x^41+x^3+1), \'a)')
