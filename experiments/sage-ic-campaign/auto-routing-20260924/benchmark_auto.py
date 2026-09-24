"""Paired cold and warm direct-Sage versus conservative auto calls."""
import argparse
import hashlib
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
from sage.schemes.elliptic_curves import binary_hardware

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    route = (case['degree'] in (67, 131) and case['power'] % case['degree'] == 65
             and case['points'] >= 4096)
    orders = [('sage', 'auto'), ('auto', 'sage')] * 6
    random.Random(case['seed']).shuffle(orders)
    trials = []
    for order in orders:
        result = {}
        for arm in order:
            start = time.perf_counter_ns()
            plan = binary_hardware.FrobeniusPlan(curve, case['power'],
                                                 backend=arm, cpu_threads=1)
            constructed = time.perf_counter_ns()
            actual = plan.apply(points)
            assert actual == expected
            del actual
            first = time.perf_counter_ns()
            chosen = plan.last_backend
            assert chosen == ('cpu' if route and arm == 'auto' else 'sage')
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
                'selected_backend': chosen,
                'setup_seconds': (constructed - start) / 1e9,
                'first_seconds': (first - constructed) / 1e9,
                'warm_seconds': statistics.median(warm_samples),
                'close_seconds': (closed - warm) / 1e9,
                'cold_total_seconds': (first - start + closed - warm) / 1e9,
            }
        trials.append({'order': order, 'arms': result})
    ratios = {}
    for metric in ('cold_total_seconds', 'warm_seconds'):
        logs = [math.log(trial['arms']['sage'][metric] / trial['arms']['auto'][metric])
                for trial in trials]
        ratios[metric] = math.exp(statistics.median(logs))
    row = {'case': case, 'route_expected': route, 'trials': trials,
           'speedup_auto_vs_sage': ratios, 'exact_output_agreement': True,
           'verified_outputs': case['points'] * 12 * 2 * 5,
           'fixture_attempts': attempts,
           'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'candidate_source_sha256': digest(binary_hardware.__file__)}
    out.write_text(json.dumps(row, indent=2) + '\n')
    print(case['degree'], case['points'], case['power'], 'route', route,
          f"cold {ratios['cold_total_seconds']:.3f}x",
          f"warm {ratios['warm_seconds']:.3f}x", flush=True)


def parent(out):
    intent = json.loads((HERE / 'intent-candidate-v1.json').read_text())
    install = json.loads((HERE / 'install-001/install.json').read_text())
    assert digest(binary_hardware.__file__) == install['installed_sha256']
    assert digest(ROOT / 'third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_hardware.py') == install['source_sha256']
    out.mkdir(parents=True, exist_ok=False)
    (out / 'execution.json').write_text(json.dumps({
        'intent_sha256': digest(HERE / 'intent-candidate-v1.json'),
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
                  'route', row['route_expected'],
                  f"cold {row['speedup_auto_vs_sage']['cold_total_seconds']:.3f}x",
                  f"warm {row['speedup_auto_vs_sage']['warm_seconds']:.3f}x", flush=True)
    (out / 'summary.json').write_text(json.dumps({
        'cells': [{'case': row['case'], 'route_expected': row['route_expected'],
                   'speedup_auto_vs_sage': row['speedup_auto_vs_sage']} for row in rows],
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
