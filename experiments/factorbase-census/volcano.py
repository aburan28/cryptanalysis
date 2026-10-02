from sympy import factorint, isprime, legendre_symbol, divisors
from math import isqrt
r = 680564733841876926932320129493409985129
assert isprime(r)
N = 4*r; q = 2**131
t = q + 1 - N
print("trace t =", t)
D = t*t - 4*q
assert D % 7 == 0
f2 = -D//7; f = isqrt(f2); assert f*f == f2
print("conductor f of Z[pi] =", f)
F = factorint(f); print("f factors:", F)
# which Koblitz curve? mu=-1 (a=0): tau^2 + tau + 2 = 0 ; mu=+1 (a=1)
for mu,a in ((-1,0),(1,1)):
    t0,t1 = 2,mu
    for _ in range(130): t0,t1 = t1, mu*t1 - 2*t0
    print(f"a={a}: trace of tau^131 =", t1, "match" if t1==t else "")
# volcano data
for p,e in F.items():
    print(f"p={p}: v_p(f)={e}, (-7/p)={legendre_symbol(-7 % p, p)}")
def h_order(fp):  # class number of Z + fp*O_K, K=Q(sqrt-7), h_K=1, units index 1 (fp>1)
    if fp == 1: return 1
    from fractions import Fraction
    h = Fraction(fp)
    for p in factorint(fp): h *= Fraction(p - legendre_symbol(-7 % p, p), p)
    return int(h)
tot = 0
for d in sorted(divisors(f)):
    h = h_order(d); tot += h
    if d==1 or h < 10**7: print(f"order conductor {d}: {h} F_q-isomorphism classes")
print("total curves in isogeny class:", tot, "~2^%.1f" % (tot.bit_length()-1))
print("log2 r = %.3f" % (r.bit_length()-1 + 0.0))
