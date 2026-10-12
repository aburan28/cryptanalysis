"""Check reusable S3 bitplanes against independent curve-sum enumeration."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ((9, 3, 3, 1), (9, 4, 3, 1), (9, 5, 3, 1),
         (9, 6, 3, 1), (9, 3, 4, 1))
SOURCE_PATHS = (
    'experiments/groebner-f6-bitplane-target-20261009/bitplane_separator.cpp',
    'experiments/groebner-f6-bitplane-target-20261009/bitplane_query.py',
    'experiments/groebner-f6-packed-target-20261009/packed_query.py',
    'experiments/groebner-f6-packed-20261009/chain_fixture.py',
    'experiments/pdp-scaling/gf2n.py',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_sources(runtime_root):
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                     text=True).strip()
    assert (HERE / 'validate.py').read_bytes() == subprocess.check_output(
        ['git', 'show', 'HEAD:experiments/groebner-f6-chain-scaling-20261009/validate.py'],
        cwd=ROOT)
    assert not subprocess.check_output(['git', 'status', '--porcelain'],
                                       cwd=ROOT).strip()
    sources = {}
    for name in SOURCE_PATHS:
        expected = subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=ROOT)
        actual = (runtime_root / name).read_bytes()
        assert actual == expected, name
        sources[name] = sha(actual)
    build_dir = runtime_root / 'experiments/groebner-f6-bitplane-target-20261009/build'
    build = json.loads((build_dir / 'receipt.json').read_text())
    for filename, digest in build['binaries'].items():
        assert sha((build_dir / filename).read_bytes()) == digest
    return commit, sources, build


def reachable_x(n, m, ell, curve_type, field_type):
    curve = curve_type(field_type(n), 1)
    base = []
    for x in range(1 << ell):
        point = curve.lift_x(x)
        if point is None:
            continue
        base.append(point)
        opposite = curve.neg(point)
        if opposite != point:
            base.append(opposite)
    reachable = set(base)
    for _ in range(m - 1):
        reachable = {curve.add(point, summand)
                     for point in reachable for summand in base}
    return sorted({point.x for point in reachable if not point.inf}), len(base)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    args = parser.parse_args()
    runtime_root = args.runtime_root.resolve()
    commit, sources, build = check_sources(runtime_root)
    experiments = runtime_root / 'experiments'
    sys.path.insert(0, str(experiments / 'groebner-f6-bitplane-target-20261009'))
    sys.path.insert(0, str(experiments / 'groebner-f6-packed-20261009'))
    sys.path.insert(0, str(experiments / 'pdp-scaling'))
    from bitplane_query import BitplaneContext, STATUS
    from chain_fixture import fixture
    from gf2n import Curve, GF2n
    assert STATUS[3] == 'width-cap'

    report = dict(schema='f6-bitplane-chain-scaling/1', status='RUNNING',
                  source_commit=commit, runtime_build=build, sources=sources,
                  timing_eligible=False, qualified_speedup=None,
                  cases=[], cap_controls=[])
    for n, m, ell, seed in CASES:
        case = fixture(n, m, ell, seed)
        expected, base_size = reachable_x(n, m, ell, Curve, GF2n)
        expected_set = set(expected)
        context = BitplaneContext(case)
        rows = []
        try:
            boundary = context.index.boundary_mask.bit_count()
            for target_x in range(1 << n):
                packed = context.run(target_x, 'packed')
                bitplane = context.run(target_x, 'bitplane')
                actual = bitplane['status'] == 'satisfiable'
                match = (packed['status'] == bitplane['status'] and
                         actual == (target_x in expected_set) and
                         (not actual or
                          (bitplane['equation_verified'] is True and
                           bitplane['point_verified'] is True)))
                rows.append(dict(target_x=target_x,
                                 packed_status=packed['status'],
                                 bitplane_status=bitplane['status'],
                                 assignment=bitplane['assignment'],
                                 equation_verified=bitplane['equation_verified'],
                                 point_verified=bitplane['point_verified'],
                                 curve_sum_reachable=target_x in expected_set,
                                 match=match))
        finally:
            context.close()
        record = dict(n=n, m=m, ell=ell, seed=seed, nvars=case['nvars'],
                      boundary_bits=boundary, base_points=base_size,
                      reachable_x=expected, static_setup=context.index.setup,
                      status='PASS' if len(rows) == 1 << n and
                      all(row['match'] for row in rows) else 'FAIL', rows=rows)
        report['cases'].append(record)
        print('F6_CHAIN_CASE', m, ell, record['status'], boundary,
              len(expected), flush=True)
    for m in (4, 5, 6):
        case = fixture(9, m, 4, 1)
        try:
            context = BitplaneContext(case)
        except RuntimeError as error:
            status = 'EXPECTED_WIDTH_CAP' if 'prepared factor setup failed: 3' in str(error) else 'FAIL'
            report['cap_controls'].append(dict(m=m, ell=4, nvars=case['nvars'],
                                               status=status, native_status_code=3,
                                               native_status=STATUS[3], error=str(error)))
        else:
            context.close()
            report['cap_controls'].append(dict(m=m, ell=4, nvars=case['nvars'],
                                               status='UNEXPECTED_SUCCESS'))
    report['status'] = ('PASS' if all(case['status'] == 'PASS' for case in report['cases'])
                        and all(case['status'] == 'EXPECTED_WIDTH_CAP'
                                for case in report['cap_controls']) else 'FAIL')
    data = (json.dumps(report, sort_keys=True, separators=(',', ':')) + '\n').encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))
    print('F6_CHAIN_SCALING', report['status'], len(report['cases']),
          sum(len(case['rows']) for case in report['cases']),
          sha(args.output.read_bytes()), flush=True)
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
