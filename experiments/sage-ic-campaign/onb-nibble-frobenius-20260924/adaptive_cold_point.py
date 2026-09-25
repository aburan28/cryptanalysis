"""One first parent/adaptive point recovery in a fresh Python process."""

import importlib.util
import json
import sys
import time
from pathlib import Path


here = Path(__file__).resolve().parent
root = here.parents[2]
variant, outcome = sys.argv[1:]
field_path = here / 'baseline/field.py' if variant == 'parent' else \
    root / 'ecc2k130/codegen/field.py'
spec = importlib.util.spec_from_file_location('cold_field', field_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.modules['field'] = module
curve_path = root / 'ecc2k130/codegen/curves.py'
spec = importlib.util.spec_from_file_location('cold_curve', curve_path)
curve_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve_module)


class RunnerField(module.Onb):
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
        return module.popcount(self.toCoords(value)) & 1


coords = {'valid': 2104348147882011174353649023374544053855,
          'invalid': 2028981750298864234240433540056293830655}
f = RunnerField(131)
c = curve_module.Curve(f)
x = f.fromCoords(coords[outcome])
start = time.perf_counter_ns()
result = c.pointFromX(x)
elapsed = time.perf_counter_ns() - start
assert (result is not None) == (outcome == 'valid')
print(json.dumps({'variant': variant, 'outcome': outcome, 'cold_ns': elapsed,
                  'cached_exponents_after': sorted(f.frobPositions)}))
