# Enumerate Koblitz curves y^2+xy=x^3+a*x^2+1 over F_{2^n}, n prime, and factor #E and the Frobenius conductor f_n.
import json
out=[]
for n in prime_range(11,128):
    for a in [0,1]:
        t1 = -1 if a==0 else 1   # #E_a(F_2) = 3 - t1 : a=0 -> 4, a=1 -> 2
        tt=[2,t1]
        for i in range(2,n+1): tt.append(t1*tt[-1]-2*tt[-2])
        tn=tt[n]; q=2**n; card=q+1-tn
        D=tn**2-4*q
        assert D % 7 ==0
        f2=D//(-7); f=isqrt(f2); assert f*f==f2
        fc=factor(card); ff=factor(f)
        rec=dict(n=int(n),a=int(a),t=int(tn),card=int(card),card_fac=str(fc),
                 f=int(f),f_fac=str(ff),
                 f_primes=[[int(pp),int(e),int(kronecker(-7,pp))] for pp,e in ff],
                 card_primes=[[int(pp),int(e)] for pp,e in fc])
        out.append(rec)
        spl=[int(pp) for pp,e in ff if kronecker(-7,pp)==1]
        mid=[int(pp) for pp,e in fc if 2**24<=pp<=2**40]
        if spl:
            print(n,a,'#E=',fc,' f=',ff,' split:',spl,' mid-size card primes:',[(m,round(float(log(m,2)),2)) for m in mid])
json.dump(out,open('/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/enumerate.json','w'),indent=1)
