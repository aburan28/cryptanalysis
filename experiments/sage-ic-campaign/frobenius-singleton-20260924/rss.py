"""Fresh-process peak RSS of repeated public Frobenius-isogeny calls."""
import argparse
import importlib.util
import json
import resource
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import hom_frobenius

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
base, _ = generate(curve, 128, 2026096301)
points = [base[i % len(base)] for i in range(4096)]
cls = hom_frobenius.EllipticCurveHom_frobenius
spec = importlib.util.spec_from_file_location(
    'old_hom_frobenius', HERE / 'baseline/hom_frobenius.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
reference = cls(curve, 65)
expected_base = [module.EllipticCurveHom_frobenius._call_(reference, point)
                 for point in base]
expected = [expected_base[i % len(expected_base)] for i in range(4096)]
if args.arm == 'incumbent':
    cls._call_ = module.EllipticCurveHom_frobenius._call_
phi = cls(curve, 65)
before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
for _ in range(6):
    actual = [phi(point) for point in points]
    assert actual == expected
    del actual
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
args.out.write_text(json.dumps({
    'arm': args.arm, 'before_rss_bytes': before,
    'peak_rss_bytes': peak, 'verified_outputs': 6 * len(points),
}, indent=2) + '\n')
print(args.arm, peak)
