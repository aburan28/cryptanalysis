"""Source-bound exact and paired complete-query replay for packed cutsets."""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREDECESSOR = HERE.parent / 'groebner-f6-cutset-20261009' / 'validate.py'
spec = importlib.util.spec_from_file_location('cutset_validation', PREDECESSOR)
cutset_validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cutset_validation)
sys.path.insert(0, str(HERE.parent / 'groebner-f6-wide-boundary-20261009'))
from wide_query import load_runtime  # noqa: E402

CASES = (4, 5)
TARGETS = 512
REPETITIONS = 3
MAX_BAG = 24
MAX_STATES = 200_000_000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_receipt(runtime_root):
    commit, sources, build = cutset_validation.source_receipt(runtime_root)
    own = [*HERE.glob('*.py'), HERE / 'PROTOCOL.md',
           ROOT / '.github/workflows/groebner-f6-cutset-packed.yml']
    for path in own:
        name = str(path.relative_to(ROOT))
        actual = path.read_bytes()
        expected = subprocess.check_output(['git', 'show', 'HEAD:' + name],
                                           cwd=ROOT)
        if actual != expected:
            raise AssertionError('source differs from committed head: ' + name)
        sources[name] = sha(actual)
    return commit, sources, build


def save(path, value):
    data = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    path.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))


def write(journal, value):
    journal.write(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    journal.flush()


def direct_rows(context, target_x):
    dynamic = context.runtime['equations'](
        context.field, context.runtime['s3'](
            context.field, context.case['curve_b'], context.auxiliary,
            context.summand, {0: target_x}))
    return [context.runtime['canonical'](row) for row in dynamic]


def packed_matches(context, target_x, reference):
    rows, _, offsets, terms = context._target_rows(target_x, 'packed')
    actual = [tuple(terms[offsets[i]:offsets[i + 1]])
              for i in range(rows)]
    return actual == reference


def independent_sets(case, runtime):
    indices = tuple(range(2, case['m'] - 1))
    choices = [tuple(zip(indices, values))
               for values in itertools.product((0, 1), repeat=len(indices))]
    branch = []
    point_counts = []
    for choice in choices:
        abscissae, sizes = cutset_validation.restricted_curve_x(
            case, runtime, choice)
        branch.append(abscissae)
        point_counts.append(sizes)
    unrestricted, _ = cutset_validation.restricted_curve_x(case, runtime, ())
    return dict(choices=choices, branch=branch, point_counts=point_counts,
                unrestricted=unrestricted,
                union_matches=sorted(set().union(*(set(x) for x in branch)))
                == unrestricted)


def check_result(context, result, target_x, reference, sets):
    expected = 'satisfiable' if any(target_x in s for s in sets) else 'unsatisfiable'
    branches = result['branches']
    matches = []
    for index, branch in enumerate(branches):
        expected_branch = ('satisfiable' if target_x in sets[index]
                           else 'unsatisfiable')
        assignment = branch['assignment']
        correct = (branch['index'] == index and
                   branch['status'] == expected_branch)
        if expected_branch == 'satisfiable':
            correct &= (assignment is not None and
                branch['input_verified'] is True and
                branch['original_equation_verified'] is True and
                branch['equation_verified'] is True and
                branch['point_verified'] is True and
                (assignment & context.branch_mask) == branch['fixed_one'] and
                all(context.runtime['satisfies'](row, assignment)
                    for row in reference) and
                all(context.runtime['satisfies'](row, assignment)
                    for row in context.original_canonical))
        else:
            correct &= assignment is None
        matches.append(bool(correct))
    return (len(branches) == len(sets) and all(matches) and
            result['status'] == expected and
            (result['assignment'] is not None) == (expected == 'satisfiable') and
            sum(result[name] for name in ('coefficient_ns', 'native_ns',
                                           'check_ns')) == result['online_ns']), matches


def run_query(context, journal, *, phase, m, sanitized, target_x, arm,
              reference, sets, repetition=None):
    branch_count = 0
    try:
        result = context.run(target_x, arm, exhaustive=True)
        for branch in result['branches']:
            branch_count += 1
            write(journal, dict(kind='branch', phase=phase, m=m,
                sanitized=sanitized, target_x=target_x,
                arm=arm, repetition=repetition, **branch))
        match, branch_matches = check_result(
            context, result, target_x, reference, sets)
        row = dict(kind='query', phase=phase, m=m,
                   sanitized=sanitized, target_x=target_x,
                   arm=arm, repetition=repetition, result=result,
                   branch_matches=branch_matches, match=bool(match))
    except Exception as error:
        row = dict(kind='query', phase=phase, m=m,
                   sanitized=sanitized, target_x=target_x,
                   arm=arm, repetition=repetition, match=False,
                   error=repr(error), execution='failure')
    write(journal, row)
    return row, branch_count


def cluster_summary(rows):
    by_target = {target_x: {} for target_x in range(TARGETS)}
    for row in rows:
        if not row['match'] or 'result' not in row:
            continue
        by_target[row['target_x']][row['repetition'], row['arm']] = row['result']
    complete = []
    for target_x, entries in by_target.items():
        if all((rep, arm) in entries for rep in range(REPETITIONS)
               for arm in ('direct', 'packed')):
            complete.append((target_x, entries))
    output = dict(paired_targets=len(complete), paired_queries=2 *
                  REPETITIONS * len(complete), ratio=None,
                  interval_95=None, medians_ms=None)
    if len(complete) != TARGETS:
        return output
    logs = []
    for _, entries in complete:
        ratios = [entries[rep, 'direct']['online_ns'] /
                  entries[rep, 'packed']['online_ns']
                  for rep in range(REPETITIONS)]
        logs.append(statistics.mean(math.log(value) for value in ratios))
    ratio = math.exp(statistics.mean(logs))
    generator = random.Random(20261009)
    boot = sorted(math.exp(statistics.mean(generator.choices(
        logs, k=TARGETS))) for _ in range(2000))
    medians = {}
    for arm in ('direct', 'packed'):
        values = [entry[rep, arm] for _, entries in complete
                  for rep in range(REPETITIONS)]
        medians[arm] = {name: statistics.median(v[name] for v in values) / 1e6
                        for name in ('online_ns', 'coefficient_ns',
                                     'native_ns', 'check_ns')}
    output.update(ratio=ratio,
                  interval_95=[boot[49], boot[1949]],
                  medians_ms=medians)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    args = parser.parse_args()
    runtime_root = args.runtime_root.resolve()
    commit, sources, build = source_receipt(runtime_root)
    runtime = load_runtime(runtime_root)
    sys.path.insert(0, str(HERE))
    from packed_cutset_query import PackedCutsetContext

    args.output.mkdir(parents=True, exist_ok=False)
    report_path = args.output / 'report.json.gz'
    report = dict(schema='f6-cutset-packed-query/1', status='RUNNING',
        source_commit=commit, source_sha256=sources, grouped_build=build,
        max_bag=MAX_BAG, max_states=MAX_STATES, primary=[], timing=[],
        timing_eligible=False, qualified_speedup=None)
    save(report_path, report)
    curve_sets = {}
    references = {}
    with (args.output / 'journal.jsonl').open('x') as journal:
        for m in CASES:
            case = runtime['fixture'](9, m, 7, 1)
            comparator = independent_sets(case, runtime)
            curve_sets[m] = comparator
            sets = [set(x) for x in comparator['branch']]
            references[m] = {}
            for sanitized in (False, True):
                record = dict(m=m, sanitized=sanitized, nvars=case['nvars'],
                    branch_choices=comparator['choices'],
                    branch_reachable_x=comparator['branch'],
                    branch_point_counts=comparator['point_counts'],
                    unrestricted_reachable_x=comparator['unrestricted'],
                    union_matches=comparator['union_matches'],
                    queries=0, branch_queries=0, coefficient_matches=0,
                    statuses=Counter(), failures=[], status='RUNNING')
                report['primary'].append(record)
                save(report_path, report)
                try:
                    context = PackedCutsetContext(case, runtime,
                        max_bag=MAX_BAG, max_states=MAX_STATES,
                        sanitized=sanitized)
                except Exception as error:
                    record.update(status='FAIL', setup_error=repr(error))
                    write(journal, dict(kind='setup_failure', phase='primary',
                        m=m, sanitized=sanitized, error=repr(error)))
                    save(report_path, report)
                    continue
                try:
                    record['setup_ns'] = context.setup_ns
                    record['template_terms'] = len(context.template.universe)
                    record['branch_setups'] = [x['layout'].setup
                                               for x in context.branches]
                    write(journal, dict(kind='setup', phase='primary',
                        m=m, sanitized=sanitized,
                        branch_setups=record['branch_setups'],
                        template_terms=record['template_terms']))
                    for target_x in range(TARGETS):
                        try:
                            reference = direct_rows(context, target_x)
                            coefficient_match = packed_matches(
                                context, target_x, reference)
                            if not sanitized:
                                references[m][target_x] = reference
                        except Exception as error:
                            reference = []
                            coefficient_match = False
                            record['failures'].append(dict(
                                target_x=target_x, phase='coefficients',
                                error=repr(error)))
                        record['coefficient_matches'] += coefficient_match
                        write(journal, dict(kind='coefficient_audit', m=m,
                            sanitized=sanitized, target_x=target_x,
                            match=coefficient_match))
                        order = ('direct', 'packed') if target_x % 2 == 0 else (
                            'packed', 'direct')
                        for arm in order:
                            row, branches = run_query(context, journal,
                                phase='primary', m=m, sanitized=sanitized,
                                target_x=target_x, arm=arm,
                                reference=reference, sets=sets)
                            record['queries'] += 1
                            record['branch_queries'] += branches
                            if row['match']:
                                record['statuses'][row['result']['status']] += 1
                            else:
                                record['failures'].append(dict(
                                    target_x=target_x, arm=arm,
                                    error=row.get('error', 'verification mismatch')))
                    record['statuses'] = dict(record['statuses'])
                    record['status'] = ('PASS' if record['union_matches'] and
                        record['coefficient_matches'] == TARGETS and
                        record['queries'] == 2 * TARGETS and
                        record['branch_queries'] == 2 * TARGETS *
                            2 ** (m - 3) and
                        not record['failures'] else 'FAIL')
                finally:
                    context.close()
                save(report_path, report)
                print('F6_PACKED_PRIMARY', m,
                    'ubsan' if sanitized else 'optimized',
                    record['status'], record['queries'],
                    record['branch_queries'], flush=True)

        for m in CASES:
            case = runtime['fixture'](9, m, 7, 1)
            sets = [set(x) for x in curve_sets[m]['branch']]
            record = dict(m=m, repetitions=REPETITIONS,
                          warmups=0, queries=0, branch_queries=0,
                          failures=[], status='RUNNING', summary=None)
            report['timing'].append(record)
            save(report_path, report)
            if len(references[m]) != TARGETS:
                record.update(status='FAIL',
                    setup_error='missing independent target ANF references')
                write(journal, dict(kind='setup_failure', phase='timing',
                    m=m, error=record['setup_error']))
                save(report_path, report)
                continue
            try:
                context = PackedCutsetContext(case, runtime,
                    max_bag=MAX_BAG, max_states=MAX_STATES)
            except Exception as error:
                record.update(status='FAIL', setup_error=repr(error))
                write(journal, dict(kind='setup_failure', phase='timing',
                    m=m, error=repr(error)))
                save(report_path, report)
                continue
            rows = []
            try:
                record['setup_ns'] = context.setup_ns
                for target_x in (0, 1, 161):
                    for arm in ('direct', 'packed'):
                        row, _ = run_query(context, journal,
                            phase='warmup', m=m, sanitized=False,
                            target_x=target_x, arm=arm,
                            reference=references[m][target_x], sets=sets)
                        record['warmups'] += 1
                        if not row['match']:
                            record['failures'].append(dict(
                                phase='warmup', target_x=target_x, arm=arm,
                                error=row.get('error', 'verification mismatch')))
                for repetition in range(REPETITIONS):
                    for target_x in range(TARGETS):
                        order = ('direct', 'packed') if (
                            target_x + repetition) % 2 == 0 else (
                            'packed', 'direct')
                        for arm in order:
                            row, branches = run_query(context, journal,
                                phase='timing', m=m, sanitized=False,
                                target_x=target_x, arm=arm,
                                reference=references[m][target_x],
                                sets=sets, repetition=repetition)
                            rows.append(row)
                            record['queries'] += 1
                            record['branch_queries'] += branches
                            if not row['match']:
                                record['failures'].append(dict(
                                    phase='timing', target_x=target_x,
                                    repetition=repetition, arm=arm,
                                    error=row.get('error', 'verification mismatch')))
                record['summary'] = cluster_summary(rows)
                record['status'] = ('PASS' if record['warmups'] == 6 and
                    record['queries'] == 2 * TARGETS * REPETITIONS and
                    record['branch_queries'] == 2 * TARGETS *
                        REPETITIONS * 2 ** (m - 3) and
                    record['summary']['paired_targets'] == TARGETS and
                    not record['failures'] else 'FAIL')
            finally:
                context.close()
            save(report_path, report)
            print('F6_PACKED_TIMING', m, record['status'],
                  record['queries'], record['branch_queries'],
                  record['summary']['ratio'] if record['summary'] else None,
                  flush=True)

    report['primary_queries'] = sum(x['queries'] for x in report['primary'])
    report['primary_branches'] = sum(x['branch_queries'] for x in report['primary'])
    report['timing_queries'] = sum(x['queries'] for x in report['timing'])
    report['timing_branches'] = sum(x['branch_queries'] for x in report['timing'])
    report['journal_sha256'] = sha((args.output / 'journal.jsonl').read_bytes())
    report['status'] = ('PASS' if len(report['primary']) == 4 and
        len(report['timing']) == 2 and
        report['primary_queries'] == 4096 and
        report['primary_branches'] == 12288 and
        report['timing_queries'] == 6144 and
        report['timing_branches'] == 18432 and
        all(x['status'] == 'PASS' for x in report['primary'] + report['timing'])
        else 'FAIL')
    save(report_path, report)
    print('F6_PACKED_RESULT', report['status'],
          report['primary_queries'], report['timing_queries'],
          sha(report_path.read_bytes()), flush=True)
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
