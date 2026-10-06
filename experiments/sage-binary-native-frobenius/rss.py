"""Fresh-process peak RSS for one full 4096-point Frobenius call."""
import argparse
import importlib.util
import json
import resource
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_batch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'sage-binary-hardware'))
from public_points import generate

parser = argparse.ArgumentParser()
parser.add_argument('--arm', choices=('incumbent', 'candidate'), required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
field = GF(2**131, 'z', impl='ntl')
curve = EllipticCurve(field, [1, 1, 0, 0, 1])
base, _ = generate(curve, 128, 2026092491)
points = [base[i % len(base)] for i in range(4096)]
expected = [curve.frobenius_isogeny(1)(P) for P in points]
if args.arm == 'incumbent':
    spec = importlib.util.spec_from_file_location('incumbent', HERE / 'baseline/binary_batch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
else:
    module = binary_batch
before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
for _ in range(12):
    actual = module.frobenius_points(curve, points, 1)
    assert actual == expected
    del actual
after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
args.out.write_text(json.dumps({'arm': args.arm, 'max_rss_bytes': after,
                                'before_rss_bytes': before, 'verified_outputs': 12 * 4096},
                               indent=2) + '\n')
print(args.arm, after)
