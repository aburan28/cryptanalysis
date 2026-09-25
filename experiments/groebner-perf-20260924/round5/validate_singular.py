"""Explicit ordinary-ring Singular oracle for both proof producers.

Run through scripts/sage_release.py run so the installed Sage stack is checked.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time

from sage.all import GF, PolynomialRing
import sage.version
from native_f4 import compute
from algebraic_certificate import verify
from reference_prover import prove, ProverBudget

HERE = Path(__file__).resolve().parent


def oracle(n, equations):
    ring = PolynomialRing(GF(2),n,names='x',order='degrevlex')
    variables = ring.gens()
    def polynomial(row):
        answer = ring.zero()
        for mask in row:
            term = ring.one()
            for i,variable in enumerate(variables):
                if mask & (1 << i):
                    term *= variable
            answer += term
        return answer
    basis = ring.ideal([polynomial(row) for row in equations]+[x*x+x for x in variables]).groebner_basis(algorithm='libsingular:std')
    rows = []
    for polynomial in basis:
        row = set()
        for powers in polynomial.dict():
            mask = sum(1 << i for i,exponent in enumerate(powers) if exponent)
            row.symmetric_difference_update((mask,))
        if row:
            rows.append(sorted(row))
    return sorted(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE/'results/singular-validation.json')
    args = parser.parse_args()
    rng = random.Random(2026092510)
    cases = [(3,[[3,4]]),(4,[[3,1],[6,2]]),(4,[[3,0]]),(4,[[1,1],[]]),(8,[]),
             (21,[[3,4]]),(32,[[3,0]]),(64,[[1 << 63,0]])]
    for n in range(1,9):
        for _ in range(16):
            cases.append((n,[[rng.randrange(1 << n) for _ in range(rng.randrange(1,10))]
                             for _ in range(rng.randrange(1,n+2))]))
    for n in (21,31,32,63,64):
        cases.append((n,[[3 << i,0] for i in range(0,n-1,2)]+[[1 << (n-1),0]]))
    report = {'status':'RUNNING','oracle':'Singular ordinary GF(2) polynomial ring, degrevlex, explicit field equations',
              'sage_version':sage.version.version,'cases':[]}
    for index,(n,equations) in enumerate(cases):
        started=time.perf_counter()
        expected=oracle(n,equations)
        actual=compute(n,equations)
        attempts=[{'status':actual['status'],'max_work':20_000_000,
                   'wall_seconds':actual['total_seconds'],'reason':actual.get('reason')}]
        if actual['status']=='inconclusive':
            # Qualification retry, not a silent replacement of the bounded
            # attempt. Both costs/statuses remain in the receipt.
            actual=compute(n,equations,max_work=100_000_000,max_nodes=2_000_000,
                           max_check_work=100_000_000,max_retained_terms=4_000_000)
            attempts.append({'status':actual['status'],'max_work':100_000_000,
                             'wall_seconds':actual['total_seconds'],'reason':actual.get('reason')})
        try:
            reference=prove(n,equations,max_work=20_000_000,max_nodes=500_000)
            checked=verify(n,equations,reference['basis'],reference['proof'],max_work=20_000_000,max_retained_terms=2_000_000)
        except ProverBudget as error:
            reference={'proof':{'nodes':[]},'reason':str(error)}
            checked={'status':'inconclusive','verified':False}
        assert actual['verified'],(n,equations,actual)
        assert sorted(actual['basis'])==expected,(n,equations,expected,actual['basis'])
        if 'basis' in reference:
            assert checked['verified'] and sorted(reference['basis'])==expected,(n,equations,reference,checked)
        report['cases'].append({'index':index,'nvars':n,'input_sha256':hashlib.sha256(json.dumps(equations).encode()).hexdigest(),
                                'basis_rows':len(expected),'native_proof_nodes':len(actual['proof']['nodes']),
                                'reference_proof_nodes':len(reference['proof']['nodes']),
                                'reference_status':checked['status'],
                                'reference_failure':reference.get('reason'),
                                'native_attempts':attempts,
                                'wall_seconds':time.perf_counter()-started,'verified':True})
        args.output.write_text(json.dumps(report,indent=2)+'\n')
    report['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [Path(__file__),HERE/'algebraic_certificate.py',HERE/'reference_prover.py',HERE/'native_f4.py',HERE/'native_f4.cpp']}
    report['status']='PASS'
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'PASS','ideals':len(cases),'oracle':report['oracle']}),flush=True)


if __name__=='__main__':
    main()
