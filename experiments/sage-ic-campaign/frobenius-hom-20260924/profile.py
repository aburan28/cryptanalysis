"""Exploratory public Frobenius-isogeny versus native-point-map profile."""
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves.binary_batch import frobenius_points
from sage.schemes.elliptic_curves.hom_frobenius import EllipticCurveHom_frobenius

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


intent = json.loads((HERE / 'intent-profile-v1.json').read_text())
for name, expected in intent['baseline_hashes'].items():
    assert digest(HERE / 'baseline' / name) == expected
out = HERE / 'run-001'
out.mkdir(exist_ok=False)
(out / 'execution.json').write_text(json.dumps({
    'intent_sha256': digest(HERE / 'intent-profile-v1.json'),
    'script_sha256': digest(Path(__file__)),
}, indent=2) + '\n')
original = EllipticCurveHom_frobenius._call_
rows = []
try:
    for index, spec in enumerate(intent['cases']):
        case = dict(spec, seed=intent['seed_base'] + index)
        field = GF(2**case['degree'], 'z', impl='ntl')
        curve = EllipticCurve(field, [1, 1, 0, 0, 1])
        points, attempts = generate(curve, case['points'], case['seed'])
        phi = curve.frobenius_isogeny(case['power'])
        assert phi.codomain() is curve
        expected = [phi(point) for point in points]

        def native_call(self, point):
            return frobenius_points(self._domain, [point], int(self._n))[0]

        def call(arm):
            if arm == 'native_batch':
                return frobenius_points(curve, points, case['power'])
            EllipticCurveHom_frobenius._call_ = original if arm == 'original' else native_call
            return [phi(point) for point in points]

        trials = []
        names = ['original', 'native_singleton', 'native_batch']
        for round_index in range(intent['rounds']):
            order = names[:]
            random.Random(case['seed'] + round_index).shuffle(order)
            measured = {}
            for arm in order:
                start = time.perf_counter_ns()
                actual = call(arm)
                elapsed = (time.perf_counter_ns() - start) / 1e9
                assert actual == expected
                measured[arm] = elapsed
            trials.append({'order': order, 'seconds': measured})
        speedups = {}
        for arm in ('native_singleton', 'native_batch'):
            speedups[arm] = math.exp(statistics.median([
                math.log(trial['seconds']['original'] / trial['seconds'][arm])
                for trial in trials]))
        row = {'case': case, 'trials': trials, 'speedup': speedups,
               'exact_outputs': True,
               'verified_outputs': case['points'] * (1 + intent['rounds'] * 3),
               'fixture_attempts': attempts}
        (out / f'cell-{index:02d}.json').write_text(json.dumps(row, indent=2) + '\n')
        rows.append(row)
        print(case['degree'], case['power'],
              f"singleton {speedups['native_singleton']:.3f}x",
              f"batch {speedups['native_batch']:.3f}x", flush=True)
finally:
    EllipticCurveHom_frobenius._call_ = original
(out / 'summary.json').write_text(json.dumps({
    'cells': [{'case': row['case'], 'speedup': row['speedup']} for row in rows],
    'all_exact': all(row['exact_outputs'] for row in rows),
    'verified_outputs': sum(row['verified_outputs'] for row in rows),
}, indent=2) + '\n')
