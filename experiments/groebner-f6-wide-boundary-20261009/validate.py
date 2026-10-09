"""Frozen exact F6 boundary-width replay with independent curve reachability."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time

from wide_query import DEPENDENCIES, WideContext, load_runtime


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MAX_STATES = 200_000_000
# n, summands, coordinate bits, fixture seed, admitted maximum bag width.
CASES = (
    (9, 4, 4, 1, 22), (9, 5, 4, 1, 22), (9, 6, 4, 1, 22),
    (9, 4, 5, 1, 23), (9, 5, 5, 1, 23),
    (9, 3, 6, 1, 21), (9, 3, 7, 1, 23),
)
# A narrower admitted width or the unchanged 200M state cap rejects these.
CAPS = (
    (9, 4, 4, 1, 21, 'width-cap'),
    (9, 5, 5, 1, 22, 'width-cap'),
    (9, 4, 6, 1, 24, 'state-cap'),
    (9, 4, 7, 1, 24, 'width-cap'),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def source_receipt(runtime_root):
    if git('status', '--porcelain').strip():
        raise AssertionError('experiment checkout must be clean and committed')
    commit = git('rev-parse', 'HEAD').decode().strip()
    sources = {}
    for path in (HERE / 'wide_query.py', HERE / 'validate.py'):
        name = str(path.relative_to(ROOT))
        data = path.read_bytes()
        assert data == git('show', 'HEAD:' + name), name
        sources[name] = sha(data)
    directories = ['experiments/' + name for name in DEPENDENCIES]
    listed = git('ls-files', '-z', '--', *directories).split(b'\0')
    for encoded in listed:
        if not encoded:
            continue
        name = encoded.decode()
        if Path(name).suffix not in ('.py', '.cpp', '.h', '.hpp'):
            continue
        expected = git('show', 'HEAD:' + name)
        actual = (runtime_root / name).read_bytes()
        assert actual == expected, name
        sources[name] = sha(actual)
    receipts = {}
    for name in ('groebner-f6-boundary-compact-20261009',
                 'groebner-f6-bitplane-target-20261009'):
        directory = runtime_root / 'experiments' / name / 'build'
        receipt = json.loads((directory / 'receipt.json').read_text())
        for binary, digest in receipt['binaries'].items():
            assert sha((directory / binary).read_bytes()) == digest
        receipts[name] = receipt
    return commit, sources, receipts


def reachable_x(case, runtime):
    curve = runtime['Curve'](runtime['GF2n'](case['n']), case['curve_b'])
    base = []
    for x in range(1 << case['ell']):
        point = curve.lift_x(x)
        if point is None:
            continue
        base.append(point)
        opposite = curve.neg(point)
        if opposite != point:
            base.append(opposite)
    reachable = set(base)
    for _ in range(case['m'] - 1):
        reachable = {curve.add(point, summand)
                     for point in reachable for summand in base}
    return sorted({point.x for point in reachable if not point.inf}), len(base)


def static_boundary(case, runtime):
    prefix, suffix = runtime['split_case'](case)
    m, ell, n = case['m'], case['ell'], case['n']
    auxiliary = runtime['coordinate'](m * ell + (m - 3) * n, n)
    summand = runtime['coordinate']((m - 1) * ell, ell)
    boundary = 0
    for mask in [*auxiliary, *summand]:
        boundary |= mask
    return prefix + suffix, boundary


def save(path, value):
    data = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    path.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    args = parser.parse_args()
    runtime_root = args.runtime_root.resolve()
    commit, sources, receipts = source_receipt(runtime_root)
    runtime = load_runtime(runtime_root)
    args.output.mkdir(parents=True, exist_ok=False)
    report_path = args.output / 'report.json.gz'
    report = dict(schema='f6-wide-boundary-exact/1', status='RUNNING',
                  source_commit=commit, source_sha256=sources,
                  build_receipts=receipts, max_states=MAX_STATES,
                  cases=[], cap_controls=[], nonaffine_control={},
                  timing_eligible=False, qualified_speedup=None)
    save(report_path, report)
    with (args.output / 'journal.jsonl').open('x') as journal:
        for n, m, ell, seed, max_bag in CASES:
            case = runtime['fixture'](n, m, ell, seed)
            expected, base_size = reachable_x(case, runtime)
            expected_set = set(expected)
            for sanitized in (False, True):
                try:
                    context = WideContext(case, runtime, max_bag=max_bag,
                                          max_states=MAX_STATES,
                                          sanitized=sanitized)
                except Exception as error:
                    record = dict(n=n, m=m, ell=ell, seed=seed,
                                  max_bag=max_bag, max_states=MAX_STATES,
                                  sanitized=sanitized, nvars=case['nvars'],
                                  base_points=base_size, reachable_x=expected,
                                  status='FAIL', phase='setup',
                                  error=repr(error), rows=[])
                    report['cases'].append(record)
                    journal.write(json.dumps(record, sort_keys=True) + '\n')
                    journal.flush()
                    save(report_path, report)
                    print('F6_WIDE_CASE', m, ell, max_bag,
                          'ubsan' if sanitized else 'optimized', 'FAIL_SETUP',
                          flush=True)
                    continue
                rows = []
                try:
                    for target_x in range(1 << n):
                        order = ('compact', 'bitplane') if target_x % 2 == 0 else (
                            'bitplane', 'compact')
                        answers = {}
                        for arm in order:
                            try:
                                answer = context.run(target_x, arm)
                                answer['execution'] = 'completed'
                            except Exception as error:
                                answer = dict(arm=arm, target_x=target_x,
                                              execution='failure', error=repr(error))
                            answers[arm] = answer
                            journal.write(json.dumps(dict(n=n, m=m, ell=ell,
                                seed=seed, max_bag=max_bag, sanitized=sanitized,
                                **answer), sort_keys=True) + '\n')
                            journal.flush()
                        left, right = answers['compact'], answers['bitplane']
                        expected_status = ('satisfiable' if target_x in expected_set
                                           else 'unsatisfiable')
                        match = all(
                            answer['execution'] == 'completed' and
                            answer['status'] == expected_status and
                            ((answer['assignment'] is not None and
                              answer['equation_verified'] is True and
                              answer['point_verified'] is True)
                             if expected_status == 'satisfiable' else
                             answer['assignment'] is None)
                            for answer in (left, right))
                        rows.append(dict(target_x=target_x,
                                         expected_status=expected_status,
                                         compact=left, bitplane=right, match=match))
                finally:
                    context.close()
                record = dict(n=n, m=m, ell=ell, seed=seed,
                              max_bag=max_bag, max_states=MAX_STATES,
                              sanitized=sanitized, nvars=case['nvars'],
                              boundary_bits=context.boundary_mask.bit_count(),
                              base_points=base_size, reachable_x=expected,
                              setup_ns=context.setup_ns,
                              compact_setup=context.compact.setup,
                              bitplane_setup=context.bitplane.setup,
                              status=('PASS' if len(rows) == 1 << n and
                                      all(row['match'] for row in rows) else 'FAIL'),
                              rows=rows)
                report['cases'].append(record)
                save(report_path, report)
                print('F6_WIDE_CASE', m, ell, max_bag,
                      'ubsan' if sanitized else 'optimized', record['status'],
                      record['boundary_bits'], len(expected), flush=True)
        for n, m, ell, seed, max_bag, expected_status in CAPS:
            case = runtime['fixture'](n, m, ell, seed)
            static, boundary = static_boundary(case, runtime)
            start = time.perf_counter_ns()
            try:
                layout = runtime['MessageLayout'](
                    case['nvars'], static, boundary, max_bag=max_bag,
                    max_states=MAX_STATES)
            except RuntimeError as error:
                actual_status = {3: 'width-cap', 4: 'state-cap'}.get(
                    int(str(error).rsplit(': ', 1)[-1]), 'other')
                detail = str(error)
            else:
                layout.close()
                actual_status, detail = 'success', ''
            record = dict(n=n, m=m, ell=ell, seed=seed, max_bag=max_bag,
                          nvars=case['nvars'], boundary_bits=boundary.bit_count(),
                          max_states=MAX_STATES, expected=expected_status,
                          actual=actual_status, detail=detail,
                          setup_ns=time.perf_counter_ns() - start,
                          match=actual_status == expected_status)
            report['cap_controls'].append(record)
            save(report_path, report)
            print('F6_WIDE_CAP', m, ell, max_bag, actual_status, flush=True)
    # u0*u1*x0 vanishes at target zero and both basis targets, yet not at u=3.
    actual = [(u & 1) * ((u >> 1) & 1) for u in range(4)]
    affine_prediction = [actual[0] ^ ((u & 1) * (actual[1] ^ actual[0])) ^
                         (((u >> 1) & 1) * (actual[2] ^ actual[0]))
                         for u in range(4)]
    report['nonaffine_control'] = dict(actual=actual, affine_prediction=affine_prediction,
                                       mismatch_at_three=actual[3] != affine_prediction[3])
    report['status'] = ('PASS' if all(row['status'] == 'PASS' for row in report['cases'])
                        and all(row['match'] for row in report['cap_controls'])
                        and report['nonaffine_control']['mismatch_at_three']
                        else 'FAIL')
    save(report_path, report)
    print('F6_WIDE_RESULT', report['status'], len(report['cases']),
          sum(len(row['rows']) for row in report['cases']),
          sha(report_path.read_bytes()), flush=True)
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
