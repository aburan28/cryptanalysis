"""Freeze target-derived right-middle coordinates from exact first two pairs."""

import hashlib
import json
from pathlib import Path
from sage.all import EllipticCurve,GF,PolynomialRing

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
INPUT=ROOT/'n131_w18_four_pairs/native_join/native_input.txt'
FIXTURE=ROOT/'n41_transport_cubic_s8_20261011/fixture.json'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    f=json.loads(FIXTURE.read_text());r=PolynomialRing(GF(2),'t');t=r.gen()
    F=GF(2**41,'t',modulus=t**41+t**3+1);E=EllipticCurve(F,[1,0,0,0,1]);zero=E(0)
    def dec(n):return F(r([(n>>i)&1 for i in range(41)]))
    def enc(x):return sum(int(v)<<i for i,v in enumerate(x.polynomial().list()))
    def coords(P):return [enc(P[0]),enc(P[1])]
    def pi(P):return E(P[0]**2,P[1]**2)
    def ht(x):
        y=F.zero()
        for _ in range(21):y+=x;x=x**4
        return y
    tokens=list(map(int,INPUT.read_text().split()));cursor=4;slots=[]
    for slot in range(8):
        assert tokens[cursor]==64;cursor+=1;rows=[]
        rotation=(0,0,10,10,20,20,30,30)[slot]
        for _ in range(64):
            x,y,col,mask,branch,sign=tokens[cursor:cursor+6];cursor+=6
            w=dec(mask<<1)**(2**rotation);u=ht(w)+branch
            P=E.lift_x(1+1/u,all=True)[sign]
            assert coords(4*P)==[x,y]
            D=P+pi(P);assert enc(1/D[0])==enc(w)
            rows.append((D,col,mask,branch,sign))
        slots.append(rows)
    assert cursor==len(tokens)
    U=E(*[dec(v) for v in f['raw_target_preimages'][0]])
    B=E(*[dec(v) for v in f['pair_points'][1]])
    assert coords(B)==f['pair_points'][1]
    assert (1/U[0]).trace()==0
    by_sum={}
    for i in range(64):
        for j in range(i+1,64):
            a,b=slots[0][i],slots[1][j]
            if a[1]==b[1] or a[1] in f['known_columns'][2:4] or b[1] in f['known_columns'][2:4]:continue
            seed=a[2]^b[2]
            by_sum.setdefault(seed,(i,j,a[0]+b[0],(a[1],b[1])))
    controls=[]
    for seed in range(1,64):
        if seed not in by_sum:continue
        i,j,A,columns=by_sum[seed];V=U-A-B
        if V==zero or V[0]==0 or int((1/V[0]).trace())!=0:continue
        controls.append({'seed_sum':seed,'first_pair_ids':[i,j],
                         'first_pair_columns':columns,'first_pair_point':coords(A),
                         'right_middle_point':coords(V),'target_z':enc(1/V[0])})
        if len(controls)==8:break
    assert len(controls)==8
    positive={'right_middle_point':f['middle_points'][1],
              'target_z':f['middle_reciprocals'][1],
              'pair_reciprocals':f['pair_reciprocals'][2:4],
              'branch_bits':[f['branch_bits'][2],f['branch_bits'][3],f['branch_bits'][5]],
              'source_masks':f['known_masks'][4:8]}
    result={'status':'PASS_N41_TARGET_DERIVED_TWO_PAIR_FIXTURES',
            'curve_id':f['curve_id'],'public_target_original':f['public_target_original'],
            'raw_target_preimage':coords(U),'known_positive':positive,
            'controls':controls,
            'source_sha256':{'targets_sage.py':sha(HERE/'targets_sage.py'),
                             'native_input.txt':sha(INPUT),'fixture.json':sha(FIXTURE),
                             'sage_runtime_info.json':sha(HERE/'sage_runtime_info.json')}}
    (HERE/'targets.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'controls':[x['seed_sum'] for x in controls]}))

if __name__=='__main__':main()
