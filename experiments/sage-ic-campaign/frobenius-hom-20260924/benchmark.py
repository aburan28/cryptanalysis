"""Paired public phi(P) benchmark for the installed native-squaring guard."""
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

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import hom_frobenius

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def original_method():
    spec = importlib.util.spec_from_file_location(
        'old_hom_frobenius', HERE / 'baseline/hom_frobenius.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.EllipticCurveHom_frobenius._call_


def worker(case, out):
    field = GF(2**case['degree'], 'z', impl='ntl')
    if case.get('alternate_modulus'):
        field = GF(2**case['degree'], 'w',
                   modulus=field.modulus().reverse(), impl='ntl')
    curve = EllipticCurve(field, [1, case['a'], 0, 0, 1])
    base, attempts = generate(curve, min(case['points'], 128), case['seed'])
    points = [base[i % len(base)] for i in range(case['points'])]
    points[0], points[1] = curve(0), curve(0, 1)
    cls = hom_frobenius.EllipticCurveHom_frobenius
    candidate = cls._call_
    original = original_method()
    cls._call_ = original
    try:
        reference = cls(curve, case['power'])
        assert reference.codomain() is curve
        expected = [reference(point) for point in points]
        methods = {'incumbent': original, 'candidate': candidate}
        order_pairs = [('incumbent', 'candidate'),
                       ('candidate', 'incumbent')] * 8
        random.Random(case['seed']).shuffle(order_pairs)
        trials = []
        for order in order_pairs:
            result = {}
            for arm in order:
                cls._call_ = methods[arm]
                start = time.perf_counter_ns()
                phi = cls(curve, case['power'])
                built = time.perf_counter_ns()
                first = [phi(point) for point in points]
                assert first == expected
                first_done = time.perf_counter_ns()
                warm = [phi(point) for point in points]
                assert warm == expected
                warm_done = time.perf_counter_ns()
                result[arm] = {
                    'construct_seconds': (built-start)/1e9,
                    'first_seconds': (first_done-built)/1e9,
                    'warm_seconds': (warm_done-first_done)/1e9,
                    'cold_total_seconds': (first_done-start)/1e9,
                }
            trials.append({'order': order, 'arms': result})
    finally:
        cls._call_ = candidate
    speedup = {}
    for metric in ('warm_seconds', 'cold_total_seconds'):
        speedup[metric] = math.exp(statistics.median([
            math.log(t['arms']['incumbent'][metric] /
                     t['arms']['candidate'][metric]) for t in trials]))
    row = {'case': case, 'trials': trials, 'speedup': speedup,
           'exact_output_agreement': True,
           'verified_outputs': case['points'] * (1 + 16*2*2),
           'fixture_attempts': attempts,
           'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'incumbent_source_sha256': digest(HERE / 'baseline/hom_frobenius.py'),
           'candidate_source_sha256': digest(hom_frobenius.__file__)}
    out.write_text(json.dumps(row, indent=2) + '\n')
    print(case['degree'], case['power'], case['points'],
          f"warm {speedup['warm_seconds']:.3f}x",
          f"cold {speedup['cold_total_seconds']:.3f}x", flush=True)


def parent(out):
    intent = json.loads((HERE / 'intent-candidate-v1.json').read_text())
    install = json.loads((HERE / 'install-001/install.json').read_text())
    assert digest(HERE / 'baseline/hom_frobenius.py') == intent['incumbent_source_sha256']
    assert digest(hom_frobenius.__file__) == install['installed_sha256'] == intent['candidate_source_sha256']
    out.mkdir(parents=True, exist_ok=False)
    (out / 'execution.json').write_text(json.dumps({
        'intent_sha256': digest(HERE / 'intent-candidate-v1.json'),
        'benchmark_sha256': digest(__file__),
        'candidate_source_sha256': digest(hom_frobenius.__file__),
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
            print(phase, case['degree'], case['power'],
                  f"warm {row['speedup']['warm_seconds']:.3f}x",
                  f"cold {row['speedup']['cold_total_seconds']:.3f}x", flush=True)
    (out / 'summary.json').write_text(json.dumps({
        'cells': [{'case': row['case'], 'speedup': row['speedup']} for row in rows],
        'all_outputs_exact': all(row['exact_output_agreement'] for row in rows),
        'total_verified_outputs': sum(row['verified_outputs'] for row in rows),
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
