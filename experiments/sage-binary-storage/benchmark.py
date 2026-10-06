"""Paired, exact-output benchmark for the native batch storage change.

Run with experiments/sage-binary-arithmetic/run-sage.sh -python.
"""
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
import types
from pathlib import Path

from sage.all import EllipticCurve, GF, set_random_seed
from sage.schemes.elliptic_curves import binary_batch, binary_batch_ntl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'sage-binary-hardware'))
from public_points import generate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def incumbent_module():
    spec = importlib.util.spec_from_file_location('incumbent',
                                                   HERE / 'baseline/binary_batch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package_name = '_sage_storage_incumbent'
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package
    name = package_name + '.binary_batch_ntl'
    binary = next((HERE / 'baseline').glob('binary_batch_ntl*.so'))
    native_spec = importlib.util.spec_from_file_location(name, binary)
    native = importlib.util.module_from_spec(native_spec)
    sys.modules[name] = native
    native_spec.loader.exec_module(native)
    module._native = native
    assert module._native is not binary_batch_ntl
    return module


def run_case(case, rounds):
    set_random_seed(case['seed'])
    field = GF(2**case['degree'], 'z', impl='ntl')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    points, attempts = generate(curve, 2*case['side'], case['seed'])
    left, right = points[:case['side']], points[case['side']:]
    expected = [P + Q for P in left for Q in right]
    incumbent = incumbent_module()
    arms = {}
    for label, module in (('incumbent', incumbent), ('candidate', binary_batch)):
        if case['api'] == 'pairs':
            arms[label] = lambda m=module: m.add_pairs(curve,
                ((P, Q) for P in left for Q in right))
        else:
            arms[label] = lambda m=module: m.add_cartesian(curve, left, right)

    def timed(label, calls):
        start = time.perf_counter_ns()
        for _ in range(calls):
            actual = arms[label]()
            if actual != expected:
                raise AssertionError(f'{label}: wrong point sum')
            del actual
        return (time.perf_counter_ns() - start) / 1e9 / calls

    for label in arms:
        timed(label, 1)
    calls = max(4, math.ceil(4096 / len(expected)))
    orders = list(itertools.permutations(arms)) * (rounds // 2)
    random.Random(case['seed'] + case['degree'] + case['side']).shuffle(orders)
    samples = []
    for order in orders:
        samples.append({'order': order, 'seconds': {label: timed(label, calls)
                                                    for label in order}})
    ratios = [s['seconds']['incumbent'] / s['seconds']['candidate'] for s in samples]
    return {'case': case, 'rounds': samples, 'calls_per_sample': calls,
            'verified_outputs': len(expected) * calls * len(samples) * 2,
            'fixture_attempts': attempts,
            'speedup': math.exp(statistics.median(map(math.log, ratios))),
            'incumbent_ms': 1000 * statistics.median(
                s['seconds']['incumbent'] for s in samples),
            'candidate_ms': 1000 * statistics.median(
                s['seconds']['candidate'] for s in samples)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--suite', choices=('pilot', 'confirmation'), default='pilot')
    parser.add_argument('--rounds', type=int, default=12)
    args = parser.parse_args()
    if args.rounds < 2 or args.rounds % 2:
        parser.error('--rounds must be positive and even')
    intent = json.loads((HERE / 'intent-v1.json').read_text())
    assert sha(HERE / 'baseline/binary_batch_ntl.pyx') == intent['incumbent']['source_sha256']
    old_so = next((HERE / 'baseline').glob('binary_batch_ntl*.so'))
    assert sha(old_so) == intent['incumbent']['installed_binary_sha256']
    cases = intent['evaluation']['pilot_cases'] if args.suite == 'pilot' else [
        {'degree': degree, 'side': side, 'api': api}
        for degree, side, api in ((31, 16, 'pairs'), (31, 48, 'cartesian'),
                                  (163, 16, 'cartesian'), (163, 48, 'pairs'))]
    cases = [dict(case, seed=2026092461 + i) for i, case in enumerate(cases)]
    args.out.mkdir(parents=True, exist_ok=False)
    rows = []
    for i, case in enumerate(cases):
        row = run_case(case, args.rounds)
        rows.append(row)
        (args.out / f'cell-{i:02d}.json').write_text(json.dumps(row, indent=2) + '\n')
        print(f"GF(2^{case['degree']}) {case['side']**2} {case['api']}: "
              f"{row['speedup']:.3f}x", flush=True)
    summary = {'suite': args.suite, 'rounds': args.rounds,
               'incumbent_binary_sha256': sha(old_so),
               'candidate_binary_sha256': sha(binary_batch_ntl.__file__),
               'candidate_source_sha256': sha(HERE.parents[1] /
                   'third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_batch_ntl.pyx'),
               'all_outputs_exact': True,
               'total_verified_outputs': sum(r['verified_outputs'] for r in rows),
               'geomean_speedup': math.exp(statistics.mean(
                   math.log(r['speedup']) for r in rows)),
               'cells': [{k: row[k] for k in ('case', 'speedup', 'incumbent_ms', 'candidate_ms')}
                         for row in rows]}
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
