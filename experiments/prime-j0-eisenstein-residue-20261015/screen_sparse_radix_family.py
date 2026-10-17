#!/usr/bin/env python3
"""Exact frozen-fixture screen for (2^k-1)+2^k*tau radix proposals."""

from hashlib import sha256
from pathlib import Path
import json
import tarfile

import screen_sparse_tau_radix as baseline

HERE = Path(__file__).resolve().parent
MAX_STEPS = 30
TERMINAL_NORM_LIMIT = 5000
TERMINAL_COORD_LIMIT = 100


def radix(k):
    t=1<<k
    a,b=t-1,t
    n=7*t*t-5*t+1
    s=4-7*t
    assert baseline.norm((a,b)) == n
    assert a+b*s == -n
    assert s*s-3*s+3 == 7*n
    return a,b,n,s


def nearest_digit(residue,n,s):
    if residue == 0:
        return 0,0
    best = None
    coefficient = s*s-3*s+3
    for lift_number in range(-2,3):
        lift = residue+lift_number*n
        center = -((3-2*s)*lift)//(2*coefficient)
        for b in range(center-2,center+3):
            a = lift-s*b
            score = (baseline.norm((a,b)),abs(b),abs(a),a,b)
            if best is None or score < best:
                best = score
    return best[3],best[4]


def multiply(pair,a,b):
    u,v=pair
    return a*u-3*b*v,b*u+(a+3*b)*v


def recode_step(pair,table,a,b,n,s):
    x,y=pair
    residue=(x+s*y)%n
    negative=residue>(n-1)//2
    index=n-residue if negative else residue
    da,db=table[index]
    if negative:
        da,db=-da,-db
    ra,rb=x-da,y-db
    qu=(a+3*b)*ra+3*b*rb
    qv=-b*ra+a*rb
    assert qu%n == 0 and qv%n == 0
    next_pair=qu//n,qv//n
    assert multiply(next_pair,a,b)==(ra,rb)
    return (da,db),next_pair


def screen(k,scalars):
    a,b,n,s=radix(k)
    table=[nearest_digit(residue,n,s) for residue in range((n+1)//2)]
    assert all((da+s*db-residue)%n == 0
               for residue,(da,db) in enumerate(table))
    max_norm=[0]*(MAX_STEPS+1)
    max_coord=[0]*(MAX_STEPS+1)
    for scalar in scalars:
        pair=baseline.choose_pair(scalar)
        assert (pair[0]+pair[1]*baseline.LAMBDA_TAU)%baseline.ORDER == scalar
        for step_index in range(MAX_STEPS+1):
            max_norm[step_index]=max(max_norm[step_index],baseline.norm(pair))
            max_coord[step_index]=max(max_coord[step_index],abs(pair[0]),abs(pair[1]))
            if step_index<MAX_STEPS:
                _,pair=recode_step(pair,table,a,b,n,s)
    selected=next((i for i in range(1,MAX_STEPS+1)
                   if max_norm[i]<TERMINAL_NORM_LIMIT
                   and max_coord[i]<=TERMINAL_COORD_LIMIT),None)
    terminal_pairs=set()
    if selected is not None:
        for scalar in scalars:
            original=baseline.choose_pair(scalar)
            pair=original
            digits=[]
            for _ in range(selected):
                digit,pair=recode_step(pair,table,a,b,n,s)
                digits.append(digit)
            terminal_pairs.add(pair)
            reconstructed=pair
            for digit in reversed(digits):
                product=multiply(reconstructed,a,b)
                reconstructed=product[0]+digit[0],product[1]+digit[1]
            assert reconstructed==original
    seed_set={baseline.canonical(digit) for digit in table}
    return {'k':k,'radix_pair':[a,b],'radix_norm':n,'tau_residue':s,
            'digit_residue_count':len(table),'digit_seed_count_including_zero':len(seed_set),
            'digit_max_norm':max(map(baseline.norm,table)),
            'digit_table_sha256':sha256(json.dumps(table,separators=(',',':')).encode()).hexdigest(),
            'digit_seed_sha256':sha256(json.dumps(sorted(seed_set),separators=(',',':')).encode()).hexdigest(),
            'first_frozen_fixture_terminal_step':selected,
            'terminal_max_norm':max_norm[selected] if selected is not None else None,
            'terminal_max_absolute_coordinate':max_coord[selected] if selected is not None else None,
            'distinct_terminal_pairs':len(terminal_pairs) if selected is not None else None,
            'terminal_pairs_sha256':sha256(json.dumps(sorted(terminal_pairs),separators=(',',':')).encode()).hexdigest() if selected is not None else None,
            'max_terminal_norm_by_step':max_norm,
            'max_terminal_coordinate_by_step':max_coord,
            'native_point_replay':'pending'}


def main():
    with tarfile.open(baseline.FIXTURE_ARCHIVE,'r:gz') as archive:
        fixture=archive.extractfile(baseline.FIXTURE_MEMBER).read()
    cases=json.loads(fixture)['cases']
    scalars=[int(case['scalar_hex'],16)%baseline.ORDER for case in cases]
    result={'schema':1,'fixture_sha256':sha256(fixture).hexdigest(),
            'checked_distinct_scalars':len(scalars),
            'terminal_norm_limit_exclusive':TERMINAL_NORM_LIMIT,
            'terminal_absolute_coordinate_limit_inclusive':TERMINAL_COORD_LIMIT,
            'selector_lift_range':[-2,2],'selector_b_center_radius':2,
            'candidates':[screen(k,scalars) for k in (5,6,7)]}
    previous=json.loads((HERE/'sparse-tau-radix-screen.json').read_text())
    reference=result['candidates'][-1]
    assert reference['k']==7
    for key in ('digit_table_sha256','digit_seed_sha256','terminal_pairs_sha256'):
        assert reference[key]==previous[key]
    assert reference['first_frozen_fixture_terminal_step']==previous['steps']==15
    assert reference['digit_seed_count_including_zero']==previous['digit_seed_count_including_zero']
    (HERE/'sparse-radix-family-screen.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'candidates':[{key:value for key,value in row.items()
                                    if key in ('k','radix_norm','digit_seed_count_including_zero',
                                               'first_frozen_fixture_terminal_step','terminal_max_norm')}
                                     for row in result['candidates']]},sort_keys=True))


if __name__=='__main__':
    main()
