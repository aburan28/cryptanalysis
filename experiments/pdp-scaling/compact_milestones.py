"""Frozen toy-field milestones: compact membership, reliable PDP, rank accounting."""
import argparse
from collections import Counter
import hashlib
import json
import math
import platform
import random
import subprocess
import time
from pathlib import Path

import pycryptosat
from compact_admissibility import PowerCompactTemplate
from fixed_phase import bases,corpus,exact_oracle,scalar,subgroup_order
from gf2n import GF2n,Curve,Point,modulus
from toy_domain import ToyDomainTemplate


def sqrt_mod(a,p):
    a%=p
    if a==0:return 0
    if pow(a,(p-1)//2,p)!=1:raise ValueError('nonresidue')
    if p%4==3:return pow(a,(p+1)//4,p)
    q=p-1;s=0
    while q%2==0:q//=2;s+=1
    z=2
    while pow(z,(p-1)//2,p)!=p-1:z+=1
    c=pow(z,q,p);x=pow(a,(q+1)//2,p);t=pow(a,q,p);m=s
    while t!=1:
        i=1;v=t*t%p
        while v!=1:v=v*v%p;i+=1
        b=pow(c,1<<(m-i-1),p)
        x=x*b%p;t=t*b*b%p;c=b*b%p;m=i
    return x


class OrbitRank:
    """Rank of factor-base coefficient rows modulo r, folding +/-Frobenius.

    This is relation-matrix progress, not a DLP recovery. The target has no
    separate per-row column (which would make rank spuriously automatic).
    """
    def __init__(self,E,r,G):
        if r<=2 or any(r%d==0 for d in range(2,math.isqrt(r)+1)):
            raise ValueError('rank accounting requires an odd prime subgroup order')
        self.E,self.r=E,r
        root=sqrt_mod(-7,r);inv2=pow(2,-1,r)
        sigma=Point(E.F.sqr(G.x),E.F.sqr(G.y))
        self.lam=next(lam for lam in (((-1+root)*inv2)%r,((-1-root)*inv2)%r)
                      if scalar(E,lam,G)==sigma)
        self.pivots={};self.seen=set()

    def canonical(self,p):
        best=None;coefficient=None;factor=1
        for _ in range(self.E.F.n):
            for sign,q in ((1,p),(-1,self.E.neg(p))):
                key=(q.x,q.y)
                if best is None or key<best:
                    best=key;coefficient=pow(sign*factor%self.r,-1,self.r)
            p=Point(self.E.F.sqr(p.x),self.E.F.sqr(p.y))
            factor=factor*self.lam%self.r
        return best,coefficient

    def add(self,points):
        row={}
        for p in points:
            key,c=self.canonical(p);self.seen.add(key)
            row[key]=(row.get(key,0)+c)%self.r
        row={k:v for k,v in row.items() if v}
        original=[[*k,v] for k,v in sorted(row.items())]
        while row:
            lead=min(row)
            if lead not in self.pivots:
                inv=pow(row[lead],-1,self.r)
                self.pivots[lead]={k:v*inv%self.r for k,v in row.items()}
                return True,original
            factor=row[lead]
            for k,v in self.pivots[lead].items():
                value=(row.get(k,0)-factor*v)%self.r
                if value:row[k]=value
                else:row.pop(k,None)
        return False,original


def campaign(n,l,targets,phases,variant,timeout=1.0):
    # Corpus generation may have warmed the global modulus cache.
    modulus.cache_clear()
    start=time.process_time();F=GF2n(n);E=Curve(F,1);r=subgroup_order(n)
    rank=OrbitRank(E,r,Point(*targets[0]['point']))
    common=time.process_time()-start
    t=time.process_time()
    truth=[exact_oracle(E,r,bases(F,l,phases),Point(*entry['point'])) is not None for entry in targets]
    instrument=time.process_time()-t
    factory=PowerCompactTemplate if variant=='compact_s4' else ToyDomainTemplate
    encoding='s3-chain' if variant=='table_chain' else 's4'
    t=time.process_time();template=factory(F,l,phases,encoding);build=time.process_time()-t
    rows=[];load=0.;rank_cpu=0.;solver=None;split=None
    for entry,want in zip(targets,truth):
        # Held-out targets start with fresh solver state. Reuse only within a split.
        if solver is None or entry['split']!=split:
            t=time.process_time();solver=template.c.solver();load+=time.process_time()-t
            split=entry['split']
        R=Point(*entry['point'])
        out=template.search(solver,E,r,R,2,timeout)
        correct=None if out['status']=='timeout' else (out['status']=='sat')==want
        if correct is False:raise AssertionError((variant,n,l,entry,out))
        independent=False;coefficient_row=[]
        if out['status']=='sat':
            points=[Point(*p) for p in out['points']]
            t=time.process_time();independent,coefficient_row=rank.add(points)
            rank_cpu+=time.process_time()-t
        rows.append({**entry,**out,'oracle_sat':want,'correct':correct,
                     'within_budget':out['search_wall_s']<=timeout,
                     'independent':independent,'coefficient_row':coefficient_row})
    total=time.process_time()-start-instrument
    statuses=dict(Counter(row['status'] for row in rows));rank_count=len(rank.pivots)
    return {'n':n,'l':l,'phases':phases,'variant':variant,'targets':len(targets),'statuses':statuses,
            'correct':sum(row['correct'] is True for row in rows),
            'rank':rank_count,'seen_orbit_columns':len(rank.seen),'frobenius_eigenvalue':rank.lam,
            'common_and_rank_setup_cpu_s':common,'build_cpu_s':build,'load_cpu_s':load,
            'rank_cpu_s':rank_cpu,'total_cpu_s':total,
            'cpu_s_per_independent_row':total/rank_count if rank_count else None,
            'oracle_cpu_s_excluded':instrument,
            'variables':template.c.nvars,'and_gates':len(template.c._and),'xor_gates':len(template.c._xor),
            'domain_payloads':getattr(template,'domain_payloads',None),'rows':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    if args.out.exists():p.error('choose a fresh output path')
    fixture=Path(__file__).with_name('results')/'compact_corpus_100.json'
    frozen=json.loads(fixture.read_text())
    jobs=[]
    for phases in frozen['phases']:
        for variant in ('table_chain','table_s4','compact_s4'):
            jobs.append(('reliability',13,6,frozen['targets'],tuple(phases),variant))
    # Fresh scaling targets; no selection by existence of decomposition.
    for n,l,count in ((7,4,12),(9,5,12),(13,6,12),(19,8,12)):
        F=GF2n(n);E=Curve(F,1);r=subgroup_order(n)
        targets=[{'id':i,'split':'scaling_holdout','point':[P.x,P.y]}
                 for i,P in enumerate(corpus(E,r,count,808013+n))]
        for variant in ('table_s4','compact_s4'):
            jobs.append(('scaling',n,l,targets,(0,1,2),variant))
    random.Random(2026092601).shuffle(jobs)
    data={'schema':'compact-milestones/v1','complete':False,'timeout_s':1.0,
          'guess_bits':2,'scaling_seed_rule':'808013+n','job_order_seed':2026092601,
          'corpus_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),
          'python':platform.python_version(),'platform':platform.platform(),'pycryptosat':pycryptosat.__version__,
          'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
          'source_sha256':{f:hashlib.sha256(Path(__file__).with_name(f).read_bytes()).hexdigest()
                          for f in ('compact_admissibility.py','compact_milestones.py','fixed_phase.py','gf2n.py','toy_domain.py')},
          'runs':[]}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    for task,n,l,targets,phases,variant in jobs:
        run=campaign(n,l,targets,phases,variant)
        data['runs'].append({'task':task,**run})
        args.out.write_text(json.dumps(data,indent=2)+'\n')
        print(task,n,l,phases,variant,run['statuses'],'rank',run['rank'],'cpu',round(run['total_cpu_s'],3),flush=True)
    data['complete']=True;args.out.write_text(json.dumps(data,indent=2)+'\n')


if __name__=='__main__':
    main()
