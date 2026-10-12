"""Rebuild frozen kernels and bind every complete-query dependency."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent
spec=importlib.util.spec_from_file_location('native94_for95',P/'round94/build.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
native.HERE=HERE
original_sources=native.source_paths

def source_paths():
    paths=original_sources()+[P/'round94'/name for name in ('build.py','generate.py','query.py','audit.py')]
    paths += [P/'round4/descent_plan.py',P/'round60/input_plan.py',P/'round13/results/confirmation.json.gz']
    paths += [P.parent/'pdp-scaling'/name for name in ('descend.py','gf2n.py','sumpoly.py')]
    return list(dict.fromkeys(paths))

native.source_paths=source_paths

def build():
    native.build()
    sys.path.insert(0,str(P.parent/'pdp-scaling'))
    import sumpoly
    # A private freshly regenerated cache; never unpickle downloaded artifacts.
    sumpoly.CACHE=HERE/'build/sumpoly_cache.pkl'
    regenerated=sumpoly.summation_polynomials(4)
    import pickle
    sumpoly.CACHE.write_bytes(pickle.dumps(regenerated))
    assert sumpoly.load(4)==regenerated
    data=[dict(degree=k,monomials=[list(v) for v in sorted(values)]) for k,values in sorted(regenerated.items())]
    resource=HERE/'build/summation-polynomials.json';resource.write_text(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n')
    receipt=json.loads((HERE/'build/receipt.json').read_text())
    receipt.update(schema='complete-query-checker-build/1',resources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (resource,sumpoly.CACHE)},polynomial_degree=4)
    (HERE/'build/receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')

if __name__=='__main__':build()
