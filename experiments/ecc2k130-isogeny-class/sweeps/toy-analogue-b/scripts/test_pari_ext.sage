import time
# F_q = F_2[z]/(z^41+z^3+1)?  check irreducibility and PARI extension-field tools
R.<Z>=GF(2)[]
print('z^41+z^3+1 irreducible:', (Z^41+Z^3+1).is_irreducible())
t0=time.time()
a = pari('ffgen(Mod(1,2)*(x^41+x^3+1), \'a)')
b = pari('ffgen(2^8815, \'b)')
print('ffgen big', time.time()-t0)
t0=time.time()
m = pari.ffembed(a, b)
print('ffembed', time.time()-t0)
img = pari.ffmap(m, a)
print('ffmap ok', pari.ffmap(m, a**41+a**3+1))
t0=time.time()
u = pari.random(b); v = pari.random(b)
for i in range(100): w = u*v
print('mult 8815-bit', (time.time()-t0)/100)
t0=time.time()
for i in range(20): w = 1/u
print('inv 8815-bit', (time.time()-t0)/20)
