# For Koblitz curves over F_{2^n} (n prime), every prime P | f_n: kron(-7,P), lambda = t_n/2 mod P (the scalar by which
# the q-Frobenius acts on E0[P]), k = ord(lambda) = extension degree over F_q of E0[P] (and of the kernel of the
# ascending P-isogeny from any level-P curve).  a=1 is the quadratic twist (t -> -t, lambda -> -lambda).
import json, sys
def lucas(n,t1):
    tt=[2,t1]
    for i in range(2,n+1): tt.append(t1*tt[-1]-2*tt[-2])
    return tt[n]
rows=[]
for n in prime_range(11,200):
    t=lucas(n,-1); q=2**n
    f=isqrt((t*t-4*q)//(-7))
    for P,e in factor(f):
        lam=Mod(t,P)/2
        k0=lam.multiplicative_order(); k1=(-lam).multiplicative_order()
        row=dict(n=int(n),P=int(P),e=int(e),kron=int(kronecker(-7,P)),lam_a0=int(lam),k_a0=int(k0),k_a1=int(k1),
                 log2P=float(log(P,2)), P_mod_2n_plus_1=int(P==2*n+1))
        rows.append(row)
        if min(k0,k1)<=12 or n in (59,109,131,179):
            print(row, flush=True)
json.dump(rows,open('/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/kernel_scan.json','w'),indent=1)
