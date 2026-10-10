"""Source-bound exactness and complete-query timing for cutset bitplanes."""
import argparse
from collections import Counter
import ctypes as C
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
PRIOR = HERE.parent / 'groebner-f6-replay-plan-20261009' / 'validate.py'
spec = importlib.util.spec_from_file_location('replay_validation', PRIOR)
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sys.path.insert(0, str(HERE))
from cutset_bitplane_query import BitplaneContext, CutsetBitplaneResult  # noqa: E402
from message_query import U64, pack  # noqa: E402

CASES = (4, 5)
TARGETS = 512
REPETITIONS = 3
MAX_BAG = 24
MAX_STATES = 200_000_000
ARMS = ('message', 'bitplane')
PREDECESSOR_REPORT_SHA = '19cfbaa26721bfdd90d7e810356365b88699e62a8343ffb4735d10e7726cd8b0'
PREDECESSOR_SOURCE = '2b377f31d117cd2f6c1b96d570b0720c7ebb5757'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_receipt(runtime_root):
    commit, sources, grouped, comparator = prior.source_receipt(runtime_root)
    own = [*HERE.glob('*.py'), *HERE.glob('*.cpp'), HERE / 'PROTOCOL.md',
           ROOT / '.github/workflows/groebner-f6-cutset-bitplane.yml']
    for path in own:
        name = str(path.relative_to(ROOT))
        actual = path.read_bytes()
        expected = subprocess.check_output(['git', 'show', 'HEAD:' + name],
                                           cwd=ROOT)
        if actual != expected:
            raise AssertionError('source differs from committed head: ' + name)
        sources[name] = sha(actual)
    predecessor = HERE.parent / 'groebner-f6-replay-plan-20261009' / \
        'evidence/report.json.gz'
    if sha(predecessor.read_bytes()) != PREDECESSOR_REPORT_SHA:
        raise AssertionError('predecessor report digest changed')
    archived = json.loads(gzip.decompress(predecessor.read_bytes()))
    if (archived['status'] != 'PASS' or
            archived['source_commit'] != PREDECESSOR_SOURCE):
        raise AssertionError('predecessor source/report does not match')
    build = json.loads((HERE / 'build/receipt.json').read_text())
    if build['source_commit'] != commit:
        raise AssertionError('bitplane build commit differs')
    for name, digest in build['sources'].items():
        if sources.get(name) != digest:
            raise AssertionError('bitplane build source differs: ' + name)
    for name, digest in build['binaries'].items():
        if sha((HERE / 'build' / name).read_bytes()) != digest:
            raise AssertionError('bitplane build binary differs: ' + name)
    return commit, sources, grouped, build, comparator, archived


def save(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def write(journal, value):
    journal.write(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    journal.flush()


def truth(row, assignment):
    return sum((assignment & term) == term for term in row) & 1


def affine_rows(blocks, target_x, equations):
    zero = blocks[:equations]
    out = [set(row) for row in zero]
    for bit in range(equations):
        if not (target_x >> bit) & 1:
            continue
        for row in range(equations):
            out[row].symmetric_difference_update(zero[row])
            out[row].symmetric_difference_update(
                blocks[(bit + 1) * equations + row])
    return [sorted(row) for row in out]


def arbitrary_controls(context, rng, journal):
    """Check the grouped static message and affine plane algebra on six bits."""
    lib = context.lib
    failures = []
    cases = 0
    for trial in range(80):
        static = [sorted(set(rng.randrange(64)
                             for _ in range(rng.randrange(1, 8))))]
        blocks = [sorted(set(rng.randrange(64)
                              for _ in range(rng.randrange(1, 8))))
                  for _ in range(6)]
        static_offsets, static_terms, static_count = pack(static)
        template_offsets, template_terms, template_count = pack(blocks)
        result = CutsetBitplaneResult()
        handle = lib.cutset_bitplane_create(6, 1, static_count,
            static_offsets, static_terms, 1, 1, 63, 6, 200_000,
            2, 2, template_count, template_offsets, template_terms,
            C.byref(result))
        if not handle or result.message.result.status != 1:
            raise AssertionError('arbitrary bitplane setup rejected')
        try:
            for target_x in range(4):
                dynamic = affine_rows(blocks, target_x, 2)
                expected = any(all(truth(row, assignment) == 0
                                   for row in static + dynamic)
                               for assignment in range(64))
                output = CutsetBitplaneResult()
                code = lib.cutset_bitplane_run(
                    handle, target_x, 200_000, C.byref(output))
                actual = code == 1
                witness = output.message.result.assignment if actual else None
                match = (code in (1, 2) and actual == expected and
                         code == output.message.result.status and
                         (witness is None or all(
                             truth(row, witness) == 0
                             for row in static + dynamic)))
                row = dict(kind='arbitrary', trial=trial,
                    target_x=target_x, expected=expected, actual=actual,
                    witness=witness, match=bool(match))
                write(journal, row)
                cases += 1
                if not match:
                    failures.append(row)
        finally:
            lib.cutset_bitplane_destroy(handle)
    return dict(cases=cases, failures=failures, status='PASS' if not failures else 'FAIL')


def applicability_controls(context, journal):
    lib = context.lib
    records = []
    for label, boundary, template in (
            ('boundary-17', (1 << 17) - 1, [[0], [0]]),
            ('template-outside-boundary', (1 << 16) - 1,
             [[1 << 16], [0]])):
        static_offsets, static_terms, static_count = pack([[1]])
        template_offsets, template_terms, template_count = pack(template)
        result = CutsetBitplaneResult()
        handle = lib.cutset_bitplane_create(17, 1, static_count,
            static_offsets, static_terms, 1, 1, boundary, 24, 200_000,
            1, 1, template_count, template_offsets, template_terms,
            C.byref(result))
        if handle:
            lib.cutset_bitplane_destroy(handle)
        row = dict(kind='applicability', label=label,
            status=result.message.result.status,
            match=not handle and result.message.result.status == 5)
        write(journal, row)
        records.append(row)
    return dict(cases=len(records), records=records,
                status='PASS' if all(row['match'] for row in records)
                else 'FAIL')


def run_query(context, old_replay, journal, *, phase, m, sanitized,
              target_x, arm, reference, sets, repetition=None):
    branch_count = 0
    try:
        result = context.run(target_x, arm, exhaustive=True)
        match, branch_matches = prior.previous.check_result(
            context, result, target_x, reference, sets)
        replay_matches = []
        for branch in result['branches']:
            branch_count += 1
            independent = (old_replay(context.curve, branch['assignment'],
                m, 7, target_x) if branch['assignment'] is not None else None)
            replay_match = (independent == branch['point_verified'] and
                (independent is True if branch['assignment'] is not None
                 else independent is None))
            replay_matches.append(replay_match)
            write(journal, dict(kind='branch', phase=phase, m=m,
                sanitized=sanitized, target_x=target_x, arm=arm,
                repetition=repetition,
                independent_point_verified=independent,
                replay_match=replay_match, **branch))
        match = bool(match and all(replay_matches))
        row = dict(kind='query', phase=phase, m=m,
            sanitized=sanitized, target_x=target_x, arm=arm,
            repetition=repetition, result=result,
            branch_matches=branch_matches,
            replay_matches=replay_matches, match=match)
    except Exception as error:
        row = dict(kind='query', phase=phase, m=m,
            sanitized=sanitized, target_x=target_x, arm=arm,
            repetition=repetition, match=False,
            error=repr(error), execution='failure')
    write(journal, row)
    return row, branch_count


def paired_summary(rows):
    by_target = {target_x: {} for target_x in range(TARGETS)}
    for row in rows:
        if row['match'] and 'result' in row:
            by_target[row['target_x']][row['repetition'],
                                        row['arm']] = row['result']
    complete = [(target_x, entries) for target_x, entries in by_target.items()
                if all((rep, arm) in entries for rep in range(REPETITIONS)
                       for arm in ARMS)]
    result = dict(paired_targets=len(complete),
                  paired_queries=2 * REPETITIONS * len(complete),
                  ratio=None, interval_95=None, medians_ms=None)
    if len(complete) != TARGETS:
        return result
    logs = [statistics.mean(math.log(
        entries[rep, 'message']['online_ns'] /
        entries[rep, 'bitplane']['online_ns'])
        for rep in range(REPETITIONS)) for _, entries in complete]
    generator = random.Random(20261010)
    bootstrap = sorted(math.exp(statistics.mean(generator.choices(
        logs, k=TARGETS))) for _ in range(2000))
    medians = {}
    for arm in ARMS:
        values = [entries[rep, arm] for _, entries in complete
                  for rep in range(REPETITIONS)]
        medians[arm] = {name: statistics.median(v[name] for v in values) / 1e6
                        for name in ('online_ns', 'native_ns', 'coefficient_ns',
                                     'check_ns', 'point_replay_ns',
                                     'other_check_ns')}
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
    commit, sources, grouped, build, comparator, archived = \
        source_receipt(runtime_root)
    runtime = prior.load_runtime(runtime_root)
    old_replay = runtime['point_replay']
    args.output.mkdir(parents=True, exist_ok=False)
    report_path = args.output / 'report.json.gz'
    report = dict(schema='f6-cutset-bitplane-exact/1', status='RUNNING',
        source_commit=commit, source_sha256=sources,
        grouped_build=grouped, bitplane_build=build,
        predecessor_report_sha256=PREDECESSOR_REPORT_SHA,
        max_bag=MAX_BAG, max_states=MAX_STATES,
        controls=[], primary=[], timing=[],
        timing_eligible=False, qualified_speedup=None)
    save(report_path, report)
    references = {}
    with (args.output / 'journal.jsonl').open('x') as journal:
        for m in CASES:
            case = runtime['fixture'](9, m, 7, 1)
            sets = prior.reference_sets(comparator, m)
            references[m] = {}
            for sanitized in (False, True):
                record = dict(m=m, sanitized=sanitized,
                    nvars=case['nvars'], queries=0, branch_queries=0,
                    pair_matches=0, statuses=Counter(), failures=[],
                    status='RUNNING')
                report['primary'].append(record)
                save(report_path, report)
                try:
                    context = BitplaneContext(case, runtime,
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
                    record['message_setup_ns'] = context.message_setup_ns
                    record['bitplane_setup_ns'] = context.bitplane_setup_ns
                    record['point_plan_setup_ns'] = context.point_plan.setup_ns
                    record['bitplane_setup'] = context.bitplane_setup
                    record['grouped_branch_setups'] = [x['layout'].setup
                                                       for x in context.branches]
                    write(journal, dict(kind='setup', phase='primary',
                        m=m, sanitized=sanitized,
                        setup_ns=record['setup_ns'],
                        message_setup_ns=record['message_setup_ns'],
                        bitplane_setup_ns=record['bitplane_setup_ns'],
                        point_plan_setup_ns=record['point_plan_setup_ns'],
                        bitplane_setup=record['bitplane_setup'],
                        grouped_branch_setups=record['grouped_branch_setups']))
                    if not sanitized:
                        control = arbitrary_controls(context,
                            random.Random(20261010 + m), journal)
                        report['controls'].append(dict(m=m, **control))
                        cap = applicability_controls(context, journal)
                        report['controls'].append(dict(m=m,
                            control='applicability', **cap))
                    for target_x in range(TARGETS):
                        try:
                            reference = prior.previous.direct_rows(context, target_x)
                            if not sanitized:
                                references[m][target_x] = reference
                            if not prior.previous.packed_matches(
                                    context, target_x, reference):
                                raise AssertionError('fresh packed ANF mismatch')
                        except Exception as error:
                            reference = []
                            record['failures'].append(dict(
                                phase='reference-anf', target_x=target_x,
                                error=repr(error)))
                        order = ARMS if target_x % 2 == 0 else ARMS[::-1]
                        paired = {}
                        for arm in order:
                            row, branches = run_query(context, old_replay,
                                journal, phase='primary', m=m,
                                sanitized=sanitized, target_x=target_x,
                                arm=arm, reference=reference, sets=sets)
                            paired[arm] = row
                            record['queries'] += 1
                            record['branch_queries'] += branches
                            if row['match']:
                                record['statuses'][row['result']['status']] += 1
                            else:
                                record['failures'].append(dict(
                                    target_x=target_x, arm=arm,
                                    error=row.get('error', 'verification mismatch')))
                        pair_match = (all(row['match'] for row in paired.values())
                            and [b['status'] for b in
                                 paired['message']['result']['branches']] ==
                                [b['status'] for b in
                                 paired['bitplane']['result']['branches']])
                        record['pair_matches'] += pair_match
                        write(journal, dict(kind='pair', phase='primary',
                            m=m, sanitized=sanitized,
                            target_x=target_x, match=bool(pair_match)))
                        if not pair_match:
                            record['failures'].append(dict(
                                target_x=target_x, error='branch status mismatch'))
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
                print('F6_BITPLANE_PRIMARY', m,
                    'ubsan' if sanitized else 'optimized',
                    record['status'], record['queries'],
                    record['branch_queries'], flush=True)

        for m in CASES:
            case = runtime['fixture'](9, m, 7, 1)
            sets = prior.reference_sets(comparator, m)
            record = dict(m=m, repetitions=REPETITIONS,
                warmups=0, queries=0, branch_queries=0,
                failures=[], status='RUNNING', summary=None)
            report['timing'].append(record)
            save(report_path, report)
            if len(references[m]) != TARGETS:
                record.update(status='FAIL',
                    setup_error='missing independent target ANF references')
                save(report_path, report)
                continue
            try:
                context = BitplaneContext(case, runtime,
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
                record['message_setup_ns'] = context.message_setup_ns
                record['bitplane_setup_ns'] = context.bitplane_setup_ns
                record['bitplane_setup'] = context.bitplane_setup
                for target_x in (0, 1, 161):
                    for arm in ARMS:
                        row, _ = run_query(context, old_replay,
                            journal, phase='warmup', m=m,
                            sanitized=False, target_x=target_x,
                            arm=arm, reference=references[m][target_x],
                            sets=sets)
                        record['warmups'] += 1
                        if not row['match']:
                            record['failures'].append(dict(
                                phase='warmup', target_x=target_x, arm=arm,
                                error=row.get('error', 'verification mismatch')))
                for repetition in range(REPETITIONS):
                    for target_x in range(TARGETS):
                        order = ARMS if (target_x + repetition) % 2 == 0 \
                            else ARMS[::-1]
                        paired = {}
                        for arm in order:
                            row, branches = run_query(context, old_replay,
                                journal, phase='timing', m=m,
                                sanitized=False, target_x=target_x,
                                arm=arm, reference=references[m][target_x],
                                sets=sets, repetition=repetition)
                            paired[arm] = row
                            rows.append(row)
                            record['queries'] += 1
                            record['branch_queries'] += branches
                            if not row['match']:
                                record['failures'].append(dict(
                                    phase='timing', repetition=repetition,
                                    target_x=target_x, arm=arm,
                                    error=row.get('error', 'verification mismatch')))
                        pair_match = (all(row['match'] for row in paired.values())
                            and [b['status'] for b in
                                 paired['message']['result']['branches']] ==
                                [b['status'] for b in
                                 paired['bitplane']['result']['branches']])
                        if not pair_match:
                            record['failures'].append(dict(
                                phase='timing', repetition=repetition,
                                target_x=target_x,
                                error='branch status mismatch'))
                record['summary'] = paired_summary(rows)
                record['status'] = ('PASS' if
                    record['warmups'] == 6 and
                    record['queries'] == 2 * REPETITIONS * TARGETS and
                    record['branch_queries'] == 2 * REPETITIONS * TARGETS *
                        2 ** (m - 3) and
                    record['summary']['paired_targets'] == TARGETS and
                    not record['failures'] else 'FAIL')
            finally:
                context.close()
            save(report_path, report)
            print('F6_BITPLANE_TIMING', m, record['status'],
                  record['queries'], record['branch_queries'],
                  record['summary']['ratio'], flush=True)
    report['primary_queries'] = sum(row['queries'] for row in report['primary'])
    report['primary_branches'] = sum(row['branch_queries']
                                     for row in report['primary'])
    report['timing_queries'] = sum(row['queries'] for row in report['timing'])
    report['timing_branches'] = sum(row['branch_queries']
                                    for row in report['timing'])
    report['status'] = ('PASS' if
        report['primary_queries'] == 4096 and
        report['primary_branches'] == 12288 and
        report['timing_queries'] == 6144 and
        report['timing_branches'] == 18432 and
        all(row['status'] == 'PASS' for row in report['controls'] +
            report['primary'] + report['timing']) else 'FAIL')
    raw = (args.output / 'journal.jsonl').read_bytes()
    report['journal_sha256'] = sha(raw)
    (args.output / 'journal.jsonl.gz').write_bytes(
        gzip.compress(raw, compresslevel=9, mtime=0))
    (args.output / 'journal.jsonl').unlink()
    save(report_path, report)
    print('F6_CUTSET_BITPLANE', report['status'],
          report['primary_queries'], report['timing_queries'], flush=True)
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
