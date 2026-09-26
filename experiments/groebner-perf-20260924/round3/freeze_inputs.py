"""Freeze algebra-only certificate workloads; planted controls imply no IC yield."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round2'))
from solve_dual import _in_process, make_instance

cases = json.loads((HERE.parent / 'round2/scaling-fixtures.json').read_text())
for seed in range(201, 206):
    instance = make_instance(31, 3, 6, seed=seed)
    cases.append({'name': f'pdp-31-3-6-seed{seed}', 'nvars': instance.nvars,
                  'equations': [sorted(g) for g in instance.equations()], 'seed': seed})
workloads = []
for case in cases:
    basis, metrics, _ = _in_process(case['nvars'], case['equations'])
    assert basis is not None, metrics
    record = {'nvars': case['nvars'], 'equations': case['equations'], 'basis': basis,
              'monomial_order': 'degrevlex-popcount-then-negative-mask', 'field': 'GF(2)-Boolean-quotient'}
    digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    workloads.append({'name': case['name'], 'workload_sha256': digest, 'input': record})
    print(case['name'], digest, flush=True)
report = {'schema': 'boolean-certificate-component-inputs-v1', 'seed_start': 201, 'seed_count': 5,
          'scope': 'Algebra-only verification component; planted correctness controls, no IC candidate or natural relation yield',
          'cases': workloads}
(HERE / 'inputs.json').write_text(json.dumps(report, separators=(',', ':'))+'\n')
