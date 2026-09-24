"""Paired cold and warm complete Sage-point calls for auto routing."""
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
from sage.schemes.elliptic_curves import binary_hardware, binary_hardware_codec

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def worker(case, out):
    field = GF(2**case['degree'], 'z', impl='ntl')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    base, attempts = generate(curve, min(case['points'], 128), case['seed'])
    points = [base[i % len(base)] for i in range(case['points'])]
    points[0], points[1] = curve(0), curve(0, 1)
    phi = curve.frobenius_isogeny(case['power'] % case['degree'])
    expected = [phi(point) for point in points]
    orders = [('sage', 'cpu'), ('cpu', 'sage')] * 6
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
            actual = plan.apply(points)
            assert actual == expected
            del actual
            warm = time.perf_counter_ns()
            plan.close()
            closed = time.perf_counter_ns()
            result[arm] = {
                'setup_seconds': (constructed - start) / 1e9,
                'first_seconds': (first - constructed) / 1e9,
                'warm_seconds': (warm - first) / 1e9,
                'close_seconds': (closed - warm) / 1e9,
                'cold_total_seconds': (first - start + closed - warm) / 1e9,
            }
        trials.append({'order': order, 'arms': result})
    ratios = {}
    for metric in ('cold_total_seconds', 'warm_seconds'):
        logs = [math.log(trial['arms']['sage'][metric] / trial['arms']['cpu'][metric])
                for trial in trials]
        ratios[metric] = math.exp(statistics.median(logs))
    row = {'case': case, 'trials': trials, 'speedup_cpu_vs_sage': ratios,
           'exact_output_agreement': True, 'verified_outputs': case['points'] * 48,
           'fixture_attempts': attempts,
           'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'hardware_source_sha256': digest(ROOT / 'third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_hardware.py'),
           'codec_source_sha256': digest(ROOT / 'third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_hardware_codec.pyx'),
           'codec_binary_sha256': digest(binary_hardware_codec.__file__)}
    out.write_text(json.dumps(row, indent=2) + '\n')
    print(case['degree'], case['points'], case['power'],
          f"cold {ratios['cold_total_seconds']:.3f}x",
          f"warm {ratios['warm_seconds']:.3f}x", flush=True)


def parent(out):
    intent = json.loads((HERE / 'intent-exploratory-v1.json').read_text())
    assert digest(ROOT / 'third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_hardware.py') == intent['incumbent_hardware_source_sha256']
    assert digest(ROOT / 'third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_hardware_codec.pyx') == intent['codec_source_sha256']
    assert digest(binary_hardware_codec.__file__) == intent['codec_binary_sha256']
    out.mkdir(parents=True, exist_ok=False)
    (out / 'execution.json').write_text(json.dumps({
        'intent_sha256': digest(HERE / 'intent-exploratory-v1.json'),
        'benchmark_sha256': digest(__file__),
    }, indent=2) + '\n')
    rows = []
    for index, spec in enumerate(intent['cases']):
        case = dict(spec, seed=intent['seed_base'] + index)
        path = out / f'cell-{index:02d}.json'
        cmd = [sys.executable, str(Path(__file__).resolve()), '--case',
               json.dumps(case), '--worker-out', str(path)]
        with (out / f'cell-{index:02d}.log').open('w') as log:
            try:
                result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=300)
                status = result.returncode
            except subprocess.TimeoutExpired:
                status = 'timeout'
        (out / f'cell-{index:02d}-parent.json').write_text(json.dumps({
            'case': case, 'status': status,
        }, indent=2) + '\n')
        if status != 0:
            raise SystemExit(f'cell failed: {case}: {status}')
        row = json.loads(path.read_text())
        rows.append(row)
        print(case['degree'], case['points'], case['power'],
              f"cold {row['speedup_cpu_vs_sage']['cold_total_seconds']:.3f}x",
              f"warm {row['speedup_cpu_vs_sage']['warm_seconds']:.3f}x", flush=True)
    (out / 'summary.json').write_text(json.dumps({
        'cells': [{'case': row['case'], 'speedup_cpu_vs_sage': row['speedup_cpu_vs_sage']}
                  for row in rows],
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
