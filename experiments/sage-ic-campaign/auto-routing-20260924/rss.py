"""Fresh-process RSS for a degree-131 power-65 complete point-map plan."""
import argparse
import json
import resource
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves.binary_hardware import FrobeniusPlan

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate

parser = argparse.ArgumentParser()
parser.add_argument('--arm', choices=('sage', 'auto'), required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()

field = GF(2**131, 'z', impl='ntl')
curve = EllipticCurve(field, [1, 1, 0, 0, 1])
base, _ = generate(curve, 128, 2026094701)
points = [base[i % len(base)] for i in range(4096)]
phi = curve.frobenius_isogeny(65)
expected = [phi(point) for point in points]
before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
with FrobeniusPlan(curve, 65, backend=args.arm) as plan:
    for _ in range(12):
        actual = plan.apply(points)
        assert actual == expected
        del actual
    selected = plan.last_backend
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
args.out.write_text(json.dumps({
    'arm': args.arm, 'selected_backend': selected,
    'before_rss_bytes': before, 'peak_rss_bytes': peak,
    'verified_outputs': 12 * len(points),
}, indent=2) + '\n')
print(args.arm, selected, peak)
