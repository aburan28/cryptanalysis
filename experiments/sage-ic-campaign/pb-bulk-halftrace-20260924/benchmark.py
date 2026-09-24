"""Measure complete polynomial-basis IC factor-base collection."""

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


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--degree', type=int, required=True)
    parser.add_argument('--weight', type=int, required=True)
    parser.add_argument('--order', choices=('baseline-first', 'candidate-first'),
                        required=True)
    parser.add_argument('--rounds', type=int, default=6)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source_dir = ROOT / 'ecc2k130/runner/codegen'
    sys.path.insert(0, str(source_dir))
    field = load('field', source_dir / 'field.py')
    sys.modules['field'] = field
    old_curves = load('curves', HERE / 'baseline/curves-runner.py')
    sys.modules['curves'] = old_curves
    old_indexcalc = load('indexcalc_old', HERE / 'baseline/indexcalc.py')
    new_curves = load('curves_new', HERE / 'source/curves-runner.py')
    sys.modules['curves'] = new_curves
    new_indexcalc = load('indexcalc_new', HERE / 'source/indexcalc.py')
    onb = new_curves.NormalView(args.degree)
    baseline = old_curves.CurvePb(onb.pb)
    candidate = new_curves.CurvePb(onb.pb)
    def old_fn():
        return old_indexcalc.factorBase(onb, baseline, args.weight)
    def new_fn():
        return new_indexcalc.factorBase(onb, candidate, args.weight, True)

    started = time.perf_counter_ns()
    expected = old_fn()
    first_old = time.perf_counter_ns() - started
    started = time.perf_counter_ns()
    actual = new_fn()
    first_new = time.perf_counter_ns() - started
    assert actual == expected
    assert baseline._traceMask is not None
    assert getattr(baseline, '_halfTraceImages', None) is None
    assert candidate._halfTraceImages is not None
    samples = {'baseline': [], 'candidate': []}
    for round_number in range(args.rounds):
        first = ('baseline', 'candidate') if args.order == 'baseline-first' else (
            'candidate', 'baseline')
        order = first if round_number % 2 == 0 else first[::-1]
        for arm in order:
            curve = (old_curves.CurvePb if arm == 'baseline' else
                     new_curves.CurvePb)(onb.pb)
            started = time.perf_counter_ns()
            if arm == 'baseline':
                output = old_indexcalc.factorBase(onb, curve, args.weight)
            else:
                output = new_indexcalc.factorBase(onb, curve, args.weight, True)
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
    medians = {name: statistics.median(row['operation_ns'] for row in rows)
               for name, rows in samples.items()}
    args.out.write_text(json.dumps({
        'case': vars(args) | {'out': str(args.out)},
        'exact_output_agreement': True,
        'actual_base_points': len(expected[0]),
        'orbits': len(expected[1]),
        'first_call_ns': {'baseline': first_old, 'candidate': first_new},
        'samples': samples,
        'median_operation_ns': medians,
        'source_sha256': {
            'field': digest(source_dir / 'field.py'),
            'baseline-curves': digest(HERE / 'baseline/curves-runner.py'),
            'candidate-curves': digest(HERE / 'source/curves-runner.py'),
            'baseline-indexcalc': digest(HERE / 'baseline/indexcalc.py'),
            'candidate-indexcalc': digest(HERE / 'source/indexcalc.py'),
        },
        'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
