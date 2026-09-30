"""Generic GF(2) row provenance pilot; not an implementation speed claim."""
from pathlib import Path
import argparse,random,json,time,hashlib

def direct(rows):
    pivots={};xors=0
    for source,row in enumerate(rows):
        provenance=1<<source
        while row:
            pivot=row.bit_length()-1
            if pivot==0:return provenance,xors
            if pivot not in pivots:
                pivots[pivot]=(row,provenance);break
            old,witness=pivots[pivot]
            row^=old;provenance^=witness;xors+=1
    return None,xors

def deferred(rows):
    pivots={};xors=0;expanded=0
    for source,row in enumerate(rows):
        dependencies=0
        while row:
            pivot=row.bit_length()-1
            if pivot==0:
                provenance=1<<source
                while dependencies:
                    bit=dependencies&-dependencies
                    dependencies^=bit
                    prior=bit.bit_length()-1
                    _,origin,parents=pivots[prior]
                    assert not parents&((1<<(prior+1))-1)
                    provenance^=1<<origin
                    dependencies^=parents
                    expanded+=1
                return provenance,xors,expanded
            if pivot not in pivots:
                assert not dependencies&((1<<(pivot+1))-1)
                pivots[pivot]=(row,source,dependencies);break
            old,_,_=pivots[pivot]
            row^=old;dependencies^=1<<pivot;xors+=1
    return None,xors,expanded

def test(rows,oracle=False):
    old,xors=direct(rows)
    new,new_xors,expanded=deferred(rows)
    assert old==new and xors==new_xors
    if new is not None:
        value=0
        for i,row in enumerate(rows):
            if new>>i&1:value^=row
        assert value==1
    if oracle:
        span={0}
        for row in rows:span|={v^row for v in span}
        assert (old is not None)==(1 in span)
    return xors,expanded

start=time.monotonic();tiny=0
for encoding in range(1<<12):
    test([(encoding>>(3*i))&7 for i in range(4)],True);tiny+=1
rng=random.Random(2026092936);wide=0;counts=[]
for columns in (1,2,3,31,32,33,63,64,65,129,130,176):
    for count in (1,3,31,128,310):
        for _ in range(5):
            rows=[rng.getrandbits(columns) for _ in range(count)]
            xors,expanded=test(rows,count<=3)
            counts.append({'columns':columns,'rows':count,'reduction_xors':xors,'provenance_bit_toggles':xors,'expanded_pivots':expanded})
            wide+=1
record={'scope':'generic GF(2) delayed provenance reconstruction mathematical pilot; no native speedup claim','seed':2026092936,'tiny_exhaustive_matrices':tiny,'random_matrices':wide,'all_combination_bitsets_equivalent':True,'all_returned_identities_directly_verified':True,'tiny_span_oracle':True,'elapsed_seconds':time.monotonic()-start,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'counts':counts}
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path)
args=parser.parse_args()
if args.output:
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='counts'},indent=2))
