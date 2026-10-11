# Extended search n in (128,200): small split l | f_n and a 24-44 bit prime factor of #E.
for n in prime_range(128,200):
    for a in [0,1]:
        t1 = -1 if a==0 else 1
        tt=[2,t1]
        for i in range(2,n+1): tt.append(t1*tt[-1]-2*tt[-2])
        tn=tt[n]; q=2**n; card=q+1-tn
        f=isqrt((tn**2-4*q)//(-7))
        ff=factor(f, limit=10**7)   # partial factorization of f is enough to spot small split primes
        spl=[int(pp) for pp,e in ff if pp<10**7 and kronecker(-7,pp)==1]
        if not spl: continue
        fc=factor(card)
        mid=[(int(pp),round(float(log(pp,2)),2)) for pp,e in fc if 2**24<=pp<=2**44]
        print(n,a,'#E=',fc,' f=',ff,' split small:',spl,' mid:',mid, flush=True)
