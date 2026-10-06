"""Replays planted PDP queries; records separate setup and query phase diagnostics."""
import cProfile
import hashlib
import io
import json
from pathlib import Path
import pstats
import sys
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round2'))
from solve_dual import make_instance, solve_dual, compute_dual_basis

report = {'scope': 'Planted PDP correctness/phase diagnostic only; complete IC pipeline and natural relation yield unmeasured',
          'complete_dlp_cost': None, 'queries': []}
for seed in (101, 201, 202, 203, 204, 205):
    start = time.perf_counter_ns()
    instance = make_instance(31, 3, 6, seed=seed)
    setup = time.perf_counter_ns()-start
    for repetition in range(4):
        start = time.perf_counter_ns()
        result = solve_dual(instance, verifier='native')
        elapsed = time.perf_counter_ns()-start
        assert result['verified'] and result['groebner_verified'] and result['status'] == 'solved'
        report['queries'].append({'seed': seed, 'repetition': repetition, 'instance_setup_ns': setup,
                                  'query_ns': elapsed, 'result': result})
    print(seed, report['queries'][-1]['query_ns'], flush=True)
    (HERE / 'results/query-check.json').write_text(json.dumps(report, indent=2)+'\n')
# Explicit Python/subprocess parity on a small instance also covers fallback arm.
instance = make_instance(11, 3, 2, seed=101)
answers = [solve_dual(instance, verifier=verifier, transport=transport)
           for verifier in ('python', 'native', 'auto') for transport in ('library', 'subprocess')]
assert all(a['verified'] for a in answers)
assert len({(a['basis_sha256'], a['assignment']) for a in answers}) == 1
report['transport_verifier_combinations_equal'] = 6
with patch('solve_dual.CERTIFICATE_LIBRARY', HERE / 'build/absent-certificate-library'):
    fallback = solve_dual(instance, verifier='auto')
assert fallback['verifier'] == 'python' and fallback['verified']
assert (fallback['basis_sha256'], fallback['assignment']) == (answers[0]['basis_sha256'], answers[0]['assignment'])
report['missing_library_fallback_verified'] = True
instance = make_instance(31, 3, 6, seed=101)
profiler = cProfile.Profile()
profiler.enable()
result = solve_dual(instance, verifier='native')
profiler.disable()
assert result['verified']
stream = io.StringIO()
pstats.Stats(profiler, stream=stream).sort_stats('cumulative').print_stats(24)
(HERE / 'results/query-profile.txt').write_text(stream.getvalue())
paths = [HERE.parent / 'round2/solve_dual.py', HERE.parent.parent / 'pdp-scaling/boolean_certificate_native.py',
         HERE.parent.parent / 'pdp-scaling/descend.py', Path(__file__)]
report['sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
report['status'] = 'PASS'
(HERE / 'results/query-check.json').write_text(json.dumps(report, indent=2)+'\n')
print(stream.getvalue())
