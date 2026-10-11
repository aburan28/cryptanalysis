"""Exclusive phase profile of complete, exactly checked hardware plan calls."""
import argparse
import hashlib
import json
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


def worker(case, backend, out):
    field = GF(2**case['degree'], 'z', impl='ntl')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    base, attempts = generate(curve, min(case['points'], 128), case['seed'])
    points = [base[i % len(base)] for i in range(case['points'])]
    points[0], points[1] = curve(0), curve(0, 1)
    phi = curve.frobenius_isogeny(case['power'] % case['degree'])
    expected = [phi(point) for point in points]
    start = time.perf_counter_ns()
    plan = binary_hardware.FrobeniusPlan(curve, case['power'], backend=backend,
                                         cpu_threads=1)
    setup = (time.perf_counter_ns() - start) / 1e9
    assert plan.codec == 'native-ntl'
    phase = {name: [] for name in ('pack', 'table', 'unpack', 'check', 'cleanup')}
    gpu_seconds = []
    rounds = []
    for _ in range(12):
        for _ in range(4):
            start = time.perf_counter_ns()
            data, flags = plan.pack_points(points)
            packed = time.perf_counter_ns()
            mapped = plan.apply_words(data)
            table = time.perf_counter_ns()
            gpu_seconds.append(plan.last_gpu_seconds)
            actual = plan._unpack_points(mapped, flags)
            unpacked = time.perf_counter_ns()
            assert actual == expected
            checked = time.perf_counter_ns()
            del actual, data, flags, mapped
            cleaned = time.perf_counter_ns()
            for name, left, right in (
                ('pack', start, packed), ('table', packed, table),
                ('unpack', table, unpacked), ('check', unpacked, checked),
                ('cleanup', checked, cleaned),
            ):
                phase[name].append((right - left) / 1e9)
        rounds.append({name: statistics.median(samples[-4:]) for name, samples in phase.items()})
    plan.close()
    medians = {name: statistics.median(samples) for name, samples in phase.items()}
    row = {'case': case, 'backend': backend, 'setup_seconds': setup,
           'fixture_attempts': attempts, 'phase_seconds': phase,
           'rounds': rounds, 'median_phase_seconds': medians,
           'total_median_seconds': sum(medians.values()),
           'pack_fraction': medians['pack'] / sum(medians.values()),
           'gpu_seconds': gpu_seconds,
           'median_gpu_seconds': statistics.median(gpu_seconds),
           'exact_output_agreement': True,
           'verified_outputs': case['points'] * 48,
           'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'source_sha256': digest(ROOT / 'third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_hardware_codec.pyx'),
           'binary_sha256': digest(binary_hardware_codec.__file__)}
    out.write_text(json.dumps(row, indent=2) + '\n')
    print(case['degree'], case['points'], case['power'], backend,
          f"pack {100*row['pack_fraction']:.1f}%", flush=True)


def parent(out):
    intent = json.loads((HERE / 'intent-v1.json').read_text())
    assert digest(ROOT / 'third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_hardware_codec.pyx') == intent['incumbent_source_sha256']
    assert digest(binary_hardware_codec.__file__) == intent['incumbent_binary_sha256']
    out.mkdir(parents=True, exist_ok=False)
    (out / 'execution.json').write_text(json.dumps({
        'intent_sha256': digest(HERE / 'intent-v1.json'),
        'profile_sha256': digest(__file__),
    }, indent=2) + '\n')
    rows = []
    for index, spec in enumerate(intent['cases']):
        for backend in intent['backends']:
            case = dict(spec, seed=intent['seed_base'] + index)
            path = out / f'cell-{len(rows):02d}.json'
            cmd = [sys.executable, str(Path(__file__).resolve()), '--case',
                   json.dumps(case), '--backend', backend, '--worker-out', str(path)]
            with (out / f'cell-{len(rows):02d}.log').open('w') as log:
                try:
                    result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                                            timeout=300)
                    status = result.returncode
                except subprocess.TimeoutExpired:
                    status = 'timeout'
            (out / f'cell-{len(rows):02d}-parent.json').write_text(json.dumps({
                'case': case, 'backend': backend, 'status': status,
            }, indent=2) + '\n')
            if status != 0:
                raise SystemExit(f'cell failed: {case} {backend}: {status}')
            row = json.loads(path.read_text())
            rows.append(row)
            print(case['degree'], case['points'], case['power'], backend,
                  f"pack {100*row['pack_fraction']:.1f}%",
                  f"Metal API {1000*row['median_phase_seconds']['table']:.3f} ms",
                  f"GPU command {1000*row['median_gpu_seconds']:.3f} ms", flush=True)
    (out / 'summary.json').write_text(json.dumps({
        'cells': [{'case': row['case'], 'backend': row['backend'],
                   'pack_fraction': row['pack_fraction'],
                   'median_gpu_seconds': row['median_gpu_seconds'],
                   'median_phase_seconds': row['median_phase_seconds']}
                  for row in rows],
        'all_outputs_exact': all(row['exact_output_agreement'] for row in rows),
        'total_verified_outputs': sum(row['verified_outputs'] for row in rows),
    }, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    parser.add_argument('--case')
    parser.add_argument('--backend', choices=('cpu', 'metal'))
    parser.add_argument('--worker-out', type=Path)
    args = parser.parse_args()
    if args.case:
        worker(json.loads(args.case), args.backend, args.worker_out)
    else:
        parent(args.out)
