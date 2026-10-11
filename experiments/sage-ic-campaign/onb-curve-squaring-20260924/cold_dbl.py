"""Time one first doubling on a fresh field in a separate process."""

import argparse
import importlib.util
import json
import random
import sys
import time
from pathlib import Path


here = Path(__file__).resolve().parent
root = here.parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parser = argparse.ArgumentParser()
parser.add_argument('--variant', choices=('incumbent', 'candidate'), required=True)
args = parser.parse_args()
field = load(root / 'ecc2k130/codegen/field.py', 'field')
sys.modules['field'] = field
old_curves = load(here / 'baseline/curves.py', 'old_curves')
new_curves = load(root / 'ecc2k130/codegen/curves.py', 'new_curves')


class FastInverse(field.Onb):
    def inv(self, value):
        if not value:
            raise ZeroDivisionError()
        a, b, u, v = value, self.allOnes, 1, 0
        while a != 1:
            if not a:
                raise ValueError('nonunit in the ONB ring')
            shift = a.bit_length() - b.bit_length()
            if shift < 0:
                a, b, u, v = b, a, v, u
                shift = -shift
            a ^= b << shift
            u ^= v << shift
        while u.bit_length() >= self.allOnes.bit_length():
            u ^= self.allOnes << (u.bit_length() - self.allOnes.bit_length())
        return self.normalize(u)

    def trace(self, value):
        return self.toCoords(value).bit_count() & 1


rng = random.Random(20260928)
generator_field = FastInverse(131)
generator_curve = old_curves.Curve(generator_field)
point = None
while point is None:
    point = generator_curve.pointFromX(generator_field.fromCoords(rng.getrandbits(131)))
expected = generator_curve.dbl(point)
test_field = FastInverse(131)
curve = (old_curves if args.variant == 'incumbent' else new_curves).Curve(test_field)
assert not test_field.frobPositions
start = time.perf_counter_ns()
actual = curve.dbl(point)
elapsed = time.perf_counter_ns() - start
assert actual == expected
print(json.dumps({'variant': args.variant, 'cold_dbl_ns': elapsed,
                  'cached_exponents_after': sorted(test_field.frobPositions)}))
