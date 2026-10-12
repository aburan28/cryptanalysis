"""Exact cutset-branch replay against independently restricted curve sums."""
import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'groebner-f6-wide-boundary-20261009'))
from wide_query import DEPENDENCIES, load_runtime  # noqa: E402

CASES = ((9, 4, 7, 1), (9, 5, 7, 1))
MAX_BAG = 24
MAX_STATES = 200_000_000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def source_receipt(runtime_root):
    if git('status', '--porcelain').strip():
        raise AssertionError('experiment checkout must be clean and committed')
    commit = git('rev-parse', 'HEAD').decode().strip()
    sources = {}
    own = [*HERE.glob('*.py'),
           ROOT / 'experiments/groebner-f6-wide-boundary-20261009/wide_query.py']
    grouped = ROOT / 'experiments/groebner-f6-grouped-factor-20261009'
    own.extend([*grouped.glob('*.py'), *grouped.glob('*.cpp')])
    for path in own:
        name = str(path.relative_to(ROOT))
        actual = path.read_bytes()
        assert actual == git('show', 'HEAD:' + name), name
        sources[name] = sha(actual)
    directories = ['experiments/' + name for name in DEPENDENCIES]
    for encoded in git('ls-files', '-z', '--', *directories).split(b'\0'):
        if not encoded:
            continue
        name = encoded.decode()
        if Path(name).suffix not in ('.py', '.cpp', '.h', '.hpp'):
            continue
        expected = git('show', 'HEAD:' + name)
        actual = (runtime_root / name).read_bytes()
        assert actual == expected, name
        sources[name] = sha(actual)
    build = json.loads((grouped / 'build/receipt.json').read_text())
    for name, digest in build['sources'].items():
        assert sources[name] == digest, name
    for name, digest in build['binaries'].items():
        assert sha((grouped / 'build' / name).read_bytes()) == digest, name
    return commit, sources, build


def save(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def eval_anf(row, assignment):
    return sum((assignment & term) == term for term in row) & 1


def conditioning_controls(condition_equation):
    generator = random.Random(20261009)
    records = []
    for trial in range(64):
        row = [generator.randrange(256)
               for _ in range(generator.randrange(12))]
        if trial % 3 == 0 and row:
            row.append(row[0])
        bits = (1 << 2,) if trial % 2 == 0 else (1 << 2, 1 << 6)
        choices = tuple((bit, generator.randrange(2)) for bit in bits)
        conditioned = condition_equation(row, choices)
        fixed_mask = sum(bits)
        checked = 0
        mismatches = []
        for assignment in range(256):
            if any(bool(assignment & bit) != bool(value)
                   for bit, value in choices):
                continue
            if eval_anf(row, assignment) != eval_anf(
                    conditioned, assignment & ~fixed_mask):
                mismatches.append(assignment)
            checked += 1
        records.append(dict(trial=trial, row=row, choices=choices,
                            conditioned=conditioned,
                            compatible_assignments=checked,
                            mismatches=mismatches,
                            status='PASS' if not mismatches else 'FAIL'))
    return records


def restricted_curve_x(case, runtime, choices):
    curve = runtime['Curve'](runtime['GF2n'](case['n']), case['curve_b'])
    ell = case['ell']
    conditioned = {summand: value for summand, value in choices}
    bases = []
    for j in range(case['m']):
        points = []
        for x in range(1 << ell):
            if j in conditioned and ((x >> (ell - 1)) & 1) != conditioned[j]:
                continue
            point = curve.lift_x(x)
            if point is None:
                continue
            points.append(point)
            opposite = curve.neg(point)
            if opposite != point:
                points.append(opposite)
        bases.append(points)
    reachable = set(bases[0])
    for points in bases[1:]:
        reachable = {curve.add(left, right)
                     for left in reachable for right in points}
    return (sorted({point.x for point in reachable if not point.inf}),
            [len(points) for points in bases])


def restoration_control(grouped_layout_type, condition_equation):
    bit = 1 << 1
    row = [bit, 0]  # x+1 requires x=1.
    conditioned = condition_equation(row, ((bit, 1),))
    layout = grouped_layout_type(2, [conditioned], 1, 1, 0,
                                 max_bag=2, max_states=10_000)
    try:
        answer = layout.run([])
    finally:
        layout.close()
    native = answer['assignment']
    restored = native | bit if native is not None else None
    record = dict(original=row, conditioned=conditioned,
                  native_assignment=native, restored_assignment=restored,
                  native_fails_original=(native is not None and
                                         bool(eval_anf(row, native))),
                  restored_satisfies_original=(restored is not None and
                                               not bool(eval_anf(row, restored))))
    record['match'] = (answer['status'] == 'satisfiable' and
                       record['native_fails_original'] and
                       record['restored_satisfies_original'])
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    args = parser.parse_args()
    runtime_root = args.runtime_root.resolve()
    commit, sources, build = source_receipt(runtime_root)
    runtime = load_runtime(runtime_root)
    from cutset_query import CutsetContext, GroupedLayout, condition_equation
    args.output.mkdir(parents=True, exist_ok=False)
    report_path = args.output / 'report.json.gz'
    report = dict(schema='f6-cutset-exact/1', status='RUNNING',
                  source_commit=commit, source_sha256=sources,
                  grouped_build=build, max_bag=MAX_BAG,
                  max_states=MAX_STATES, controls={}, cases=[],
                  timing_eligible=False, qualified_speedup=None)
    save(report_path, report)
    with (args.output / 'journal.jsonl').open('x') as journal:
        report['controls']['conditioning'] = conditioning_controls(
            condition_equation)
        report['controls']['restoration'] = restoration_control(
            GroupedLayout, condition_equation)
        try:
            GroupedLayout(78, [], 0, 9, 0, max_bag=MAX_BAG,
                          max_states=MAX_STATES)
        except RuntimeError as error:
            abi_status = 'input-cap' if str(error).endswith(': 5') else 'failure'
        else:
            abi_status = 'unexpected-success'
        report['controls']['abi'] = dict(nvars=78, supported_max=64,
                                         actual=abi_status,
                                         match=abi_status == 'input-cap')
        journal.write(json.dumps(dict(kind='controls',
            controls=report['controls']), sort_keys=True) + '\n')
        journal.flush()
        save(report_path, report)
        for n, m, ell, seed in CASES:
            case = runtime['fixture'](n, m, ell, seed)
            branch_indices = tuple(range(2, m - 1))
            branch_choices = [tuple(zip(branch_indices, values))
                for values in itertools.product(
                    (0, 1), repeat=len(branch_indices))]
            expected = []
            sizes = []
            for choices in branch_choices:
                abscissae, base_sizes = restricted_curve_x(
                    case, runtime, choices)
                expected.append(abscissae)
                sizes.append(base_sizes)
            union = sorted(set().union(*(set(xs) for xs in expected)))
            unrestricted, _ = restricted_curve_x(case, runtime, ())
            union_matches = union == unrestricted
            sets = [set(xs) for xs in expected]
            union_set = set(union)
            for sanitized in (False, True):
                record = dict(n=n, m=m, ell=ell, seed=seed,
                              nvars=case['nvars'], sanitized=sanitized,
                              branch_choices=branch_choices,
                              branch_reachable_x=expected,
                              branch_base_points=sizes,
                              union_reachable_x=union,
                              unrestricted_reachable_x=unrestricted,
                              union_matches=union_matches,
                              rows=[], status='RUNNING')
                report['cases'].append(record)
                save(report_path, report)
                try:
                    context = CutsetContext(case, runtime, max_bag=MAX_BAG,
                        max_states=MAX_STATES, sanitized=sanitized)
                except Exception as error:
                    record.update(status='FAIL', phase='setup', error=repr(error))
                    journal.write(json.dumps(dict(kind='setup_failure',
                        **record), sort_keys=True) + '\n')
                    journal.flush()
                    save(report_path, report)
                    continue
                try:
                    record.update(setup_ns=context.setup_ns,
                        branch_bits=context.branch_bits,
                        boundary_bits=context.boundary_mask.bit_count(),
                        branch_setups=[branch['layout'].setup
                                       for branch in context.branches])
                    try:
                        context.check_dynamic_scope([[context.branch_bits[0]]])
                    except ValueError:
                        target_scope_rejected = True
                    else:
                        target_scope_rejected = False
                    record['target_scope_rejected'] = target_scope_rejected
                    journal.write(json.dumps(dict(kind='setup', n=n, m=m,
                        ell=ell, seed=seed, sanitized=sanitized,
                        branch_setups=record['branch_setups'],
                        target_scope_rejected=target_scope_rejected),
                        sort_keys=True) + '\n')
                    journal.flush()
                    for target_x in range(1 << n):
                        def on_branch(branch):
                            journal.write(json.dumps(dict(kind='branch',
                                n=n, m=m, ell=ell, seed=seed,
                                sanitized=sanitized, target_x=target_x,
                                **branch), sort_keys=True) + '\n')
                            journal.flush()
                        try:
                            result = context.run(target_x, exhaustive=True,
                                                 on_branch=on_branch)
                            expected_status = ('satisfiable' if target_x in
                                union_set else 'unsatisfiable')
                            matches = []
                            for index, branch in enumerate(result['branches']):
                                expected_branch = ('satisfiable' if target_x in
                                    sets[index] else 'unsatisfiable')
                                match = (branch['status'] == expected_branch and
                                    ((branch['assignment'] is not None and
                                      branch['equation_verified'] is True and
                                      branch['point_verified'] is True and
                                      (branch['assignment'] & context.branch_mask)
                                      == branch['fixed_one'])
                                     if expected_branch == 'satisfiable' else
                                     branch['assignment'] is None))
                                matches.append(match)
                            valid = (len(matches) == len(sets) and all(matches)
                                     and result['status'] == expected_status and
                                     ((result['assignment'] is not None)
                                      if expected_status == 'satisfiable' else
                                      result['assignment'] is None))
                            row = dict(target_x=target_x,
                                expected_status=expected_status,
                                result=result, branch_matches=matches,
                                match=valid)
                        except Exception as error:
                            row = dict(target_x=target_x, match=False,
                                       error=repr(error), execution='failure')
                        record['rows'].append(row)
                        journal.write(json.dumps(dict(kind='target',
                            n=n, m=m, ell=ell, seed=seed,
                            sanitized=sanitized, **row), sort_keys=True) + '\n')
                        journal.flush()
                    record['status'] = ('PASS' if union_matches and
                        target_scope_rejected and
                        len(record['rows']) == 1 << n and
                        all(row['match'] for row in record['rows']) else 'FAIL')
                finally:
                    context.close()
                save(report_path, report)
                print('F6_CUTSET_CASE', m, ell,
                      'ubsan' if sanitized else 'optimized',
                      record['status'], len(record['branch_choices']),
                      len(record['union_reachable_x']), flush=True)
    controls = report['controls']
    report['target_records'] = sum(len(case['rows']) for case in report['cases'])
    report['branch_records'] = sum(len(row.get('result', {}).get('branches', []))
                                   for case in report['cases']
                                   for row in case['rows'])
    report['status'] = ('PASS' if
        all(row['status'] == 'PASS' for row in controls['conditioning']) and
        controls['restoration']['match'] and controls['abi']['match'] and
        len(report['cases']) == 4 and
        report['target_records'] == 2048 and
        report['branch_records'] == 6144 and
        all(case['status'] == 'PASS' for case in report['cases'])
        else 'FAIL')
    save(report_path, report)
    print('F6_CUTSET_RESULT', report['status'], len(report['cases']),
          sum(len(case['rows']) for case in report['cases']),
          sha(report_path.read_bytes()), flush=True)
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
