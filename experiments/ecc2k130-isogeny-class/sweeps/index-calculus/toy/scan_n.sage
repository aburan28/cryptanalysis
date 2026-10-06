# conductor of Z[pi] in O_K for E0_n: y^2+xy=x^3+1 over F_{2^n}, n prime
for n in prime_range(11, 48):
    q=2**n; t=[2,-1]
    for i in range(2,n+1): t.append(-t[-1]-2*t[-2])
    tn=t[n]; D=tn**2-4*q; f2=D//(-7); f=isqrt(f2); assert f*f==f2
    card=q+1-tn
    print(n, 'card=',card, factor(card), ' f=',f, factor(f) if f>1 else 1, [ (l, kronecker(-7,l)) for l,_ in (factor(f) if f>1 else [])])
