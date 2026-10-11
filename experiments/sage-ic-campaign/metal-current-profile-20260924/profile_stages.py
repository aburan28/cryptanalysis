"""Measure complete installed Sage point calls by host and Metal stage."""

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time


root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'experiments/sage-binary-hardware'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--degree', type=int, required=True)
    parser.add_argument('--points', type=int, required=True)
    parser.add_argument('--power', type=int, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()

    from sage.all import GF, EllipticCurve, set_random_seed
    from sage.schemes.elliptic_curves.binary_batch import frobenius_points
    from load_hardware import FrobeniusPlan, SOURCE, artifacts
    from public_points import generate

    set_random_seed(args.seed)
    field = GF(2**args.degree, 'z')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    points, attempts = generate(curve, args.points, args.seed)
    if len(points) >= 4:
        points[0] = curve(0)
        points[1] = curve(0, 1)
        points[2] = points[3]
    expected = frobenius_points(curve, points, args.power)
    plans = {}
    setup = {}
    for backend in ('cpu', 'metal'):
        started = time.perf_counter_ns()
        plans[backend] = FrobeniusPlan(curve, args.power, backend, cpu_threads=1)
        setup[backend] = time.perf_counter_ns() - started

    samples = {'cpu': [], 'metal': []}
    for round_number in range(12):
        order = ('cpu', 'metal') if round_number % 2 == 0 else ('metal', 'cpu')
        for backend in order:
            plan = plans[backend]
            t0 = time.perf_counter_ns()
            packed, flags = plan.pack_points(points)
            t1 = time.perf_counter_ns()
            mapped = plan.apply_words(packed)
            t2 = time.perf_counter_ns()
            output = plan._unpack_points(mapped, flags)
            t3 = time.perf_counter_ns()
            assert output == expected
            t4 = time.perf_counter_ns()
            del packed, flags, mapped, output
            t5 = time.perf_counter_ns()
            samples[backend].append({
                'round': round_number,
                'pack_ns': t1 - t0,
                'map_ns': t2 - t1,
                'unpack_ns': t3 - t2,
                'verify_ns': t4 - t3,
                'cleanup_ns': t5 - t4,
                'complete_ns': t5 - t0,
                'device_seconds': plan.last_gpu_seconds,
            })
    for plan in plans.values():
        plan.close()
    args.out.write_text(json.dumps({
        'degree': args.degree, 'points': args.points,
        'power': args.power, 'seed': args.seed,
        'generation_attempts': attempts,
        'exact_output_agreement': True,
        'setup_ns': setup,
        'samples': samples,
        'loaded_artifacts': artifacts(),
        'source_sha256': digest(SOURCE),
        'peak_rss': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
