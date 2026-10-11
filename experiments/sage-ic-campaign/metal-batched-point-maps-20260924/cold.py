"""One fresh-process plan construction and exact complete point-map call."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SAGE_ROOT = Path('/Volumes/SSD990/cryptanalysis/third_party/sage-binary')
NATIVE = (SAGE_ROOT / 'local/var/lib/sage/venv-python3.14/lib/python3.14/'
          'site-packages/sage/schemes/elliptic_curves/_binary_hardware_native.dylib')
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--points', type=int, required=True)
    parser.add_argument('--groups', type=int, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--arm', choices=('metal_separate', 'metal_batched',
                                          'cpu_separate', 'cpu_batched'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()

    from sage.all import EllipticCurve, GF, set_random_seed
    from sage.schemes.elliptic_curves.binary_batch import frobenius_points
    from sage.schemes.elliptic_curves.binary_hardware import FrobeniusPlan as Baseline
    from public_points import generate
    spec = importlib.util.spec_from_file_location(
        'sage_binary_hardware_batched', HERE / 'source/binary_hardware.py')
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)

    set_random_seed(args.seed)
    field = GF(2**131, 'z')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    points, attempts = generate(curve, args.points, args.seed)
    points[:3] = [curve(0), curve(0, 1), points[3]]
    width = args.points // args.groups
    groups = [points[i:i + width] for i in range(0, len(points), width)]
    expected = [frobenius_points(curve, group, 65) for group in groups]
    klass = candidate.FrobeniusPlan if args.arm.endswith('batched') else Baseline
    backend = args.arm.split('_')[0]
    start = time.perf_counter_ns()
    plan = klass(curve, 65, backend, native_library=NATIVE)
    constructed = time.perf_counter_ns()
    if args.arm.endswith('batched'):
        actual = plan.apply_batches(groups)
    else:
        actual = [plan.apply(group) for group in groups]
    computed = time.perf_counter_ns()
    assert actual == expected
    verified = time.perf_counter_ns()
    plan.close()
    args.out.write_text(json.dumps({
        'arm': args.arm, 'points': args.points, 'groups': args.groups,
        'seed': args.seed, 'attempts': attempts,
        'exact_output_agreement': True,
        'setup_ns': constructed - start,
        'operation_ns': computed - constructed,
        'setup_plus_operation_ns': computed - start,
        'verification_ns': verified - computed,
        'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'source_sha256': hashlib.sha256((HERE / 'source/binary_hardware.py').read_bytes()).hexdigest(),
        'native_sha256': hashlib.sha256(NATIVE.read_bytes()).hexdigest(),
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
