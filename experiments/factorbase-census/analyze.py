import re, statistics as st, math, sys
def gb(n,d):
    r=1
    for i in range(d): r=r*(2**(n-i)-1)//(2**(i+1)-1)
    return r
def parse_mc(fn):
    rows=[]
    for line in open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'data',fn)):
        m=re.match(r'(c (\d+) eps (\d)|random (\d+)) size (\d+) N1 (\d+) N2 (\d+)(.*)probes',line)
        if not m: continue
        N={1:int(m.group(6)),2:int(m.group(7))}; se={}
        for d,v,s in re.findall(r'N(\d) (\S+) se (\S+)',m.group(8)): N[int(d)]=float(v); se[int(d)]=float(s)
        rows.append(dict(c=int(m.group(2)) if m.group(2) else None,eps=m.group(3),size=int(m.group(5)),N=N,se=se))
    return rows
def parse_exact(fn):
    rows=[]
    for line in open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'data',fn)):
        m=re.match(r'(c (\d+) eps (\d)|random (\d+)) size (\d+) :((?: \d+)+)',line)
        if not m: continue
        cnts=list(map(int,m.group(6).split()))
        rows.append(dict(c=int(m.group(2)) if m.group(2) else None,eps=m.group(3),size=int(m.group(5)),N={d+1:cnts[d] for d in range(len(cnts))},se={}))
    return rows
def ratios(rows,n,d):
    out=[]
    for r in rows:
        rho=r['size']/(2**n-1); exp=gb(n,d)*rho**(2**d-1)
        out.append(r['N'][d]/exp)
    return out
def report(n,curves,rands,dims):
    print(f"\n== n={n}: {len(curves)} curve-like sets, {len(rands)} random sets ==")
    for d in dims:
        rc=ratios(curves,n,d); rr=ratios(rands,n,d)
        c1=[r['N'][d]/(gb(n,d)*(r['size']/(2**n-1))**(2**d-1)) for r in curves if r['c']==1]
        def fmt(v): return f"mean {st.mean(v):.4f} sd {st.pstdev(v):.4f} min {min(v):.3f} max {max(v):.3f}"
        # Welch t-test
        if len(rc)>1 and len(rr)>1:
            m1,m2=st.mean(rc),st.mean(rr); v1,v2=st.variance(rc),st.variance(rr)
            t=(m1-m2)/math.sqrt(v1/len(rc)+v2/len(rr))
        else: t=float('nan')
        print(f" dim {d}: N_d / random-model  curve-like: {fmt(rc)} | random: {fmt(rr)} | c=1: {', '.join(f'{v:.3f}' for v in c1)} | Welch t = {t:+.1f}")
    # existence counts for top dims
    for d in dims[-1:]+[dims[-1]+1]:
        nc=sum(1 for r in curves if r['N'].get(d,0)>0); nr=sum(1 for r in rands if r['N'].get(d,0)>0)
        print(f" sets with any dim-{d} full-density subspace: curve-like {nc}/{len(curves)}, random {nr}/{len(rands)}")
report(11,parse_exact('n11_all.txt'),parse_exact('n11_rand.txt'),[3,4,5])
report(13,parse_exact('n13_sample.txt'),parse_exact('n13_rand.txt'),[3,4,5])
report(17,parse_mc('n17_curves.txt'),parse_mc('n17_rand.txt'),[3,4,5])
report(19,parse_mc('n19_curves.txt'),parse_mc('n19_rand.txt'),[3,4,5])
