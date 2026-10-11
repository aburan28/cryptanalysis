"""Fresh-process peak RSS for complete 4,096-pair public P+Q calls."""
import argparse
import importlib.util
import json
import resource
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF, set_random_seed
from sage.schemes.elliptic_curves import ell_point

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
set_random_seed(2026098001)
points, _ = generate(curve, 128, 2026098001)
pairs = [(points[i % len(points)], points[(5*i+7) % len(points)])
         for i in range(4096)]
cls = ell_point.EllipticCurvePoint_finite_field
candidate = cls._add_
spec = importlib.util.spec_from_file_location('old_ell_point',
                                               HERE / 'baseline/ell_point.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cls._add_ = module.EllipticCurvePoint_field._add_
expected = [P+Q for P, Q in pairs]
cls._add_ = candidate if args.arm == 'candidate' else module.EllipticCurvePoint_field._add_
before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
for _ in range(6):
    actual = [P+Q for P, Q in pairs]
    assert actual == expected
    del actual
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
args.out.write_text(json.dumps({
    'arm': args.arm, 'before_rss_bytes': before,
    'peak_rss_bytes': peak, 'verified_outputs': 6*len(pairs),
}, indent=2) + '\n')
print(args.arm, peak)
