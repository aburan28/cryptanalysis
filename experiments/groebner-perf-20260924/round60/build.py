"""Rebuild the unchanged round 58 engines and bind the complete-query harness."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import hashlib
import gzip
HERE=Path(__file__).resolve().parent
P=HERE.parent
ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=HERE/'build';out.mkdir(exist_ok=True)
    command=[sys.executable,str(P/'round58/build.py')]
    subprocess.run(command,check=True)
    previous=json.loads((P/'round58/build/receipt.json').read_text())
    sources={str((P/name).relative_to(ROOT)):value for name,value in previous['sources'].items()}
    for directory in (HERE,P/'round56',P/'round57',P/'round59',P/'round4',P/'round2',P/'round5',P.parent/'pdp-scaling'):
        for pattern in ('*.py','*.cpp','*.h','*.json'):
            for path in directory.glob(pattern):sources[str(path.relative_to(ROOT))]=sha(path)
    for path in (P/'round58/results/frozen-screen.json.gz',P/'round13/results/confirmation.json.gz'):
        sources[str(path.relative_to(ROOT))]=sha(path)
    generated={str((P/'round58/build'/name).relative_to(ROOT)):value for name,value in previous['generated'].items()}
    binaries={str((P/'round58/build'/name).relative_to(ROOT)):value for name,value in previous['binaries'].items()}
    # The reference descent also reads a target-independent polynomial cache.
    # Validate its contents against fresh symbolic construction and bind the
    # actual bytes before any fixture/layout preparation or measured query.
    sys.path.insert(0,str(P.parent/'pdp-scaling'))
    import sumpoly
    fixtures=json.loads(gzip.decompress((P/'round13/results/confirmation.json.gz').read_bytes()))['inputs']
    degree=max(case['m']+1 for case in fixtures if case['boundary']=='pdp')
    cached=sumpoly.load(degree);regenerated=sumpoly.summation_polynomials(degree)
    assert all(cached[k]==value for k,value in regenerated.items())
    resources={str(sumpoly.CACHE.relative_to(ROOT)):sha(sumpoly.CACHE)}
    receipt={'schema':'sparse-f4-query-build/1','commands':[command],'sources':sources,'generated':generated,'binaries':binaries,
             'resources':resources,'polynomial_cache_checked_through_degree':degree,
             'plan_sha256':sha(HERE/'measurement_plan.json'),'compiler':previous['compiler'],
             'platform':platform.platform(),'architecture':platform.machine(),'timing_eligible':False}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
