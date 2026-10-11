"""Matched complete Frobenius API benchmark with exact Sage reference checks."""
import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, set_random_seed
from sage.schemes.elliptic_curves import binary_batch, binary_batch_ntl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'sage-binary-hardware'))
from public_points import generate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def incumbent_module():
    spec = importlib.util.spec_from_file_location('incumbent_frobenius',
                                                   HERE / 'baseline/binary_batch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case_run(case, rounds):
    set_random_seed(case['seed'])
    field = GF(2**case['degree'], 'z', impl='ntl')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    base, attempts = generate(curve, min(case['size'], 128), case['seed'])
    points = [base[i % len(base)] for i in range(case['size'])]
    phi = curve.frobenius_isogeny(case['power'])
    assert phi.degree() == 2**case['power'] and phi.codomain() == curve
    expected = [phi(P) for P in points]
    old = incumbent_module()
    arms = {'incumbent': lambda: old.frobenius_points(curve, points, case['power']),
            'candidate': lambda: binary_batch.frobenius_points(curve, points, case['power'])}

    def timed(label, calls):
        start = time.perf_counter_ns()
        for _ in range(calls):
            actual = arms[label]()
            if actual != expected:
                raise AssertionError(f'{label}: wrong Frobenius point')
            del actual
        return (time.perf_counter_ns() - start) / 1e9 / calls

    for label in arms:
        timed(label, 1)
    calls = max(4, math.ceil(4096 / len(expected)))
    orders = list(itertools.permutations(arms)) * (rounds // 2)
    random.Random(case['seed'] + case['degree'] + case['size']).shuffle(orders)
    samples = []
    for order in orders:
        samples.append({'order': order, 'seconds': {label: timed(label, calls)
                                                    for label in order}})
    ratios = [s['seconds']['incumbent'] / s['seconds']['candidate'] for s in samples]
    return {'case': case, 'rounds': samples, 'calls_per_sample': calls,
            'verified_outputs': len(expected) * calls * len(samples) * 2,
            'fixture_attempts': attempts, 'all_outputs_exact': True,
            'speedup': math.exp(statistics.median(map(math.log, ratios))),
            'incumbent_ms': 1000 * statistics.median(
                s['seconds']['incumbent'] for s in samples),
            'candidate_ms': 1000 * statistics.median(
                s['seconds']['candidate'] for s in samples)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--suite', choices=('primary', 'confirmation'), required=True)
    args = parser.parse_args()
    intent = json.loads((HERE / 'intent-v1.json').read_text())
    assert sha(HERE / 'baseline/binary_batch.py') == intent['incumbent']['python_sha256']
    assert sha(HERE / 'baseline/binary_batch_ntl.pyx') == intent['incumbent']['native_sha256']
    assert sha(next((HERE / 'baseline').glob('binary_batch_ntl*.so'))) == intent['incumbent']['native_binary_sha256']
    source_dir = HERE.parents[1] / 'third_party/sage-binary/src/sage/schemes/elliptic_curves'
    assert sha(source_dir / 'binary_batch.py') == sha(binary_batch.__file__)
    cases = [dict(c, seed=2026092481 + i + (100 if args.suite == 'confirmation' else 0))
             for i, c in enumerate(intent['evaluation'][args.suite + '_cases'])]
    args.out.mkdir(parents=True, exist_ok=False)
    rows = []
    for i, case in enumerate(cases):
        row = case_run(case, intent['evaluation']['rounds'])
        rows.append(row)
        (args.out / f'cell-{i:02d}.json').write_text(json.dumps(row, indent=2) + '\n')
        print(f"GF(2^{case['degree']}) {case['size']} power={case['power']}: "
              f"{row['speedup']:.3f}x", flush=True)
    summary = {'suite': args.suite, 'rounds': intent['evaluation']['rounds'],
               'incumbent_python_sha256': sha(HERE / 'baseline/binary_batch.py'),
               'candidate_python_sha256': sha(binary_batch.__file__),
               'candidate_native_sha256': sha(source_dir / 'binary_batch_ntl.pyx'),
               'candidate_binary_sha256': sha(binary_batch_ntl.__file__),
               'all_outputs_exact': True,
               'total_verified_outputs': sum(row['verified_outputs'] for row in rows),
               'geomean_speedup': math.exp(statistics.mean(
                   math.log(row['speedup']) for row in rows)),
               'cells': [{k: row[k] for k in ('case', 'speedup', 'incumbent_ms', 'candidate_ms')}
                         for row in rows]}
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
