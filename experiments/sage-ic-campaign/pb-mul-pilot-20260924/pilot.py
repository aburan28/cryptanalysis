"""Exploratory paired multiplication pilot; no promotion decision is frozen."""

import hashlib
import importlib.util
import json
from pathlib import Path
import random
import statistics
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIELD = ROOT / 'experiments/sage-ic-campaign/pb-squaring-20260924/source/field-local.py'
CURVES = ROOT / 'experiments/sage-ic-campaign/pb-trace-mask-20260924/baseline/curves-local.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


field = load('field', FIELD)
sys.modules['field'] = field
curves = load('curves_pilot', CURVES)


class Sparse(field.Pb):
    def mul(self, a, b):
        if (a | b) >> self.m:
            return super().mul(a, b)
        result = 0
        while b:
            bit = b & -b
            result ^= a << (bit.bit_length() - 1)
            b ^= bit
        return field.polyMod(result, self.poly)


class Nibble(field.Pb):
    def mul(self, a, b):
        if (a | b) >> self.m:
            return super().mul(a, b)
        basis = (a, a << 1, a << 2, a << 3)
        table = [0] * 16
        for mask in range(1, 16):
            bit = mask & -mask
            table[mask] = table[mask ^ bit] ^ basis[bit.bit_length() - 1]
        result = 0
        shift = 0
        while b:
            result ^= table[b & 15] << shift
            b >>= 4
            shift += 4
        return field.polyMod(result, self.poly)


def main():
    rows = []
    for m in (11, 15, 53, 131):
        poly, _ = curves.findIrreduciblePoly(m)
        fields = [cls(m, poly) for cls in (field.Pb, Sparse, Nibble)]
        rng = random.Random(2026093000 + m)
        pairs = [(rng.randrange(1 << m), rng.randrange(1 << m))
                 for _ in range(256)]
        curve = curves.CurvePb(fields[0])
        points = []
        while len(points) < 3:
            point = curve.pointFromX(rng.randrange(1, 1 << m))
            if point is not None:
                points.append(point)
        scalar = (1 << 31) | rng.getrandbits(31)
        for operation, fn in (
                ('field_mul', lambda f: [f.mul(a, b) for a, b in pairs]),
                ('point_scalar', lambda f: [curves.CurvePb(f).mul(p, scalar)
                                             for p in points])):
            expected = fn(fields[0])
            samples = [[], [], []]
            for round_number in range(12):
                order = range(3) if round_number % 2 == 0 else (2, 1, 0)
                for index in order:
                    started = time.perf_counter_ns()
                    actual = fn(fields[index])
                    elapsed = time.perf_counter_ns() - started
                    assert actual == expected
                    samples[index].append(elapsed)
            medians = [statistics.median(values) for values in samples]
            rows.append({
                'degree': m,
                'operation': operation,
                'seed': 2026093000 + m,
                'exact_output_agreement': True,
                'samples_ns': dict(zip(('baseline', 'sparse', 'nibble'), samples)),
                'median_ns': dict(zip(('baseline', 'sparse', 'nibble'), medians)),
                'speedup': {'sparse': medians[0] / medians[1],
                            'nibble': medians[0] / medians[2]},
            })
    output = {
        'status': 'exploratory held pilot; no independent confirmation',
        'source_sha256': {
            'field': hashlib.sha256(FIELD.read_bytes()).hexdigest(),
            'curves': hashlib.sha256(CURVES.read_bytes()).hexdigest(),
        },
        'rows': rows,
    }
    (HERE / 'run-001.json').write_text(json.dumps(output, indent=2) + '\n')
    for row in rows:
        print(row['degree'], row['operation'],
              {name: round(value, 3) for name, value in row['speedup'].items()})


if __name__ == '__main__':
    main()
