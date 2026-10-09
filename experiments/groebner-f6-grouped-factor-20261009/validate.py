"""Frozen grouped-factor replay against independent Boolean and curve models."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'groebner-f6-wide-boundary-20261009'))
from wide_query import DEPENDENCIES, load_runtime  # noqa: E402
MAX_STATES = 200_000_000
CASES = ((9, 4, 4, 1, 22), (9, 4, 5, 1, 23),
         (9, 5, 5, 1, 23), (9, 4, 6, 1, 24),
         (9, 5, 6, 1, 24))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def source_receipt(runtime_root):
    if git('status', '--porcelain').strip():
        raise AssertionError('experiment checkout must be clean and committed')
    commit = git('rev-parse', 'HEAD').decode().strip()
    sources = {}
    for path in [*HERE.glob('*.py'), *HERE.glob('*.cpp'),
                 ROOT / 'experiments/groebner-f6-wide-boundary-20261009/wide_query.py']:
        name = str(path.relative_to(ROOT))
        data = path.read_bytes()
        assert data == git('show', 'HEAD:' + name), name
        sources[name] = sha(data)
    dirs = ['experiments/' + name for name in DEPENDENCIES]
    for encoded in git('ls-files', '-z', '--', *dirs).split(b'\0'):
        if not encoded:
            continue
        name = encoded.decode()
        if Path(name).suffix not in ('.py', '.cpp', '.h', '.hpp'):
            continue
        expected = git('show', 'HEAD:' + name)
        actual = (runtime_root / name).read_bytes()
        assert actual == expected, name
        sources[name] = sha(actual)
    build = json.loads((HERE / 'build/receipt.json').read_text())
    assert build['source_commit'] == commit
    for name, digest in build['sources'].items():
        assert sources[name] == digest, name
    for name, digest in build['binaries'].items():
        assert sha((HERE / 'build' / name).read_bytes()) == digest, name
    return commit, sources, build


def save(path, value):
    data = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    path.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))


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


def random_controls(grouped_layout_type, sanitized, journal):
    rows = []
    for group_size in (1, 3, 9, 16):
        generator = random.Random(20261009 + group_size)
        for trial in range(20):
            equations = []
            for _ in range(group_size):
                terms = [generator.randrange(64)
                         for _ in range(generator.randrange(9))]
                if trial % 3 == 0 and terms:
                    terms.append(terms[0])
                equations.append(terms)
            solutions = [assignment for assignment in range(64)
                         if all(not (sum((assignment & term) == term
                                         for term in equation) & 1)
                                for equation in equations)]
            expected = 'satisfiable' if solutions else 'unsatisfiable'
            try:
                layout = grouped_layout_type(
                    6, equations, group_size, group_size, 0,
                    max_bag=6, max_states=100_000, sanitized=sanitized)
                try:
                    answer = layout.run([])
                    actual = answer['status']
                    assignment = answer['assignment']
                    match = (actual == expected and
                             ((assignment in solutions and
                               answer['independently_verified'] is True)
                              if solutions else assignment is None))
                finally:
                    layout.close()
                error = None
            except Exception as failure:
                actual, assignment, match = 'failure', None, False
                error = repr(failure)
            record = dict(group_size=group_size, trial=trial,
                          sanitized=sanitized, equations=equations,
                          expected=expected, actual=actual,
                          assignment=assignment, solution_count=len(solutions),
                          match=match, error=error)
            rows.append(record)
            journal.write(json.dumps(dict(kind='random', **record),
                                     sort_keys=True) + '\n')
            journal.flush()
    return rows


def baseline_answer(layout, case, runtime, auxiliary, summand, curve, target_x):
    start = time.perf_counter_ns()
    dynamic = runtime['equations'](runtime['GF2n'](case['n']),
        runtime['s3'](runtime['GF2n'](case['n']), case['curve_b'],
                      auxiliary, summand, {0: target_x}))
    result = layout.run(dynamic)
    point_verified = (runtime['point_replay'](
        curve, result['assignment'], case['m'], case['ell'], target_x)
        if result['assignment'] is not None else None)
    return dict(target_x=target_x, status=result['status'],
                assignment=result['assignment'],
                equation_verified=result['independently_verified'],
                point_verified=point_verified,
                online_ns=time.perf_counter_ns() - start,
                native=result)


def valid_answer(answer, expected):
    if answer.get('execution') != 'completed' or answer['status'] != expected:
        return False
    if expected == 'satisfiable':
        return (answer['assignment'] is not None and
                answer['equation_verified'] is True and
                answer['point_verified'] is True)
    return answer['assignment'] is None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    args = parser.parse_args()
    runtime_root = args.runtime_root.resolve()
    commit, sources, build = source_receipt(runtime_root)
    runtime = load_runtime(runtime_root)
    from grouped_query import GroupedContext, GroupedLayout
    args.output.mkdir(parents=True, exist_ok=False)
    report_path = args.output / 'report.json.gz'
    report = dict(schema='f6-grouped-factor-exact/1', status='RUNNING',
                  source_commit=commit, source_sha256=sources,
                  build_receipt=build, max_states=MAX_STATES,
                  random_controls=[], cases=[], width_control={},
                  timing_eligible=False, qualified_speedup=None)
    save(report_path, report)
    with (args.output / 'journal.jsonl').open('x') as journal:
        for sanitized in (False, True):
            controls = random_controls(GroupedLayout, sanitized, journal)
            report['random_controls'].extend(controls)
            save(report_path, report)
            print('F6_GROUPED_RANDOM', 'ubsan' if sanitized else 'optimized',
                  len(controls), sum(row['match'] for row in controls), flush=True)
        for n, m, ell, seed, max_bag in CASES:
            case = runtime['fixture'](n, m, ell, seed)
            reachable, base_size = reachable_x(case, runtime)
            expected_set = set(reachable)
            for sanitized in (False, True):
                record = dict(n=n, m=m, ell=ell, seed=seed,
                              max_bag=max_bag, max_states=MAX_STATES,
                              sanitized=sanitized, nvars=case['nvars'],
                              base_points=base_size, reachable_x=reachable,
                              rows=[], status='RUNNING')
                report['cases'].append(record)
                save(report_path, report)
                try:
                    grouped = GroupedContext(case, runtime, max_bag=max_bag,
                        max_states=MAX_STATES, sanitized=sanitized)
                except Exception as error:
                    record.update(status='FAIL', phase='grouped_setup',
                                  error=repr(error))
                    journal.write(json.dumps(dict(kind='setup', **record),
                                             sort_keys=True) + '\n')
                    journal.flush()
                    save(report_path, report)
                    continue
                baseline = None
                try:
                    try:
                        baseline = runtime['MessageLayout'](
                            case['nvars'], grouped.static,
                            grouped.boundary_mask, max_bag=max_bag,
                            max_states=MAX_STATES, sanitized=sanitized)
                        baseline_status = 'complete'
                    except RuntimeError as error:
                        baseline_status = {4: 'state-cap', 3: 'width-cap'}.get(
                            int(str(error).rsplit(': ', 1)[-1]), 'failure')
                    record.update(grouped_setup=grouped.layout.setup,
                                  grouped_setup_ns=grouped.setup_ns,
                                  boundary_bits=grouped.boundary_mask.bit_count(),
                                  baseline_status=baseline_status,
                                  baseline_setup=baseline.setup if baseline else None)
                    journal.write(json.dumps(dict(kind='setup', n=n, m=m,
                        ell=ell, seed=seed, sanitized=sanitized,
                        grouped_setup=record['grouped_setup'],
                        baseline_status=baseline_status), sort_keys=True) + '\n')
                    journal.flush()
                    curve = grouped.curve
                    for target_x in range(1 << n):
                        expected = ('satisfiable' if target_x in expected_set
                                    else 'unsatisfiable')
                        arms = ('grouped', 'baseline') if target_x % 2 == 0 else (
                            'baseline', 'grouped')
                        answers = {}
                        for arm in arms:
                            if arm == 'baseline' and baseline is None:
                                continue
                            try:
                                if arm == 'grouped':
                                    answer = grouped.run(target_x)
                                else:
                                    answer = baseline_answer(
                                        baseline, case, runtime,
                                        grouped.auxiliary, grouped.summand,
                                        curve, target_x)
                                answer['execution'] = 'completed'
                            except Exception as error:
                                answer = dict(target_x=target_x,
                                              execution='failure',
                                              error=repr(error))
                            answers[arm] = answer
                            journal.write(json.dumps(dict(kind='query', n=n,
                                m=m, ell=ell, seed=seed,
                                sanitized=sanitized, arm=arm, **answer),
                                sort_keys=True) + '\n')
                            journal.flush()
                        match = (valid_answer(answers['grouped'], expected) and
                                 (valid_answer(answers['baseline'], expected)
                                  if baseline is not None else
                                  baseline_status == 'state-cap'))
                        record['rows'].append(dict(target_x=target_x,
                            expected=expected, grouped=answers['grouped'],
                            baseline=answers.get('baseline'), match=match))
                    expected_baseline = ('complete' if ell <= 5 else 'state-cap')
                    record['status'] = ('PASS' if len(record['rows']) == 1 << n
                                        and all(row['match'] for row in record['rows'])
                                        and baseline_status == expected_baseline
                                        else 'FAIL')
                finally:
                    if baseline is not None:
                        baseline.close()
                    grouped.close()
                save(report_path, report)
                print('F6_GROUPED_CASE', m, ell, max_bag,
                      'ubsan' if sanitized else 'optimized', record['status'],
                      record.get('baseline_status'),
                      record.get('grouped_setup', {}).get('factor_states'),
                      flush=True)
        case = runtime['fixture'](9, 4, 7, 1)
        from grouped_query import GroupedContext
        try:
            context = GroupedContext(case, runtime, max_bag=24,
                                     max_states=MAX_STATES)
        except RuntimeError as error:
            actual = {3: 'width-cap', 4: 'state-cap'}.get(
                int(str(error).rsplit(': ', 1)[-1]), 'failure')
        else:
            context.close()
            actual = 'complete'
        report['width_control'] = dict(m=4, ell=7, max_bag=24,
                                       expected='width-cap', actual=actual,
                                       match=actual == 'width-cap')
        journal.write(json.dumps(dict(kind='width_control',
            **report['width_control']), sort_keys=True) + '\n')
        journal.flush()
    report['status'] = ('PASS' if
        all(row['match'] for row in report['random_controls']) and
        all(case['status'] == 'PASS' for case in report['cases']) and
        report['width_control']['match'] else 'FAIL')
    save(report_path, report)
    print('F6_GROUPED_RESULT', report['status'], len(report['cases']),
          sum(len(case['rows']) for case in report['cases']),
          sha(report_path.read_bytes()), flush=True)
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
