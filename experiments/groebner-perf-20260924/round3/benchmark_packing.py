"""Paired check of the native verifier's initial list versus array transport."""
import importlib.util
import json
import hashlib
from pathlib import Path
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'pdp-scaling'))
from boolean_certificate_native import certify_boolean_basis_native, DEFAULT_LIBRARY
spec = importlib.util.spec_from_file_location('list_packing', HERE / 'baseline/native-list-packing.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
report = {'scope': 'Native verification component, same native binary and same certificate; only Python packing differs', 'cells': []}
for case in json.loads((HERE / 'inputs.json').read_text())['cases']:
    if case['input']['nvars'] != 18: continue
    data = case['input']
    samples = []
    for repeat in range(12):
        sample = {'warmup': repeat == 0}
        for name in (('list', 'array') if repeat%2 == 0 else ('array', 'list')):
            fn = old.certify_boolean_basis_native if name == 'list' else certify_boolean_basis_native
            start = time.perf_counter_ns()
            result = fn(18, data['equations'], data['basis'], library=DEFAULT_LIBRARY)
            sample[name+'_ns'] = time.perf_counter_ns()-start
            assert result['verified']
        samples.append(sample)
    report['cells'].append({'name': case['name'], 'workload_sha256': case['workload_sha256'], 'samples': samples,
                          'median_ns': {n: statistics.median(s[n+'_ns'] for s in samples[1:]) for n in ('list', 'array')}})
paths = [HERE / 'baseline/native-list-packing.py', HERE.parent.parent / 'pdp-scaling/boolean_certificate_native.py', DEFAULT_LIBRARY, Path(__file__)]
report['sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(HERE / 'results/packing-benchmark.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps([{k:v for k,v in c.items() if k != 'samples'} for c in report['cells']], indent=2))
