"""Compare full Sage point-map calls with separately dispatched batches."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import statistics
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SAGE_ROOT = Path('/Volumes/SSD990/cryptanalysis/third_party/sage-binary')
NATIVE = (SAGE_ROOT / 'local/var/lib/sage/venv-python3.14/lib/python3.14/'
          'site-packages/sage/schemes/elliptic_curves/_binary_hardware_native.dylib')
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--points', type=int, required=True)
    parser.add_argument('--groups', type=int, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--rounds', type=int, default=12)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.points > 0 and 1 < args.groups <= args.points
    assert args.points % args.groups == 0

    from sage.all import EllipticCurve, GF, set_random_seed
    from sage.schemes.elliptic_curves.binary_batch import frobenius_points
    from sage.schemes.elliptic_curves.binary_hardware import FrobeniusPlan as Baseline
    from public_points import generate

    spec = importlib.util.spec_from_file_location(
        'sage_binary_hardware_batched', HERE / 'source/binary_hardware.py')
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    set_random_seed(args.seed)
    field = GF(2**131, 'z')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    points, attempts = generate(curve, args.points, args.seed)
    points[0] = curve(0)
    points[1] = curve(0, 1)
    points[2] = points[3]
    width = args.points // args.groups
    groups = [points[i:i + width] for i in range(0, len(points), width)]
    expected = frobenius_points(curve, points, 65)

    plans = {}
    setup_ns = {}
    for arm, klass, backend in (
        ('metal_separate', Baseline, 'metal'),
        ('metal_batched', candidate.FrobeniusPlan, 'metal'),
        ('cpu_separate', Baseline, 'cpu'),
        ('cpu_batched', candidate.FrobeniusPlan, 'cpu'),
    ):
        start = time.perf_counter_ns()
        plans[arm] = klass(curve, 65, backend, native_library=NATIVE)
        setup_ns[arm] = time.perf_counter_ns() - start
    assert len({plan._table.tobytes() for plan in plans.values()}) == 1

    samples = {arm: [] for arm in plans}
    arms = tuple(plans)
    for round_number in range(args.rounds):
        order = arms[round_number % len(arms):] + arms[:round_number % len(arms)]
        if (round_number // len(arms)) % 2:
            order = order[::-1]
        for arm in order:
            plan = plans[arm]
            start = time.perf_counter_ns()
            if arm.endswith('batched'):
                actual_groups = plan.apply_batches(iter(iter(g) for g in groups))
            else:
                actual_groups = [plan.apply(g) for g in groups]
            computed = time.perf_counter_ns()
            assert actual_groups == [expected[i:i + width]
                                     for i in range(0, len(expected), width)]
            checked = time.perf_counter_ns()
            del actual_groups
            finished = time.perf_counter_ns()
            samples[arm].append({
                'round': round_number,
                'operation_ns': computed - start,
                'verification_ns': checked - computed,
                'cleanup_ns': finished - checked,
                'validated_ns': finished - start,
                'last_gpu_seconds': plan.last_gpu_seconds,
            })
    for plan in plans.values():
        plan.close()
    packed, flags = plans['cpu_batched'].pack_points(points)
    args.out.write_text(json.dumps({
        'case': vars(args) | {'out': str(args.out)},
        'attempts': attempts,
        'exact_output_agreement': True,
        'source_sha256': {
            'baseline': digest(HERE / 'baseline/binary_hardware.py'),
            'candidate': digest(HERE / 'source/binary_hardware.py'),
            'native': digest(NATIVE),
        },
        'input_sha256': hashlib.sha256(packed.tobytes() + flags.tobytes()).hexdigest(),
        'setup_ns': setup_ns,
        'samples': samples,
        'median_operation_ns': {
            arm: statistics.median(row['operation_ns'] for row in rows)
            for arm, rows in samples.items()},
        'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
