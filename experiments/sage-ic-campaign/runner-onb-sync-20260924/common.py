"""Load frozen and candidate runner copies with the runner's field overrides."""

import importlib.util
import sys
from pathlib import Path


here = Path(__file__).resolve().parent
root = here.parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load(here / 'baseline/field.py', 'old_field')
new = load(root / 'ecc2k130/runner/codegen/field.py', 'new_field')
sys.modules['field'] = old
old_curves = load(here / 'baseline/curves.py', 'old_curves')
sys.modules['field'] = new
new_curves = load(root / 'ecc2k130/runner/codegen/curves.py', 'new_curves')


class RunnerOverrides:
    """The IC runner's AuditField inv/trace, without instrumentation cost."""

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
        bit_count = getattr(int, 'bit_count', new.popcount)
        return bit_count(self.toCoords(value)) & 1


class OldRunnerField(RunnerOverrides, old.Onb):
    pass


class NewRunnerField(RunnerOverrides, new.Onb):
    pass
