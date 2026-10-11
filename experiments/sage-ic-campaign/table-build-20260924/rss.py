"""Fresh-process peak RSS for old and vectorized CPU table plans."""
import argparse
import importlib.util
import json
import resource
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_hardware

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate

parser = argparse.ArgumentParser()
parser.add_argument('--arm', choices=('incumbent', 'candidate'), required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()

field = GF(2**131, 'z', impl='ntl')
curve = EllipticCurve(field, [1, 1, 0, 0, 1])
base, _ = generate(curve, 128, 2026095001)
points = [base[i % len(base)] for i in range(4096)]
phi = curve.frobenius_isogeny(65)
expected = [phi(point) for point in points]
if args.arm == 'incumbent':
    spec = importlib.util.spec_from_file_location('old_binary_hardware',
                                                   HERE / 'baseline-pr75/binary_hardware.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    module = binary_hardware
native = binary_hardware._library()._name
before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
with module.FrobeniusPlan(curve, 65, backend='cpu', native_library=native) as plan:
    for _ in range(12):
        actual = plan.apply(points)
        assert actual == expected
        del actual
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
args.out.write_text(json.dumps({
    'arm': args.arm, 'before_rss_bytes': before,
    'peak_rss_bytes': peak, 'verified_outputs': 12 * len(points),
}, indent=2) + '\n')
print(args.arm, peak)
