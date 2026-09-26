"""Exact full-call pilot of one-thread-per-element Metal mapping."""

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
ELEMENT = Path('/private/tmp/codex-metal-element-kernel/libelement.dylib')
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))


def module(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--points', type=int, required=True)
    parser.add_argument('--groups', type=int, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--rounds', type=int, default=8)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.points % args.groups == 0
    from sage.all import EllipticCurve, GF, set_random_seed
    from sage.schemes.elliptic_curves.binary_batch import frobenius_points
    from public_points import generate

    baseline = module('metal_word_kernel', HERE / 'baseline/binary_hardware.py')
    candidate = module('metal_element_kernel', HERE / 'source/binary_hardware.py')
    set_random_seed(args.seed)
    field = GF(2**131, 'z')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    points, attempts = generate(curve, args.points, args.seed)
    points[:3] = [curve(0), curve(0, 1), points[3]]
    width = args.points // args.groups
    groups = [points[i:i + width] for i in range(0, len(points), width)]
    expected = frobenius_points(curve, points, 65)
    expected_groups = [expected[i:i + width] for i in range(0, len(expected), width)]

    plans = {}
    setup_ns = {}
    for name, klass, backend, native in (
        ('metal_word', baseline.FrobeniusPlan, 'metal', NATIVE),
        ('metal_element', candidate.FrobeniusPlan, 'metal', ELEMENT),
        ('cpu_batched', baseline.FrobeniusPlan, 'cpu', NATIVE),
    ):
        start = time.perf_counter_ns()
        plans[name] = klass(curve, 65, backend, native_library=native)
        setup_ns[name] = time.perf_counter_ns() - start
    assert len({plan._table.tobytes() for plan in plans.values()}) == 1
    samples = {name: [] for name in (*plans, 'sage_flat')}
    arms = tuple(samples)
    for round_number in range(args.rounds):
        order = arms[round_number % len(arms):] + arms[:round_number % len(arms)]
        if (round_number // len(arms)) % 2:
            order = order[::-1]
        for name in order:
            start = time.perf_counter_ns()
            if name == 'sage_flat':
                result = frobenius_points(curve, points, 65)
                actual = [result[i:i + width] for i in range(0, len(result), width)]
            else:
                actual = plans[name].apply_batches(groups)
            computed = time.perf_counter_ns()
            assert actual == expected_groups
            checked = time.perf_counter_ns()
            del actual
            finished = time.perf_counter_ns()
            samples[name].append({
                'round': round_number,
                'operation_ns': computed - start,
                'verification_ns': checked - computed,
                'cleanup_ns': finished - checked,
                'validated_ns': finished - start,
                'device_seconds': plans[name].last_gpu_seconds if name != 'sage_flat' else None,
            })
    for plan in plans.values():
        plan.close()
    args.out.write_text(json.dumps({
        'case': vars(args) | {'out': str(args.out)},
        'attempts': attempts,
        'exact_output_agreement': True,
        'source_sha256': {
            'baseline': digest(HERE / 'baseline/binary_hardware.py'),
            'candidate': digest(HERE / 'source/binary_hardware.py'),
            'bridge': digest(HERE / 'source/binary_hardware_metal.mm'),
            'native': digest(NATIVE), 'element': digest(ELEMENT),
        },
        'setup_ns': setup_ns,
        'samples': samples,
        'median_operation_ns': {
            arm: statistics.median(row['operation_ns'] for row in rows)
            for arm, rows in samples.items()},
        'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
