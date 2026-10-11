"""Independently check all target-derived N41 linear-gate decisions in Sage."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
FIXTURE=ROOT/'n41_transport_cubic_s8_20261011/fixture.json'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    result=json.loads((HERE/'linear_result_v2.json').read_text())
    protocol=json.loads((HERE/'linear_protocol_v2.json').read_text())
    fixture=json.loads(FIXTURE.read_text())
    assert result['status']=='PASS_N41_TARGET_DERIVED_LAST_PAIR_LINEAR_GATE_V2'
    assert result['fourth_pair_rotation']==30
    assert protocol['source_sha256']['producer']==sha(HERE/'linear_last_pair_sage_v2.py')
    r=PolynomialRing(GF(2),'t');t=r.gen();F=GF(2**41,'t',modulus=t**41+t**3+1)
    E=EllipticCurve(F,[1,0,0,0,1]);zero=E(0)
    def dec(x):return F(r([(x>>i)&1 for i in range(41)]))
    def bits(x):
        coeff=x.polynomial().list()
        return [int(coeff[i]) if i<len(coeff) else 0 for i in range(41)]
    def halftrace(x):
        out=F.zero()
        for _ in range(21):
            out+=x;x=x**4
        return out
    s_basis=[t**(i+1) for i in range(6)]
    p_basis=[t**(i+2) for i in range(11)]
    def gate(coords):
        P=E(dec(coords[0]),dec(coords[1]));assert P!=zero and P[0]!=0
        z=1/P[0];assert z.trace()==0
        cols=[halftrace((F(v)**(2**30))**2) for v in s_basis]
        cols += [z*(F(v)**(2**30)) for v in p_basis]
        cols += [F.one()]
        M=matrix(GF(2),41,18,lambda row,col:bits(cols[col])[row])
        rhs=vector(GF(2),bits(halftrace(z**2)))
        return M.rank()==M.augment(rhs).rank(),M.rank()
    decisions=[]
    for item in result['candidates']:
        decision,rank=gate(item['required_raw_fourth'])
        assert decision==item['linear_gate_pass'] and rank==item['linear_system_rank']
        decisions.append(decision)
    assert len(decisions)==63 and not any(decisions)
    known=fixture['pair_points'][3]
    known_decision,known_rank=gate(known)
    assert known_decision
    audit={'status':'PASS_INDEPENDENT_SAGE_N41_LINEAR_GATE_REPLAY',
           'negative_candidates_checked':len(decisions),
           'negative_candidates_passing':sum(decisions),
           'known_exact_pair_positive_pass':known_decision,
           'known_exact_pair_rank':known_rank,
           'sha256':{'linear_result_v2.json':sha(HERE/'linear_result_v2.json'),
                     'linear_protocol_v2.json':sha(HERE/'linear_protocol_v2.json'),
                     'fixture.json':sha(FIXTURE),
                     'audit_linear_v2_sage.py':sha(HERE/'audit_linear_v2_sage.py'),
                     'sage_runtime_info.json':sha(HERE/'sage_runtime_info.json')}}
    (HERE/'linear_audit_v2.json').write_text(json.dumps(audit,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':audit['status'],
                      'negative_candidates_checked':len(decisions),
                      'negative_candidates_passing':sum(decisions)}))

if __name__=='__main__':main()
