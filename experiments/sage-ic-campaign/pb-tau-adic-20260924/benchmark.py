"""Paired warm and first-call polynomial-basis Frobenius scalar timings."""

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
    parser.add_argument('--bits', type=int, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--rounds', type=int, default=12)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source_dir = ROOT / 'ecc2k130' / ('codegen' if args.variant == 'local'
                                      else 'runner/codegen')
    sys.path.insert(0, str(source_dir))
    import field
    old = load('curve_old_' + args.variant,
               HERE / ('baseline/curves-' + args.variant + '.py'))
    new = load('curve_new_' + args.variant,
               HERE / ('source/curves-' + args.variant + '.py'))
    poly, _ = old.findIrreduciblePoly(args.degree)
    fixture = old.CurvePb(field.Pb(args.degree, poly))
    rng = random.Random(args.seed)
    point = None
    attempts = 0
    while point is None:
        attempts += 1
        assert attempts <= 128
        point = fixture.pointFromX(rng.randrange(1, 1 << args.degree))
    scalar = (1 << (args.bits - 1)) | rng.getrandbits(args.bits - 1)
    assert scalar.bit_length() == args.bits
    old_field, new_field = field.Pb(args.degree, poly), field.Pb(args.degree, poly)
    baseline, candidate = old.CurvePb(old_field), new.CurvePb(new_field)
    started = time.perf_counter_ns()
    expected = baseline.mul(point, scalar)
    baseline_first_ns = time.perf_counter_ns() - started
    started = time.perf_counter_ns()
    first_candidate = candidate.mul(point, scalar)
    candidate_first_ns = time.perf_counter_ns() - started
    assert first_candidate == expected

    samples = {'baseline': [], 'candidate': []}
    for round_number in range(args.rounds):
        order = ('baseline', 'candidate') if round_number % 2 == 0 else \
            ('candidate', 'baseline')
        for arm in order:
            curve = baseline if arm == 'baseline' else candidate
            started = time.perf_counter_ns()
            actual = curve.mul(point, scalar)
            computed = time.perf_counter_ns()
            assert actual == expected and curve.onCurve(actual)
            verified = time.perf_counter_ns()
            del actual
            finished = time.perf_counter_ns()
            samples[arm].append({
                'round': round_number,
                'operation_ns': computed - started,
                'verification_ns': verified - computed,
                'cleanup_ns': finished - verified,
                'validated_ns': finished - started,
            })
    args.out.write_text(json.dumps({
        'case': vars(args) | {'out': str(args.out)},
        'point_attempts': attempts,
        'scalar_hex': hex(scalar),
        'first_call_ns': {'baseline': baseline_first_ns,
                          'candidate': candidate_first_ns},
        'exact_output_agreement': True,
        'source_sha256': {
            'baseline': digest(HERE / ('baseline/curves-' + args.variant + '.py')),
            'candidate': digest(HERE / ('source/curves-' + args.variant + '.py')),
            'field': digest(source_dir / 'field.py'),
        },
        'samples': samples,
        'median_operation_ns': {
            arm: statistics.median(sample['operation_ns'] for sample in rows)
            for arm, rows in samples.items()},
        'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
