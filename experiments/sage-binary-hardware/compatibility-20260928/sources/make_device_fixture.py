"""Create public Sage-verified field fixtures for remote GPU validation."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import numpy as np
from sage.all import GF,EllipticCurve
from load_hardware import FrobeniusPlan,candidate,SOURCE

parser=argparse.ArgumentParser()
parser.add_argument('--out',required=True,type=Path)
args=parser.parse_args()
args.out.mkdir(parents=True,exist_ok=False)
rng=random.Random(2026092303)
records=[]
for degree in (19,31,67,131):
    F=GF(2**degree,'z');E=EllipticCurve(F,[1,1,0,0,1])
    for power in (1,7,65):
        with FrobeniusPlan(E,power,'cpu') as plan:
            values=[0,1,(1<<degree)-1]+[rng.getrandbits(degree) for _ in range(254)]
            data=np.array([[(v>>(32*w))&0xffffffff for w in range(plan.words)] for v in values],dtype=np.uint32)
            images=[int(F.from_integer(v).frobenius(power%degree).to_integer()) for v in values]
            expected=np.array([[(v>>(32*w))&0xffffffff for w in range(plan.words)] for v in images],dtype=np.uint32)
            assert np.array_equal(plan.apply_words(data),expected)
            path=args.out/f'field-{degree}-power-{power}.npz'
            np.savez(path,table=plan._table,data=data,expected=expected)
            records.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                            'degree':degree,'power':power,'bytes':plan.bytes,'words':plan.words,
                            'modulus':str(F.modulus()),'coordinates':len(data)})
sources={}
for backend in ('cuda','opencl'):
    path=args.out/f'kernel.{backend}'
    path.write_text(candidate.kernel_source(backend))
    sources[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
(args.out/'manifest.json').write_text(json.dumps({'scope':'public field-coordinate maps; correctness fixture, not full Sage-point performance',
    'sage_source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'kernel_sha256':sources,'cases':records},indent=2)+'\n')
print('Wrote',len(records),'Sage-verified public fixtures.')
