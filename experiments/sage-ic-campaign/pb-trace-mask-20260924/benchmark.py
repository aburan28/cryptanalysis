"""Paired trace and complete point-recovery timings for polynomial basis."""

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
    field = load('field_' + args.variant, source_dir / 'field.py')
    old = load('curve_old_' + args.variant,
               HERE / ('baseline/curves-' + args.variant + '.py'))
    new = load('curve_new_' + args.variant,
               HERE / ('source/curves-' + args.variant + '.py'))
    poly, _ = old.findIrreduciblePoly(args.degree)
    rng = random.Random(args.seed)
    xs = [rng.randrange(1, 1 << args.degree) for _ in range(64)]
    values = [rng.randrange(1 << args.degree) for _ in range(256)]
    results = {}
    for operation, inputs in (('point_from_x', xs), ('field_trace', values)):
        old_curve = old.CurvePb(field.Pb(args.degree, poly))
        new_curve = new.CurvePb(field.Pb(args.degree, poly))
        method = 'pointFromX' if operation == 'point_from_x' else 'trace'
        old_fn = getattr(old_curve, method)
        new_fn = getattr(new_curve, method)
        started = time.perf_counter_ns()
        first_old = old_fn(inputs[0])
        old_first_ns = time.perf_counter_ns() - started
        started = time.perf_counter_ns()
        first_new = new_fn(inputs[0])
        new_first_ns = time.perf_counter_ns() - started
        assert first_old == first_new
        expected = [old_fn(value) for value in inputs]
        assert [new_fn(value) for value in inputs] == expected
        if operation == 'point_from_x':
            assert all(old_curve.onCurve(point) for point in expected)
            assert all(new_curve.onCurve(point) for point in expected)
        samples = {'baseline': [], 'candidate': []}
        for round_number in range(args.rounds):
            order = ('baseline', 'candidate') if round_number % 2 == 0 else \
                ('candidate', 'baseline')
            for arm in order:
                fn = old_fn if arm == 'baseline' else new_fn
                started = time.perf_counter_ns()
                output = [fn(value) for value in inputs]
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
            'first_call_ns': {'baseline': old_first_ns,
                              'candidate': new_first_ns},
            'trace_mask_hex': hex(new_curve._traceMask),
            'samples': samples,
            'median_operation_ns': {
                arm: statistics.median(sample['operation_ns'] for sample in rows)
                for arm, rows in samples.items()},
        }
    args.out.write_text(json.dumps({
        'case': vars(args) | {'out': str(args.out)},
        'exact_output_agreement': True,
        'source_sha256': {
            'baseline': digest(HERE / ('baseline/curves-' + args.variant + '.py')),
            'candidate': digest(HERE / ('source/curves-' + args.variant + '.py')),
            'field': digest(source_dir / 'field.py'),
        },
        'results': results,
        'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
