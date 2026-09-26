"""Paired cold complete-call benchmark for vectorized table construction."""
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

import numpy as np
from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_hardware

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def incumbent_module():
    spec = importlib.util.spec_from_file_location('old_binary_hardware',
                                                   HERE / 'baseline-pr75/binary_hardware.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker(case, out):
    field = GF(2**case['degree'], 'z', impl='ntl')
    if case.get('alternate_modulus'):
        field = GF(2**case['degree'], 'w',
                   modulus=field.modulus().reverse(), impl='ntl')
    curve = EllipticCurve(field, [1, case['a'], 0, 0, 1])
    base, attempts = generate(curve, min(case['points'], 128), case['seed'])
    points = [base[i % len(base)] for i in range(case['points'])]
    points[0], points[1] = curve(0), curve(0, 1)
    phi = curve.frobenius_isogeny(case['power'] % case['degree'])
    expected = [phi(point) for point in points]
    old = incumbent_module()
    native = binary_hardware._library()._name
    modules = {'incumbent': old, 'candidate': binary_hardware}
    with old.FrobeniusPlan(curve, case['power'], backend='metal',
                           native_library=native) as original:
        with binary_hardware.FrobeniusPlan(curve, case['power'], backend='metal',
                                           native_library=native) as improved:
            assert np.array_equal(original._table, improved._table)
    orders = [('incumbent', 'candidate'), ('candidate', 'incumbent')] * 6
    random.Random(case['seed']).shuffle(orders)
    trials = []
    for order in orders:
        result = {}
        for arm in order:
            start = time.perf_counter_ns()
            plan = modules[arm].FrobeniusPlan(
                curve, case['power'], backend='metal', native_library=native)
            built = time.perf_counter_ns()
            actual = plan.apply(points)
            assert actual == expected
            del actual
            first = time.perf_counter_ns()
            warm_samples = []
            for _ in range(4):
                before = time.perf_counter_ns()
                actual = plan.apply(points)
                assert actual == expected
                del actual
                warm_samples.append((time.perf_counter_ns() - before) / 1e9)
            warm = time.perf_counter_ns()
            plan.close()
            closed = time.perf_counter_ns()
            result[arm] = {
                'setup_seconds': (built - start) / 1e9,
                'table_seconds': plan.table_seconds,
                'first_seconds': (first - built) / 1e9,
                'warm_seconds': statistics.median(warm_samples),
                'close_seconds': (closed - warm) / 1e9,
                'cold_total_seconds': (first - start + closed - warm) / 1e9,
            }
        trials.append({'order': order, 'arms': result})
    ratios = {}
    for metric in ('table_seconds', 'cold_total_seconds', 'warm_seconds'):
        logs = [math.log(t['arms']['incumbent'][metric] / t['arms']['candidate'][metric])
                for t in trials]
        ratios[metric] = math.exp(statistics.median(logs))
    row = {'case': case, 'trials': trials, 'speedup': ratios,
           'exact_table_agreement': True, 'exact_output_agreement': True,
           'verified_outputs': case['points'] * 12 * 2 * 5,
           'fixture_attempts': attempts,
           'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'incumbent_source_sha256': digest(HERE / 'baseline-pr75/binary_hardware.py'),
           'candidate_source_sha256': digest(binary_hardware.__file__)}
    out.write_text(json.dumps(row, indent=2) + '\n')
    print(case['degree'], case['points'], case['power'],
          f"table {ratios['table_seconds']:.3f}x",
          f"cold {ratios['cold_total_seconds']:.3f}x", flush=True)


def parent(out):
    intent = json.loads((HERE / 'intent-metal-independent-v1.json').read_text())
    install = json.loads((HERE / 'install-independent-001/install.json').read_text())
    assert digest(HERE / 'baseline-pr75/binary_hardware.py') == intent['incumbent_source_sha256']
    assert digest(binary_hardware.__file__) == install['installed_sha256']
    out.mkdir(parents=True, exist_ok=False)
    (out / 'execution.json').write_text(json.dumps({
        'intent_sha256': digest(HERE / 'intent-metal-independent-v1.json'),
        'benchmark_sha256': digest(__file__),
        'candidate_source_sha256': digest(binary_hardware.__file__),
    }, indent=2) + '\n')
    rows = []
    for phase in ('primary', 'confirmation'):
        for index, spec in enumerate(intent[phase + '_cases']):
            case = dict(spec, phase=phase,
                        seed=(intent['seed_base_primary'] if phase == 'primary'
                              else intent['seed_base_confirmation']) + index)
            path = out / f'cell-{len(rows):02d}.json'
            cmd = [sys.executable, str(Path(__file__).resolve()), '--case',
                   json.dumps(case), '--worker-out', str(path)]
            with (out / f'cell-{len(rows):02d}.log').open('w') as log:
                try:
                    result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                                            timeout=300)
                    status = result.returncode
                except subprocess.TimeoutExpired:
                    status = 'timeout'
            (out / f'cell-{len(rows):02d}-parent.json').write_text(json.dumps({
                'case': case, 'status': status,
            }, indent=2) + '\n')
            if status != 0:
                raise SystemExit(f'cell failed: {case}: {status}')
            row = json.loads(path.read_text())
            rows.append(row)
            print(phase, case['degree'], case['points'], case['power'],
                  f"table {row['speedup']['table_seconds']:.3f}x",
                  f"cold {row['speedup']['cold_total_seconds']:.3f}x", flush=True)
    (out / 'summary.json').write_text(json.dumps({
        'cells': [{'case': row['case'], 'speedup': row['speedup']}
                  for row in rows],
        'all_tables_exact': all(row['exact_table_agreement'] for row in rows),
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
