"""Paired complete public P+Q benchmark for native binary dispatch."""
import argparse
import hashlib
import importlib.util
import json
import math
import random
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, set_random_seed
from sage.schemes.elliptic_curves import ell_point

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def original_method():
    spec = importlib.util.spec_from_file_location('old_ell_point',
                                                   HERE / 'baseline/ell_point.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.EllipticCurvePoint_field._add_


def worker(case, out):
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
    cls = ell_point.EllipticCurvePoint_finite_field
    candidate = cls._add_
    original = original_method()
    cls._add_ = original
    try:
        expected = [P+Q for P, Q in pairs]
        orders = [('incumbent', 'candidate'),
                  ('candidate', 'incumbent')] * 12
        random.Random(case['seed']).shuffle(orders)
        methods = {'incumbent': original, 'candidate': candidate}
        trials = []
        for order in orders:
            seconds = {}
            for arm in order:
                cls._add_ = methods[arm]
                start = time.perf_counter_ns()
                actual = [P+Q for P, Q in pairs]
                seconds[arm] = (time.perf_counter_ns()-start)/1e9
                assert actual == expected
            trials.append({'order': order, 'seconds': seconds})
    finally:
        cls._add_ = candidate
    speedup = math.exp(statistics.median([
        math.log(t['seconds']['incumbent'] / t['seconds']['candidate'])
        for t in trials]))
    row = {'case': case, 'trials': trials, 'speedup': speedup,
           'exact_outputs': True,
           'verified_outputs': case['pairs'] * (1 + 24*2),
           'fixture_attempts': attempts,
           'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'incumbent_source_sha256': digest(HERE / 'baseline/ell_point.py'),
           'candidate_source_sha256': digest(ell_point.__file__)}
    out.write_text(json.dumps(row, indent=2) + '\n')
    print(case['field'], case.get('degree', case.get('p')),
          f'{speedup:.3f}x', flush=True)


def parent(out):
    intent = json.loads((HERE / 'intent-candidate-v2.json').read_text())
    install = json.loads((HERE / 'install-002/install.json').read_text())
    assert digest(HERE / 'baseline/ell_point.py') == intent['incumbent_source_sha256']
    assert digest(ell_point.__file__) == install['installed_sha256'] == intent['candidate_source_sha256']
    out.mkdir(parents=True, exist_ok=False)
    (out / 'execution.json').write_text(json.dumps({
        'intent_sha256': digest(HERE / 'intent-candidate-v2.json'),
        'benchmark_sha256': digest(__file__),
        'candidate_source_sha256': digest(ell_point.__file__),
    }, indent=2) + '\n')
    rows = []
    for phase in ('primary', 'confirmation'):
        for index, spec in enumerate(intent[phase + '_cases']):
            case = dict(spec, phase=phase,
                        seed=intent['seed_base_' + phase] + index)
            path = out / f'cell-{len(rows):02d}.json'
            cmd = [sys.executable, str(Path(__file__).resolve()), '--case',
                   json.dumps(case), '--worker-out', str(path)]
            with (out / f'cell-{len(rows):02d}.log').open('w') as log:
                try:
                    proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=300)
                    status = proc.returncode
                except subprocess.TimeoutExpired:
                    status = 'timeout'
            (out / f'cell-{len(rows):02d}-parent.json').write_text(json.dumps({
                'case': case, 'status': status,
            }, indent=2) + '\n')
            if status != 0:
                raise SystemExit(f'cell failed: {case}: {status}')
            row = json.loads(path.read_text())
            rows.append(row)
            print(phase, case['field'], case.get('degree', case.get('p')),
                  f"{row['speedup']:.3f}x", flush=True)
    (out / 'summary.json').write_text(json.dumps({
        'cells': [{'case': row['case'], 'speedup': row['speedup']} for row in rows],
        'all_exact': all(row['exact_outputs'] for row in rows),
        'verified_outputs': sum(row['verified_outputs'] for row in rows),
    }, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    parser.add_argument('--case')
    parser.add_argument('--worker-out', type=Path)
    args = parser.parse_args()
    if args.case:
        worker(json.loads(args.case), args.worker_out)
    else:
        parent(args.out)
