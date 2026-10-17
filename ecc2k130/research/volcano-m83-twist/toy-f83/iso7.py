p=83
inv=lambda v:pow(v%p,-1,p)
# polys as lists low->high
def norm(a):
    a=[c%p for c in a]
    while a and a[-1]==0: a.pop()
    return a
def add(a,b): n=max(len(a),len(b)); return norm([(a[i] if i<len(a) else 0)+(b[i] if i<len(b) else 0) for i in range(n)])
def sub(a,b): return add(a,[-c for c in b])
def mul(a,b):
    if not a or not b: return []
    r=[0]*(len(a)+len(b)-1)
    for i,x in enumerate(a):
        for j,y in enumerate(b): r[i+j]+=x*y
    return norm(r)
def divmod_(a,b):
    a=norm(a[:]); q=[0]*max(len(a)-len(b)+1,1); il=inv(b[-1])
    while len(a)>=len(b):
        c=a[-1]*il%p; d=len(a)-len(b); q[d]=c
        a=sub(a,[0]*d+[c*x for x in b])
    return norm(q),a
mod=lambda a,b:divmod_(a,b)[1]
def gcd(a,b):
    while b: a,b=b,mod(a,b)
    return [c*inv(a[-1])%p for c in a]
def pw(base,e,m):
    r=[1]; base=mod(base,m)
    while e:
        if e&1: r=mod(mul(r,base),m)
        base=mod(mul(base,base),m); e>>=1
    return r
def short_from_general(a2,a4,a6):
    # x = X - a2/3
    s=(-a2*inv(3))%p
    A=(3*s*s+2*a2*s+a4)%p; B=(s**3+a2*s*s+a4*s+a6)%p
    return A,B
def j(A,B): return 1728*4*A**3*inv(4*A**3+27*B*B)%p
def count(A,B):
    return p+1+sum(0 if (v:=(x**3+A*x+B)%p)==0 else (1 if pow(v,(p-1)//2,p)==1 else -1) for x in range(p))
def f7(A,B):
    # psi_7 via standard recursion, as polys in x with y^2 replaced by F
    F=[B,A,0,1]
    psi={0:[],1:[1],2:[2],3:[ -A*A,12*B,6*A,0,3],4:None}
    # use convention: psi_n for even n carries factor y; store psi_n/y for even n... simpler: psi4/(2y)
    psi[4]=mul([4],[-A**3-8*B*B,-4*A*B,-5*A*A,20*B,5*A,0,1])  # = psi4/y  (psi2=2y)
    F2=mul(F,F)
    # psi5 = psi4 psi2^3 - psi1 psi3^3 ; with psi2=2y, psi4 = y*P4: psi4*psi2^3 = y*P4*8y^3 = 8 P4 F^2
    p5=sub(mul([8],mul(psi[4],F2)),mul(psi[3],mul(psi[3],psi[3])))
    # psi7 = psi5 psi3^3 - psi2^3... general: psi_{2m+1}=psi_{m+2}psi_m^3 - psi_{m-1}psi_{m+1}^3, m=3:
    # psi7 = psi5*psi3^3 - psi2*psi4^3 = p5*P3^3 - 2y * y^3 P4^3 = p5 P3^3 - 2 F^2 P4^3
    P3=psi[3]; P4=psi[4]
    return sub(mul(p5,mul(P3,mul(P3,P3))),mul([2],mul(F2,mul(P4,mul(P4,P4)))))
def kernels7(A,B):
    f=f7(A,B); f=[c*inv(f[-1])%p for c in f]
    assert len(f)==25
    # x^(p^3) mod f
    xp=pw([0,1],p,f); xp3=xp
    for _ in range(2): # compose: x^(p^k) via powering repeatedly
        xp3=pw(xp3,p,f)
    g=gcd(f,sub(xp3,[0,1]))
    # split g into cubics by random gcds (Cantor-Zassenhaus, odd p)
    import random; random.seed(1)
    facs=[g]; out=[]
    while facs:
        h=facs.pop()
        if len(h)-1<=3: out.append(h); continue
        r=[random.randrange(p) for _ in range(len(h)-1)]
        t=sub(pw(r,(p**3-1)//2,h),[1]); d=gcd(h,t) if t else h
        if 0<len(d)-1<len(h)-1: facs+= [d, divmod_(h,d)[0]]
        else: facs.append(h)
    ks=[]
    for h in out:
        if len(h)!=4: continue
        # closure under doubling: h(num/den)=0 mod h
        num=[A*A,-8*B,-2*A,0,1]; den=[4*B,4*A,0,4]
        val=[]; 
        for i,c in enumerate(h):
            val=add(val,mul([c],mul(pw(num,i,h) if i else [1],pw(den,3-i,h) if 3-i else [1])))
        if not mod(val,h): ks.append(h)
    return ks,len(out)
def velu(A,B,h):
    # h monic cubic: x^3 - s1 x^2 + s2 x - s3 ; power sums
    s1=-h[2]%p; s2=h[1]; s3=-h[0]%p
    p1=s1; p2=(s1*s1-2*s2)%p; p3=(s1**3-3*s1*s2+3*s3)%p
    t=(6*p2+2*A*3)%p
    # w = sum(4(x^3+Ax+B) + x(6x^2+2A)) = sum(10x^3 + 6A x + 4B)
    w=(10*p3+6*A*p1+12*B)%p
    return (A-5*t)%p,(B-7*w)%p
if __name__=="__main__":
    A,B=short_from_general(1,2,0)
    print("original y^2=x^3+x^2+2x -> short W A,B =",A,B,"#E",count(A,B),"j",j(A,B))
    print("target y^2=x^3+x+16: #E",count(1,16),"j",j(1,16))
    ks,n=kernels7(A,B); print("cubic factors of psi7:",n,"kernel cubics:",len(ks))
    for h in ks:
        A2,B2=velu(A,B,h); print(" 7-isogeny ->",(A2,B2),"#E",count(A2,B2),"j",j(A2,B2))
    # full graph over j-invariants with 82 points
    js={}
    for a in range(p):
        for b in range(p):
            if (4*a**3+27*b*b)%p and count(a,b)==82: js.setdefault(j(a,b),(a,b))
    print("j-invariants in isogeny class (#E=82):",sorted(js))
    for jj,(a,b) in sorted(js.items()):
        ks,_=kernels7(a,b); print(" j=%d 7-neighbours:"%jj,sorted(j(*velu(a,b,h)) for h in ks))
