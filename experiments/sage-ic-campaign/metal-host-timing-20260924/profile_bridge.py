"""Compare installed Metal bridge with an exact instrumented standalone copy."""

import argparse
import ctypes
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
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()

    from sage.all import GF, EllipticCurve, set_random_seed
    from sage.schemes.elliptic_curves.binary_batch import frobenius_points
    from sage.schemes.elliptic_curves.binary_hardware import FrobeniusPlan
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
    setup = {}
    plans = {}
    for name, path in (('installed', None), ('instrumented', args.native)):
        start = time.perf_counter_ns()
        plans[name] = FrobeniusPlan(curve, args.power, 'metal',
                                   native_library=path)
        setup[name] = time.perf_counter_ns() - start
    assert plans['installed']._table.tobytes() == plans['instrumented']._table.tobytes()

    library = plans['instrumented']._lib
    library.bh_metal_last_times.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_double),
                                           ctypes.c_uint32]
    library.bh_metal_last_times.restype = ctypes.c_int
    samples = {'installed': [], 'instrumented': []}
    phase_names = ('allocation', 'input_copy', 'command_encode',
                   'submit_wait', 'output_copy', 'bridge_total')
    for round_number in range(12):
        order = ('installed', 'instrumented') if round_number % 2 == 0 else \
            ('instrumented', 'installed')
        for name in order:
            plan = plans[name]
            start = time.perf_counter_ns()
            output = plan.apply(points)
            computed = time.perf_counter_ns()
            assert output == expected
            verified = time.perf_counter_ns()
            del output
            finished = time.perf_counter_ns()
            row = {'round': round_number, 'operation_ns': computed - start,
                   'verification_ns': verified - computed,
                   'cleanup_ns': finished - verified,
                   'validated_ns': finished - start,
                   'device_seconds': plan.last_gpu_seconds}
            if name == 'instrumented':
                timings = (ctypes.c_double * 6)()
                assert library.bh_metal_last_times(plan._context, timings, 6) == 0
                row['bridge_seconds'] = dict(zip(phase_names, timings))
            samples[name].append(row)
    for plan in plans.values():
        plan.close()
    args.out.write_text(json.dumps({
        'degree': args.degree, 'points': args.points,
        'power': args.power, 'seed': args.seed,
        'generation_attempts': attempts,
        'exact_output_agreement': True,
        'setup_ns': setup, 'samples': samples,
        'installed_native_sha256': digest(plans['installed']._lib._name),
        'instrumented_native_sha256': digest(args.native),
        'peak_rss': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
