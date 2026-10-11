"""Paired exact checker timings on identical serialized algebraic proofs."""
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import time

from algebraic_certificate import verify

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('unpruned_certificate',HERE/'baseline/algebraic_certificate.py')
baseline=importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def main():
    source=HERE/'results/proof-benchmark-before-product.json.gz'
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    frozen=json.loads(gzip.decompress(source.read_bytes()))
    report={'scope':'Checker-only diagnostic, identical native derivation proofs; no proof-production or IC speedup claim',
            'source_receipt_sha256':source_hash,'platform':platform.platform(),'load_start':os.getloadavg(),'cases':[]}
    rng=random.Random(2026092513)
    for case in frozen['cases']:
        rows=[r for r in frozen['rows'] if r['name']==case['name'] and r['native'].get('verified')]
        if not rows:
            continue
        digest=rows[0]['native']['proof_sha256']
        data=frozen['certificates'][digest]
        samples=[]
        for repetition in range(16):
            order=['baseline','product']
            rng.shuffle(order)
            sample={'repetition':repetition,'warmup':repetition==0,'order':order}
            for arm in order:
                start=time.perf_counter_ns()
                result=(baseline.verify if arm=='baseline' else verify)(data['nvars'],data['equations'],data['basis'],data['proof'])
                sample[arm+'_ns']=time.perf_counter_ns()-start
                assert result['verified'],result
            samples.append(sample)
        logs=[math.log(s['baseline_ns']/s['product_ns']) for s in samples[1:]]
        bootstrap=sorted(math.exp(statistics.mean(rng.choices(logs,k=len(logs)))) for _ in range(2000))
        report['cases'].append({'name':case['name'],'proof_sha256':digest,'samples':samples,
            'baseline_median_ms':statistics.median(s['baseline_ns'] for s in samples[1:])/1e6,
            'product_median_ms':statistics.median(s['product_ns'] for s in samples[1:])/1e6,
            'paired_geomean_speedup':math.exp(statistics.mean(logs)),
            'paired_bootstrap_95pct':[bootstrap[49],bootstrap[1949]]})
    report['source_sha256']={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [Path(__file__),HERE/'algebraic_certificate.py',HERE/'baseline/algebraic_certificate.py']}
    report['load_end']=os.getloadavg()
    report['status']='PASS'
    (HERE/'results/checker-benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps([{k:v for k,v in case.items() if k!='samples'} for case in report['cases']],indent=2))


if __name__=='__main__':
    main()
