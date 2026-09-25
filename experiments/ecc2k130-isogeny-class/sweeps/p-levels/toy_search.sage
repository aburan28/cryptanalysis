# search Koblitz toys y^2+xy=x^3+1 over F_{2^m}: primes l | f_m, with r_l = ord_l(t_m/2)
def trace(m):
    a,b=-1,2  # t_1=-1, t_0=2 : t_{k+1} = t1*t_k - 2 t_{k-1}
    t0,t1=2,-1
    for k in range(1,m):
        t0,t1=t1,-t1-2*t0
    return t1
res=[]
for m in prime_range(3,80):
    t=trace(m); q=2^m
    D=t^2-4*q
    assert D%(-7)==0
    f2=D//(-7); f=isqrt(f2); assert f*f==f2
    for l,e in factor(f):
        if l in (2,7): continue
        c=Mod(t,l)/2
        r=c.multiplicative_order()
        res.append((m,l,e,kronecker(-7,l),r, m*r, (-c).multiplicative_order(), (r%2==0 and c^(r//2)==-1)))
for x in res:
    if x[5]<=1200: print("m=%d l=%d e=%d (-7|l)=%d r=%d m*r=%d ord(-c)=%d -1in<c>=%s"%x)
