"""Exact rank census for the N41 relaxed-pair linear maps L_p."""

import hashlib
import importlib.util
import json
import time
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'n41_transport_cubic_s8_20261011/circuit.py'
spec=importlib.util.spec_from_file_location('n41_rank_preflight_base',BASE)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    field=base.Field()
    def halftrace(x):
        out=0
        for _ in range(21):
            out^=x;x=field.square(field.square(x))
        return out
    halfcols=[halftrace(field.square(1<<i)) for i in range(41)]
    def rank(cols):
        pivots={}
        for col in cols:
            while col:
                bit=col.bit_length()-1
                if bit in pivots:col^=pivots[bit]
                else:pivots[bit]=col;break
        return len(pivots)
    started=time.monotonic()
    counts=Counter()
    for mask in range(2048):
        p=mask<<2
        cols=[field.mul(p,1<<i)^halfcols[i] for i in range(41)]
        counts[rank(cols)]+=1
    result={'status':'PASS_EXACT_N41_RELAXED_PAIR_LINEAR_MAP_RANK_CENSUS',
            'field':'GF(2)[t]/(t^41+t^3+1)',
            'product_span':'span(t^2,...,t^12)',
            'map':'L_p(z)=p*z+H(z^2)',
            'product_coefficients_tested':2048,
            'rank_histogram':{str(k):counts[k] for k in sorted(counts)},
            'nullity_histogram':{str(41-k):counts[k] for k in sorted(counts)},
            'elapsed_seconds_exploratory':time.monotonic()-started,
            'source_sha256':{'rank_preflight.py':sha(HERE/'rank_preflight.py'),
                             'n41_circuit.py':sha(BASE)}}
    assert dict(counts)=={39:255,40:1269,41:524}
    (HERE/'rank_preflight.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':result['status'],
                      'rank_histogram':result['rank_histogram']}))

if __name__=='__main__':main()
