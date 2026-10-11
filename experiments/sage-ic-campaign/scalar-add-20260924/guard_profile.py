"""Exploratory guarded native dispatch on the public P+Q operation."""
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, set_random_seed
from sage.schemes.elliptic_curves import binary_batch, ell_point

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


intent = json.loads((HERE / 'intent-guard-v1.json').read_text())
assert digest(ell_point.__file__) == intent['incumbent_source_sha256']
cls = ell_point.EllipticCurvePoint_finite_field
original = cls._add_


def guarded(self, other):
    if type(self) is cls and type(other) is cls:
        curve = self.curve()
        if other.curve() is curve and curve._point is cls:
            use = getattr(curve, '_binary_native_add', None)
            if use is None:
                field = curve.base_ring()
                use = False
                if field.characteristic() == 2 and binary_batch._native is not None:
                    try:
                        binary_batch._curve_coefficient(curve)
                        use = binary_batch._native.supports(field)
                    except ValueError:
                        pass
                curve._binary_native_add = use
            if use:
                return binary_batch.add_pairs(curve, ((self, other),))[0]
    return original(self, other)


out = HERE / 'run-002'
out.mkdir(exist_ok=False)
(out / 'execution.json').write_text(json.dumps({
    'intent_sha256': digest(HERE / 'intent-guard-v1.json'),
    'script_sha256': digest(Path(__file__)),
}, indent=2) + '\n')
rows = []
try:
    for phase in ('primary', 'confirmation'):
        for index, spec in enumerate(intent[phase + '_cases']):
            case = dict(spec, phase=phase,
                        seed=intent['seed_base_' + phase] + index)
            if case['field'] == 'prime':
                curve = EllipticCurve(GF(case['p']), [1, 1])
            else:
                field = GF(2**case['degree'], 'z', impl='ntl')
                if case.get('alternate_modulus'):
                    field = GF(2**case['degree'], 'w',
                               modulus=field.modulus().reverse(), impl='ntl')
                coefficients = ([1, 1, field.gen(), 0, 1]
                                if case['field'] == 'unsupported_binary'
                                else [1, case['a'], 0, 0, 1])
                curve = EllipticCurve(field, coefficients)
            set_random_seed(case['seed'])
            if case['field'] == 'binary':
                points, attempts = generate(curve, min(case['pairs'], 128), case['seed'])
            else:
                points = [curve.random_point() for _ in range(min(case['pairs'], 128))]
                attempts = len(points)
            pairs = [(points[i % len(points)], points[(5*i+7) % len(points)])
                     for i in range(case['pairs'])]
            expected = [P+Q for P, Q in pairs]
            trials = []
            for round_index in range(intent['rounds']):
                order = ['incumbent', 'candidate']
                random.Random(case['seed'] + round_index).shuffle(order)
                seconds = {}
                for arm in order:
                    cls._add_ = original if arm == 'incumbent' else guarded
                    start = time.perf_counter_ns()
                    actual = [P+Q for P, Q in pairs]
                    seconds[arm] = (time.perf_counter_ns() - start) / 1e9
                    assert actual == expected
                trials.append({'order': order, 'seconds': seconds})
            speedup = math.exp(statistics.median([
                math.log(t['seconds']['incumbent'] / t['seconds']['candidate'])
                for t in trials]))
            row = {'case': case, 'trials': trials, 'speedup': speedup,
                   'exact_outputs': True,
                   'verified_outputs': case['pairs'] * (1 + intent['rounds']*2),
                   'fixture_attempts': attempts}
            (out / f'cell-{len(rows):02d}.json').write_text(json.dumps(row, indent=2) + '\n')
            rows.append(row)
            print(phase, case['field'], case.get('degree', case.get('p')),
                  f'{speedup:.3f}x', flush=True)
finally:
    cls._add_ = original
(out / 'summary.json').write_text(json.dumps({
    'cells': [{'case': row['case'], 'speedup': row['speedup']} for row in rows],
    'all_exact': all(row['exact_outputs'] for row in rows),
    'verified_outputs': sum(row['verified_outputs'] for row in rows),
}, indent=2) + '\n')
