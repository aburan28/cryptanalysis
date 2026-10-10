"""Exact old-versus-planned point replay and complete-query panel."""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREVIOUS = HERE.parent / 'groebner-f6-cutset-packed-20261009' / 'validate.py'
spec = importlib.util.spec_from_file_location('packed_cutset_validation', PREVIOUS)
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
load_runtime = previous.load_runtime

CASES = (4, 5)
TARGETS = 512
REPETITIONS = 3
MAX_BAG = 24
MAX_STATES = 200_000_000
ARCHIVE_SHA = 'fd92b8ced02d60e3b3166f76f47a0759be1da148c192d22974bba2f823169f29'
ARCHIVE_COMMIT = '9883bbea14c9ff82489f5858ece46dc3828e82c3'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_receipt(runtime_root):
    commit, sources, build = previous.source_receipt(runtime_root)
    own = [*HERE.glob('*.py'), HERE / 'PROTOCOL.md',
           ROOT / '.github/workflows/groebner-f6-replay-plan.yml']
    for path in own:
        name = str(path.relative_to(ROOT))
        actual = path.read_bytes()
        expected = subprocess.check_output(['git', 'show', 'HEAD:' + name],
                                           cwd=ROOT)
        if actual != expected:
            raise AssertionError('source differs from committed head: ' + name)
        sources[name] = sha(actual)
    archive = HERE.parent / 'groebner-f6-cutset-packed-20261009' / \
        'evidence/complete/report.json.gz'
    if sha(archive.read_bytes()) != ARCHIVE_SHA:
        raise AssertionError('predecessor exact report changed')
    reference = json.loads(gzip.decompress(archive.read_bytes()))
    if (reference['status'] != 'PASS' or
            reference['source_commit'] != ARCHIVE_COMMIT):
        raise AssertionError('predecessor exact report is not the frozen PASS')
    return commit, sources, build, reference


def save(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def write(journal, value):
    journal.write(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    journal.flush()


def reference_sets(report, m):
    cases = [case for case in report['primary']
             if case['m'] == m and case['sanitized'] is False]
    if len(cases) != 1 or cases[0]['status'] != 'PASS':
        raise AssertionError('missing predecessor curve comparator')
    case = cases[0]
    if not case['union_matches'] or len(case['branch_reachable_x']) != 2 ** (m - 3):
        raise AssertionError('invalid predecessor branch target sets')
    return [set(xs) for xs in case['branch_reachable_x']]


def control_panel(context, original_replay, m, journal):
    generator = random.Random(20261009 + m)
    rows = []
    for trial in range(1024):
        assignment = sum(generator.randrange(128) << (j * 7)
                         for j in range(m))
        target_x = generator.randrange(512)
        reference = original_replay(context.curve, assignment, m, 7, target_x)
        planned = context.point_plan.verify(assignment, target_x)
        row = dict(kind='control', m=m, trial=trial,
            assignment=assignment, target_x=target_x,
            reference=reference, planned=planned,
            match=reference == planned)
        write(journal, row)
        rows.append(row)
    zero = 0
    unliftable = next(x for x, points in enumerate(context.point_plan.choices)
                      if not points)
    special = [('infinity-prefix', zero, 0),
               ('unliftable-first', unliftable, 0)]
    for label, assignment, target_x in special:
        reference = original_replay(context.curve, assignment, m, 7, target_x)
        planned = context.point_plan.verify(assignment, target_x)
        row = dict(kind='control', m=m, trial=label,
            assignment=assignment, target_x=target_x,
            reference=reference, planned=planned,
            match=reference == planned and reference is False)
        write(journal, row)
        rows.append(row)
    return dict(cases=len(rows), matched=sum(row['match'] for row in rows),
                failures=[row for row in rows if not row['match']],
                unliftable_x=unliftable)


def run_query(context, original_replay, journal, *, phase, m, sanitized,
              target_x, replay_arm, reference, sets, repetition=None):
    branch_count = 0
    try:
        result = context.run(target_x, replay_arm, exhaustive=True)
        match, branch_matches = previous.check_result(
            context, result, target_x, reference, sets)
        if (result['point_replay_ns'] < 0 or
                result['other_check_ns'] < 0 or
                result['point_replay_ns'] + result['other_check_ns'] !=
                    result['check_ns']):
            match = False
        replay_matches = []
        for branch in result['branches']:
            branch_count += 1
            independent = (original_replay(context.curve,
                branch['assignment'], m, 7, target_x)
                if branch['assignment'] is not None else None)
            replay_match = (independent == branch['point_verified'] and
                (independent is True if branch['assignment'] is not None
                 else independent is None))
            replay_matches.append(replay_match)
            write(journal, dict(kind='branch', phase=phase, m=m,
                sanitized=sanitized, target_x=target_x,
                replay_arm=replay_arm, repetition=repetition,
                independent_point_verified=independent,
                replay_match=replay_match, **branch))
        match = bool(match and all(replay_matches))
        row = dict(kind='query', phase=phase, m=m,
            sanitized=sanitized, target_x=target_x,
            replay_arm=replay_arm, repetition=repetition,
            result=result, branch_matches=branch_matches,
            replay_matches=replay_matches, match=match)
    except Exception as error:
        row = dict(kind='query', phase=phase, m=m,
            sanitized=sanitized, target_x=target_x,
            replay_arm=replay_arm, repetition=repetition,
            match=False, error=repr(error), execution='failure')
    write(journal, row)
    return row, branch_count


def paired_summary(rows):
    by_target = {target_x: {} for target_x in range(TARGETS)}
    for row in rows:
        if row['match'] and 'result' in row:
            by_target[row['target_x']][row['repetition'],
                                        row['replay_arm']] = row['result']
    complete = []
    for target_x, entries in by_target.items():
        if all((rep, arm) in entries for rep in range(REPETITIONS)
               for arm in ('reference', 'planned')):
            complete.append((target_x, entries))
    result = dict(paired_targets=len(complete),
                  paired_queries=2 * REPETITIONS * len(complete),
                  ratio=None, interval_95=None, medians_ms=None)
    if len(complete) != TARGETS:
        return result
    logs = [statistics.mean(math.log(
        entries[rep, 'reference']['online_ns'] /
        entries[rep, 'planned']['online_ns'])
        for rep in range(REPETITIONS)) for _, entries in complete]
    generator = random.Random(20261009)
    bootstrap = sorted(math.exp(statistics.mean(generator.choices(
        logs, k=TARGETS))) for _ in range(2000))
    medians = {}
    for arm in ('reference', 'planned'):
        values = [entries[rep, arm] for _, entries in complete
                  for rep in range(REPETITIONS)]
        medians[arm] = {name: statistics.median(v[name] for v in values) / 1e6
                        for name in ('online_ns', 'native_ns',
                                     'coefficient_ns', 'check_ns',
                                     'point_replay_ns', 'other_check_ns')}
    result.update(ratio=math.exp(statistics.mean(logs)),
                  interval_95=[bootstrap[49], bootstrap[1949]],
                  medians_ms=medians)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    args = parser.parse_args()
    runtime_root = args.runtime_root.resolve()
    commit, sources, build, archived = source_receipt(runtime_root)
    runtime = load_runtime(runtime_root)
    original_replay = runtime['point_replay']
    sys.path.insert(0, str(HERE))
    from replay_plan import ReplayContext

    args.output.mkdir(parents=True, exist_ok=False)
    report_path = args.output / 'report.json.gz'
    report = dict(schema='f6-point-replay-plan/1', status='RUNNING',
        source_commit=commit, source_sha256=sources, grouped_build=build,
        predecessor_report_sha256=ARCHIVE_SHA,
        max_bag=MAX_BAG, max_states=MAX_STATES,
        controls=[], primary=[], timing=[],
        timing_eligible=False, qualified_speedup=None)
    save(report_path, report)
    references = {}
    with (args.output / 'journal.jsonl').open('x') as journal:
        for m in CASES:
            case = runtime['fixture'](9, m, 7, 1)
            sets = reference_sets(archived, m)
            references[m] = {}
            for sanitized in (False, True):
                record = dict(m=m, sanitized=sanitized,
                    nvars=case['nvars'], queries=0, branch_queries=0,
                    pair_matches=0, statuses=Counter(), failures=[],
                    status='RUNNING')
                report['primary'].append(record)
                save(report_path, report)
                try:
                    context = ReplayContext(case, runtime,
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
                    record['plan_setup_ns'] = context.point_plan.setup_ns
                    record['liftable_x'] = context.point_plan.liftable_x
                    record['pair_slots'] = context.point_plan.pair_slots
                    record['pair_states'] = context.point_plan.pair_states
                    record['branch_setups'] = [x['layout'].setup
                                               for x in context.branches]
                    write(journal, dict(kind='setup', phase='primary',
                        m=m, sanitized=sanitized,
                        setup_ns=record['setup_ns'],
                        plan_setup_ns=record['plan_setup_ns'],
                        liftable_x=record['liftable_x'],
                        pair_slots=record['pair_slots'],
                        pair_states=record['pair_states'],
                        branch_setups=record['branch_setups']))
                    if not sanitized:
                        controls = control_panel(context,
                            original_replay, m, journal)
                        report['controls'].append(dict(m=m, **controls))
                    for target_x in range(TARGETS):
                        try:
                            reference = previous.direct_rows(context, target_x)
                            if not sanitized:
                                references[m][target_x] = reference
                        except Exception as error:
                            reference = []
                            record['failures'].append(dict(
                                phase='reference-anf', target_x=target_x,
                                error=repr(error)))
                        order = ('reference', 'planned') if target_x % 2 == 0 \
                            else ('planned', 'reference')
                        paired = {}
                        for replay_arm in order:
                            row, branches = run_query(context,
                                original_replay, journal, phase='primary',
                                m=m, sanitized=sanitized,
                                target_x=target_x,
                                replay_arm=replay_arm,
                                reference=reference, sets=sets)
                            paired[replay_arm] = row
                            record['queries'] += 1
                            record['branch_queries'] += branches
                            if row['match']:
                                record['statuses'][row['result']['status']] += 1
                            else:
                                record['failures'].append(dict(
                                    target_x=target_x, replay_arm=replay_arm,
                                    error=row.get('error', 'verification mismatch')))
                        pair_match = (all(row['match'] for row in paired.values())
                            and [(b['status'], b['assignment']) for b in
                                 paired['reference']['result']['branches']] ==
                                [(b['status'], b['assignment']) for b in
                                 paired['planned']['result']['branches']])
                        record['pair_matches'] += pair_match
                        write(journal, dict(kind='pair', phase='primary',
                            m=m, sanitized=sanitized,
                            target_x=target_x, match=bool(pair_match)))
                        if not pair_match:
                            record['failures'].append(dict(
                                target_x=target_x,
                                error='native branch result mismatch'))
                    record['statuses'] = dict(record['statuses'])
                    record['status'] = ('PASS' if
                        record['queries'] == 2 * TARGETS and
                        record['branch_queries'] == 2 * TARGETS *
                            2 ** (m - 3) and
                        record['pair_matches'] == TARGETS and
                        not record['failures'] else 'FAIL')
                finally:
                    context.close()
                save(report_path, report)
                print('F6_REPLAY_PRIMARY', m,
                    'ubsan' if sanitized else 'optimized',
                    record['status'], record['queries'],
                    record['branch_queries'], flush=True)

        for m in CASES:
            case = runtime['fixture'](9, m, 7, 1)
            sets = reference_sets(archived, m)
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
                context = ReplayContext(case, runtime,
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
                record['plan_setup_ns'] = context.point_plan.setup_ns
                for target_x in (0, 1, 161):
                    for replay_arm in ('reference', 'planned'):
                        row, _ = run_query(context, original_replay,
                            journal, phase='warmup', m=m,
                            sanitized=False, target_x=target_x,
                            replay_arm=replay_arm,
                            reference=references[m][target_x], sets=sets)
                        record['warmups'] += 1
                        if not row['match']:
                            record['failures'].append(dict(
                                phase='warmup', target_x=target_x,
                                replay_arm=replay_arm,
                                error=row.get('error', 'verification mismatch')))
                for repetition in range(REPETITIONS):
                    for target_x in range(TARGETS):
                        order = ('reference', 'planned') if (
                            target_x + repetition) % 2 == 0 else (
                            'planned', 'reference')
                        paired = {}
                        for replay_arm in order:
                            row, branches = run_query(context,
                                original_replay, journal, phase='timing',
                                m=m, sanitized=False,
                                target_x=target_x,
                                replay_arm=replay_arm,
                                reference=references[m][target_x],
                                sets=sets, repetition=repetition)
                            paired[replay_arm] = row
                            rows.append(row)
                            record['queries'] += 1
                            record['branch_queries'] += branches
                            if not row['match']:
                                record['failures'].append(dict(
                                    phase='timing', target_x=target_x,
                                    repetition=repetition,
                                    replay_arm=replay_arm,
                                    error=row.get('error', 'verification mismatch')))
                        pair_match = (all(row['match'] for row in paired.values())
                            and [(b['status'], b['assignment']) for b in
                                 paired['reference']['result']['branches']] ==
                                [(b['status'], b['assignment']) for b in
                                 paired['planned']['result']['branches']])
                        write(journal, dict(kind='pair', phase='timing',
                            m=m, target_x=target_x,
                            repetition=repetition,
                            match=bool(pair_match)))
                        if not pair_match:
                            record['failures'].append(dict(
                                phase='timing', target_x=target_x,
                                repetition=repetition,
                                error='native branch result mismatch'))
                record['summary'] = paired_summary(rows)
                record['status'] = ('PASS' if
                    record['warmups'] == 6 and
                    record['queries'] == 2 * TARGETS * REPETITIONS and
                    record['branch_queries'] == 2 * TARGETS *
                        REPETITIONS * 2 ** (m - 3) and
                    record['summary']['paired_targets'] == TARGETS and
                    not record['failures'] else 'FAIL')
            finally:
                context.close()
            save(report_path, report)
            print('F6_REPLAY_TIMING', m, record['status'],
                  record['queries'], record['branch_queries'],
                  record['summary']['ratio'] if record['summary'] else None,
                  flush=True)

    report['primary_queries'] = sum(x['queries'] for x in report['primary'])
    report['primary_branches'] = sum(x['branch_queries'] for x in report['primary'])
    report['timing_queries'] = sum(x['queries'] for x in report['timing'])
    report['timing_branches'] = sum(x['branch_queries'] for x in report['timing'])
    report['journal_sha256'] = sha((args.output / 'journal.jsonl').read_bytes())
    report['status'] = ('PASS' if
        len(report['controls']) == 2 and
        all(x['cases'] == x['matched'] == 1026 for x in report['controls']) and
        len(report['primary']) == 4 and
        len(report['timing']) == 2 and
        report['primary_queries'] == 4096 and
        report['primary_branches'] == 12288 and
        report['timing_queries'] == 6144 and
        report['timing_branches'] == 18432 and
        all(x['status'] == 'PASS' for x in report['primary'] + report['timing'])
        else 'FAIL')
    save(report_path, report)
    print('F6_REPLAY_RESULT', report['status'],
          report['primary_queries'], report['timing_queries'],
          sha(report_path.read_bytes()), flush=True)
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
