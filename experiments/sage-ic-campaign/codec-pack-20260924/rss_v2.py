"""Fresh-process memory check for the measured output codec."""
import argparse
import json
import resource
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_hardware

from benchmark_v2 import incumbent_hardware
from public_points import generate


parser = argparse.ArgumentParser()
parser.add_argument('--arm', choices=('incumbent', 'candidate'), required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()

field = GF(2**131, 'z', impl='ntl')
curve = EllipticCurve(field, [1, 1, 0, 0, 1])
base, _ = generate(curve, 128, 2026093801)
points = [base[i % len(base)] for i in range(4096)]
expected = [curve.frobenius_isogeny(65)(point) for point in points]
module = incumbent_hardware() if args.arm == 'incumbent' else binary_hardware
plan = module.FrobeniusPlan(curve, 65, backend='cpu', cpu_threads=1)
before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
for _ in range(12):
    actual = plan.apply(points)
    assert actual == expected
    del actual
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
plan.close()
args.out.write_text(json.dumps({
    'arm': args.arm,
    'before_rss_bytes': before,
    'peak_rss_bytes': peak,
    'verified_outputs': len(points) * 12,
}, indent=2) + '\n')
print(args.arm, peak)
