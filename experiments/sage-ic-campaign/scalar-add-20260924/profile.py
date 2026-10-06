"""Profile public binary point addition against a singleton native batch."""
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_batch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


intent = json.loads((HERE / 'intent-profile-v1.json').read_text())
for name, expected in intent['baseline_hashes'].items():
    assert digest(HERE / 'baseline' / name) == expected
out = HERE / 'run-001'
out.mkdir(exist_ok=False)
(out / 'execution.json').write_text(json.dumps({
    'intent_sha256': digest(HERE / 'intent-profile-v1.json'),
    'script_sha256': digest(Path(__file__)),
}, indent=2) + '\n')
rows = []
for index, spec in enumerate(intent['cases']):
    case = dict(spec, seed=intent['seed_base'] + index)
    field = GF(2**case['degree'], 'z', impl='ntl')
    curve = EllipticCurve(field, [1, case['a'], 0, 0, 1])
    points, attempts = generate(curve, min(case['pairs'], 128), case['seed'])
    pairs = [(points[i % len(points)], points[(5*i+7) % len(points)])
             for i in range(case['pairs'])]
    expected = [P+Q for P, Q in pairs]
    def compute(arm):
        if arm == 'scalar':
            return [P+Q for P, Q in pairs]
        return [binary_batch.add_pairs(curve, [(P, Q)])[0] for P, Q in pairs]
    trials = []
    for round_index in range(intent['rounds']):
        order = ['scalar', 'native_singleton']
        random.Random(case['seed'] + round_index).shuffle(order)
        seconds = {}
        for arm in order:
            start = time.perf_counter_ns()
            actual = compute(arm)
            seconds[arm] = (time.perf_counter_ns() - start) / 1e9
            assert actual == expected
        trials.append({'order': order, 'seconds': seconds})
    speedup = math.exp(statistics.median([
        math.log(t['seconds']['scalar'] / t['seconds']['native_singleton'])
        for t in trials]))
    row = {'case': case, 'trials': trials, 'speedup': speedup,
           'exact_outputs': True,
           'verified_outputs': case['pairs'] * (1 + intent['rounds']*2),
           'fixture_attempts': attempts}
    (out / f'cell-{index:02d}.json').write_text(json.dumps(row, indent=2) + '\n')
    rows.append(row)
    print(case['degree'], case['a'], f'{speedup:.3f}x', flush=True)
(out / 'summary.json').write_text(json.dumps({
    'cells': [{'case': row['case'], 'speedup': row['speedup']} for row in rows],
    'all_exact': all(row['exact_outputs'] for row in rows),
    'verified_outputs': sum(row['verified_outputs'] for row in rows),
}, indent=2) + '\n')
