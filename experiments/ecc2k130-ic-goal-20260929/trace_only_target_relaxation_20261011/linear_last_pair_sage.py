"""Test a target-derived fourth output against the sparse-product S3 linear gate."""

import hashlib
import json
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INPUT = ROOT/'n131_w18_four_pairs/native_join/native_input.txt'
FIXTURE = ROOT/'n41_transport_cubic_s8_20261011/fixture.json'
N41 = ROOT/'n41_transport_cubic_s8_20261011'
sys.path.insert(0, str(N41))
import circuit  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def halftrace(field, x):
    out = 0
    for _ in range(21):
        out ^= x
        x = field.square(field.square(x))
    return out


def in_span(columns, rhs):
    pivots = {}
    for column in columns:
        while column:
            bit = column.bit_length()-1
            if bit in pivots:
                column ^= pivots[bit]
            else:
                pivots[bit] = column
                break
    while rhs:
        bit = rhs.bit_length()-1
        if bit not in pivots:
            return False, len(pivots)
        rhs ^= pivots[bit]
    return True, len(pivots)


def main():
    protocol = json.loads((HERE/'linear_protocol.json').read_text())
    assert protocol['status'] == 'FROZEN_N41_TARGET_DERIVED_LAST_PAIR_LINEAR_GATE'
    for name, path in {'producer': HERE/'linear_last_pair_sage.py',
                       'input': INPUT, 'fixture': FIXTURE,
                       'n41_circuit': N41/'circuit.py',
                       'runtime': HERE/'sage_runtime_info.json'}.items():
        assert protocol['source_sha256'][name] == sha(path)
    fixture = json.loads(FIXTURE.read_text())
    ring = PolynomialRing(GF(2), 't')
    t = ring.gen()
    field = GF(2**41, 't', modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1,0,0,0,1])
    zero = curve(0)
    fast = circuit.Field()

    def dec(value):
        return field(ring([(value >> i) & 1 for i in range(41)]))

    def enc(value):
        return sum(int(bit) << i for i,bit in enumerate(value.polynomial().list()))

    def coords(point):
        return [enc(point[0]),enc(point[1])]

    def ordinary(point):
        return point != zero and point[0] != 0

    def chi(point):
        assert ordinary(point)
        return int((1/point[0]).trace())

    def pi(point):
        return curve(point[0]**2,point[1]**2)

    def ht_sage(value):
        out = field.zero()
        for _ in range(21):
            out += value
            value = value**4
        return out

    s_columns = [halftrace(fast,fast.square(1 << (i+1))) for i in range(6)]
    assert all(value == enc(ht_sage(dec(1 << (i+1))**2))
               for i,value in enumerate(s_columns))

    def gate(point):
        assert ordinary(point) and chi(point) == 0
        z = fast.inv(enc(point[0]))
        rhs = halftrace(fast,fast.square(z))
        columns = s_columns + [fast.mul(z,1 << (i+2)) for i in range(11)] + [1]
        return in_span(columns,rhs)

    tokens = list(map(int,INPUT.read_text().split()))
    assert tokens[2:4] == [549756390943,8]
    original = curve(dec(tokens[0]),dec(tokens[1]))
    target = curve(*[dec(v) for v in fixture['raw_target_preimages'][0]])
    assert 4*target == original+pi(original)
    assert chi(target) == 0
    slots,cursor=[],4
    for slot_index in range(8):
        count=tokens[cursor]
        cursor+=1
        assert count==64
        rows=[]
        rotation=(0,0,10,10,20,20,30,30)[slot_index]
        for _ in range(64):
            x,y,col,mask,branch,sign=tokens[cursor:cursor+6]
            cursor+=6
            w=dec(mask << 1)**(2**rotation)
            u=ht_sage(w)+branch
            point=curve.lift_x(1+1/u,all=True)[sign]
            assert coords(4*point)==[x,y]
            moved=point+pi(point)
            assert 4*moved == (4*point)+pi(4*point)
            assert enc(1/moved[0])==enc(w)
            rows.append((moved,col,mask,branch,sign))
        slots.append(rows)
    assert cursor==len(tokens)
    assert all(slots[2*i]==slots[2*i+1] for i in range(4))
    pair_lists=[]
    for group in range(4):
        slot=slots[2*group]
        rows=[]
        for i in range(64):
            for j in range(i+1,64):
                if slot[i][1]==slot[j][1]:
                    continue
                total=slot[i][0]+slot[j][0]
                assert ordinary(total) and chi(total)==0
                rows.append((total,slot[i][2]^slot[j][2],
                             (slot[i][1],slot[j][1]),(i,j)))
        assert len(rows)==1956
        pair_lists.append(rows)
    first_by_sum={}
    for row in pair_lists[0]:
        first_by_sum.setdefault(row[1],row)
    assert set(first_by_sum)==set(range(1,64))
    positives_start=time.monotonic_ns()
    positive=[]
    for row in pair_lists[3]:
        accepted,rank=gate(row[0])
        positive.append((accepted,rank))
    positive_ns=time.monotonic_ns()-positives_start
    assert all(flag for flag,_ in positive)
    search_start=time.monotonic_ns()
    candidates=[]
    for seed_sum in range(1,64):
        A=first_by_sum[seed_sum]
        found=None
        for B in pair_lists[1]:
            if len(set(A[2]+B[2]))!=4:
                continue
            middle0=A[0]+B[0]
            if not ordinary(middle0):
                continue
            for C in pair_lists[2]:
                if len(set(A[2]+B[2]+C[2]))!=6:
                    continue
                D=target-A[0]-B[0]-C[0]
                middle1=C[0]+D
                if not ordinary(D) or not ordinary(middle1):
                    continue
                assert chi(D)==0 and middle0+middle1==target
                found=(A,B,C,D)
                break
            if found:
                break
        assert found is not None
        A,B,C,D=found
        candidates.append({'first_seed_sum':seed_sum,'required_raw_fourth':coords(D),
                           'first_three_pair_ids':[A[3],B[3],C[3]]})
    candidate_search_ns=time.monotonic_ns()-search_start
    gate_start=time.monotonic_ns()
    for item in candidates:
        point=curve(*[dec(v) for v in item['required_raw_fourth']])
        item['linear_gate_pass'],item['linear_system_rank']=gate(point)
    gate_ns=time.monotonic_ns()-gate_start
    passes=sum(item['linear_gate_pass'] for item in candidates)
    result={'status':'PASS_N41_TARGET_DERIVED_LAST_PAIR_LINEAR_GATE',
            'target_raw_preimage':coords(target),
            'positive_exact_fourth_pairs_tested':len(positive),
            'positive_exact_fourth_pairs_accepted':sum(flag for flag,_ in positive),
            'positive_rank_range':[min(rank for _,rank in positive),
                                   max(rank for _,rank in positive)],
            'trace_only_first_pair_sums':63,
            'target_derived_fourth_outputs_tested':len(candidates),
            'target_derived_fourth_outputs_passing_linear_gate':passes,
            'candidates':candidates,
            'phase_ns_exploratory':{'positive_gate_scan':positive_ns,
                                    'target_candidate_construction':candidate_search_ns,
                                    'target_candidate_linear_gate':gate_ns},
            'source_sha256':{'protocol':sha(HERE/'linear_protocol.json'),
                             'producer':sha(HERE/'linear_last_pair_sage.py'),
                             'input':sha(INPUT),'fixture':sha(FIXTURE),
                             'runtime':sha(HERE/'sage_runtime_info.json')}}
    (HERE/'linear_result.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':result['status'],
                      'positive_accepted':result['positive_exact_fourth_pairs_accepted'],
                      'target_candidate_passes':passes,
                      'phase_ns_exploratory':result['phase_ns_exploratory']}))


if __name__=='__main__':
    main()
