# For each prime P | f_n, pi acts on E0[P] as the scalar lam = t/2 mod P (E0 has End = O_K, and (pi - t/2)/f... in O_K).
# The kernel points of any P-isogeny out of E0 (and the ascending one from a level-P curve) live over F_{q^k}, k = ord_P(lam).
def lucas(n,t1):
    tt=[2,t1]
    for i in range(2,n+1): tt.append(t1*tt[-1]-2*tt[-2])
    return tt[n]
for (n,a) in [(59,0),(109,0),(89,0),(131,0),(31,0),(127,0),(107,0)]:
    t1=-1 if a==0 else 1
    t=lucas(n,t1); q=2**n
    f=isqrt((t*t-4*q)//(-7))
    print('n=%d a=%d t=%d f=%s'%(n,a,t,factor(f)))
    for P,e in factor(f):
        lam=Mod(t,P)/2
        k=lam.multiplicative_order()
        kt=(-lam).multiplicative_order()
        print('   P=%d kron(-7,P)=%d  lam=t/2 mod P=%d  k=ord(lam)=%d  (twist: ord(-lam)=%d)  ord_P(2)=%d  P-1=%s'%(P,kronecker(-7,P),lam,k,kt,Mod(2,P).multiplicative_order(),factor(P-1)))
