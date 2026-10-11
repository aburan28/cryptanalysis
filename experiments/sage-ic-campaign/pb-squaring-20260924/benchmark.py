"""Paired exact polynomial-basis square and containing scalar-call timings."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import resource
import statistics
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=('local', 'runner'), required=True)
    parser.add_argument('--degree', type=int, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--rounds', type=int, default=12)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source_dir = ROOT / 'ecc2k130' / ('codegen' if args.variant == 'local'
                                      else 'runner/codegen')
    sys.path.insert(0, str(source_dir))
    curves = load('curve_' + args.variant, source_dir / 'curves.py')
    old = load('field_old_' + args.variant,
               HERE / ('baseline/field-' + args.variant + '.py'))
    new = load('field_new_' + args.variant,
               HERE / ('source/field-' + args.variant + '.py'))
    poly, _ = curves.findIrreduciblePoly(args.degree)
    old_field, new_field = old.Pb(args.degree, poly), new.Pb(args.degree, poly)
    old_curve, new_curve = curves.CurvePb(old_field), curves.CurvePb(new_field)
    rng = random.Random(args.seed)
    values = [rng.randrange(1 << args.degree) for _ in range(256)]
    points = []
    attempts = 0
    while len(points) < 3:
        attempts += 1
        assert attempts <= 64
        point = old_curve.pointFromX(rng.randrange(1, 1 << args.degree))
        if point is not None:
            points.append(point)
    scalar = (1 << 31) | rng.getrandbits(31)
    operations = {
        'field_square': (
            lambda: [old_field.sqr(value) for value in values],
            lambda: [new_field.sqr(value) for value in values]),
        'point_scalar': (
            lambda: [old_curve.mul(point, scalar) for point in points],
            lambda: [new_curve.mul(point, scalar) for point in points]),
    }
    results = {}
    for operation, (old_fn, new_fn) in operations.items():
        started = time.perf_counter_ns()
        expected = old_fn()
        first_old = time.perf_counter_ns() - started
        started = time.perf_counter_ns()
        actual = new_fn()
        first_new = time.perf_counter_ns() - started
        assert actual == expected
        if operation == 'point_scalar':
            assert all(old_curve.onCurve(point) for point in expected)
            assert all(new_curve.onCurve(point) for point in actual)
        samples = {'baseline': [], 'candidate': []}
        for round_number in range(args.rounds):
            order = ('baseline', 'candidate') if round_number % 2 == 0 else \
                ('candidate', 'baseline')
            for arm in order:
                fn = old_fn if arm == 'baseline' else new_fn
                started = time.perf_counter_ns()
                output = fn()
                computed = time.perf_counter_ns()
                assert output == expected
                verified = time.perf_counter_ns()
                del output
                finished = time.perf_counter_ns()
                samples[arm].append({
                    'round': round_number,
                    'operation_ns': computed - started,
                    'verification_ns': verified - computed,
                    'cleanup_ns': finished - verified,
                    'validated_ns': finished - started,
                })
        results[operation] = {
            'first_call_ns': {'baseline': first_old, 'candidate': first_new},
            'samples': samples,
            'median_operation_ns': {
                arm: statistics.median(sample['operation_ns'] for sample in rows)
                for arm, rows in samples.items()},
        }
    args.out.write_text(json.dumps({
        'case': vars(args) | {'out': str(args.out)},
        'point_attempts': attempts,
        'scalar_hex': hex(scalar),
        'exact_output_agreement': True,
        'source_sha256': {
            'baseline': digest(HERE / ('baseline/field-' + args.variant + '.py')),
            'candidate': digest(HERE / ('source/field-' + args.variant + '.py')),
            'curves': digest(source_dir / 'curves.py'),
        },
        'results': results,
        'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
