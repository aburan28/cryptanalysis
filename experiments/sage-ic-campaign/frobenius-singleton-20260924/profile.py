"""Profile wrapper overhead in repeated public binary Frobenius calls."""
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_batch, binary_batch_ntl, hom_frobenius

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


intent = json.loads((HERE / 'intent-profile-v1.json').read_text())
for name, expected in intent['baseline_hashes'].items():
    assert digest(HERE / 'baseline' / name) == expected
assert digest(binary_batch_ntl.__file__) == intent['native_binary_sha256']
assert digest(hom_frobenius.__file__) == intent['baseline_hashes']['hom_frobenius.py']
out = HERE / 'run-001'
out.mkdir(exist_ok=False)
(out / 'execution.json').write_text(json.dumps({
    'intent_sha256': digest(HERE / 'intent-profile-v1.json'),
    'script_sha256': digest(Path(__file__)),
}, indent=2) + '\n')

cls = hom_frobenius.EllipticCurveHom_frobenius
original = cls._call_
rows = []
try:
    for index, spec in enumerate(intent['cases']):
        case = dict(spec, seed=intent['seed_base'] + index)
        field = GF(2**case['degree'], 'z', impl='ntl')
        curve = EllipticCurve(field, [1, 1, 0, 0, 1])
        points, attempts = generate(curve, case['points'], case['seed'])
        phi = curve.frobenius_isogeny(case['power'])
        expected = [phi(point) for point in points]

        def direct(self, point):
            prepared = (binary_batch._point_data(self._domain, point),)
            return binary_batch_ntl._frobenius_prepared(
                self._domain, prepared, int(self._n))[0]

        methods = {'installed': original, 'direct_prepared': direct}
        trials = []
        for round_index in range(intent['rounds']):
            order = list(methods)
            random.Random(case['seed'] + round_index).shuffle(order)
            measured = {}
            for arm in order:
                cls._call_ = methods[arm]
                start = time.perf_counter_ns()
                actual = [phi(point) for point in points]
                elapsed = (time.perf_counter_ns() - start) / 1e9
                assert actual == expected
                measured[arm] = elapsed
            trials.append({'order': order, 'seconds': measured})
        speedup = math.exp(statistics.median([
            math.log(trial['seconds']['installed'] /
                     trial['seconds']['direct_prepared']) for trial in trials]))
        row = {'case': case, 'trials': trials, 'speedup': speedup,
               'exact_outputs': True,
               'verified_outputs': case['points'] * (1 + intent['rounds']*2),
               'fixture_attempts': attempts}
        (out / f'cell-{index:02d}.json').write_text(json.dumps(row, indent=2) + '\n')
        rows.append(row)
        print(case['degree'], case['power'], f'{speedup:.3f}x', flush=True)
finally:
    cls._call_ = original
(out / 'summary.json').write_text(json.dumps({
    'cells': [{'case': row['case'], 'speedup': row['speedup']} for row in rows],
    'all_exact': all(row['exact_outputs'] for row in rows),
    'verified_outputs': sum(row['verified_outputs'] for row in rows),
}, indent=2) + '\n')
