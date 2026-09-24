"""Exact cold/warm point-recovery pilot for cached half-trace images."""

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
FIELD = ROOT / 'experiments/sage-ic-campaign/pb-squaring-20260924/source/field-local.py'
CURVES = ROOT / 'experiments/sage-ic-campaign/pb-trace-mask-20260924/source/curves-local.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


field = load('field', FIELD)
sys.modules['field'] = field
curves = load('curves_pilot', CURVES)


class Cached(curves.CurvePb):
    def __init__(self, pb):
        super().__init__(pb)
        self.images = None

    def halfTrace(self, a):
        if a >> self.f.m:
            return super().halfTrace(a)
        if self.images is None:
            self.images = tuple(curves.CurvePb.halfTrace(self, 1 << i)
                                for i in range(self.f.m))
        result = 0
        while a:
            bit = a & -a
            result ^= self.images[bit.bit_length() - 1]
            a ^= bit
        return result


def measure(fn):
    started = time.perf_counter_ns()
    output = fn()
    return output, time.perf_counter_ns() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--degree', type=int, choices=(11, 15, 53, 131), required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    m = args.degree
    poly, _ = curves.findIrreduciblePoly(m)
    rng = random.Random(args.seed)
    xs = [rng.randrange(1, 1 << m) for _ in range(1024)]
    def make(candidate):
        return (Cached if candidate else curves.CurvePb)(field.Pb(m, poly))

    # The first call includes construction of the candidate's image table.
    first = {}
    for name, candidate in (('baseline', False), ('candidate', True)):
        curve = make(candidate)
        first[name], first[name + '_ns'] = measure(lambda: curve.pointFromX(xs[0]))
    assert first['baseline'] == first['candidate']
    first_ns = {name: first[name + '_ns'] for name in ('baseline', 'candidate')}

    cold = {}
    for size in (64, 256, 1024):
        outcomes = {}
        order = (('baseline', False), ('candidate', True)) if args.seed % 2 else (
            ('candidate', True), ('baseline', False))
        for name, candidate in order:
            curve = make(candidate)
            output, elapsed = measure(lambda: [curve.pointFromX(x) for x in xs[:size]])
            outcomes[name] = {'output': output, 'operation_ns': elapsed}
        assert outcomes['baseline']['output'] == outcomes['candidate']['output']
        cold[str(size)] = {name: outcomes[name]['operation_ns']
                           for name in ('baseline', 'candidate')}

    old_curve, new_curve = make(False), make(True)
    expected = [old_curve.pointFromX(x) for x in xs[:256]]
    assert [new_curve.pointFromX(x) for x in xs[:256]] == expected
    warm = {'baseline': [], 'candidate': []}
    for round_number in range(8):
        order = (('baseline', old_curve), ('candidate', new_curve)) if round_number % 2 == 0 else (
            ('candidate', new_curve), ('baseline', old_curve))
        for name, curve in order:
            output, elapsed = measure(lambda: [curve.pointFromX(x) for x in xs[:256]])
            assert output == expected
            warm[name].append(elapsed)
    medians = {name: statistics.median(values) for name, values in warm.items()}
    receipt = {
        'status': 'exploratory paired cold/warm pilot; no production change',
        'case': {'degree': m, 'seed': args.seed, 'warm_rounds': 8},
        'source_sha256': {
            'field': hashlib.sha256(FIELD.read_bytes()).hexdigest(),
            'curves': hashlib.sha256(CURVES.read_bytes()).hexdigest(),
            'pilot': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        'exact_output_agreement': True,
        'first_call_ns': first_ns,
        'cold_batch_ns': cold,
        'warm_256_samples_ns': warm,
        'warm_256_median_ns': medians,
        'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    args.out.write_text(json.dumps(receipt, indent=2) + '\n')
    print('m%d seed%d first %.3fx cold64 %.3fx cold256 %.3fx cold1024 %.3fx warm256 %.3fx' % (
        m, args.seed,
        first_ns['baseline'] / first_ns['candidate'],
        cold['64']['baseline'] / cold['64']['candidate'],
        cold['256']['baseline'] / cold['256']['candidate'],
        cold['1024']['baseline'] / cold['1024']['candidate'],
        medians['baseline'] / medians['candidate']))


if __name__ == '__main__':
    main()
