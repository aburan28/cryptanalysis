def lucas(n,t1):
    tt=[2,t1]
    for i in range(2,n+1): tt.append(t1*tt[-1]-2*tt[-2])
    return tt[n]
for n in [37,41,43,47,29,17]:
  for a in [0,1]:
    t1=-1 if a==0 else 1; t=lucas(n,t1); q=2^n; f=isqrt((t*t-4*q)//(-7)); card=q+1-t
    print('n=%d a=%d #E=%s f=%s'%(n,a,factor(card),factor(f)))
    for P,e in factor(f):
        lam=Mod(t,P)/2; k=lam.multiplicative_order()
        print('    P=%d kron=%d k=%d  (P-1)/k=%s  (P+1)/k=%s'%(P,kronecker(-7,P),k,(P-1)/k,(P+1)/k))
