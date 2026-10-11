"""Exact point, batch-boundary, and lifetime checks for the optional API."""

import importlib.util
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves.binary_batch import frobenius_points


HERE = Path(__file__).resolve().parent
NATIVE = (Path('/Volumes/SSD990/cryptanalysis/third_party/sage-binary') /
          'local/var/lib/sage/venv-python3.14/lib/python3.14/site-packages/'
          'sage/schemes/elliptic_curves/_binary_hardware_native.dylib')
spec = importlib.util.spec_from_file_location(
    'sage_binary_hardware_batched', HERE / 'source/binary_hardware.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)

for degree in (5, 19, 131):
    field = GF(2**degree, 'z')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    other = EllipticCurve(field, [1, 0, 0, 0, 1])
    points = list(curve) if degree == 5 else [curve.random_point() for _ in range(11)]
    points[:2] = [curve(0), curve(0, 1)]
    batches = [[], points[:3], [], points[3:8], points[8:], []]
    expected = [frobenius_points(curve, batch, 7) for batch in batches]
    for backend in ('sage', 'cpu', 'metal'):
        with candidate.FrobeniusPlan(curve, 7, backend,
                                     native_library=NATIVE) as plan:
            assert plan.apply_batches(iter(iter(batch) for batch in batches)) == expected
            assert plan.apply_batches(iter(())) == []
            try:
                plan.apply_batches([points[:2], [other(0)]])
            except ValueError:
                pass
            else:
                raise AssertionError('foreign-curve point accepted')
        try:
            plan.apply_batches([])
        except RuntimeError:
            pass
        else:
            raise AssertionError('closed plan accepted batches')
print('batched Sage point checks passed')
