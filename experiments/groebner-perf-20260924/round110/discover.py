"""Untimed complete native queries on the unchanged thirteen-case workload."""
import argparse
import ctypes as C
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from native import HERE, Native, SeededStats, abi
from common import Context, verify_solution


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counters(value):
    return {k: v for k, v in value.items() if not k.endswith('seconds')}


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2)+'\n')
    temp.replace(path)


def worker(args):
    ctx, native = Context(sanitizer=args.sanitized), Native(args.sanitized)
    case = ctx.cases[args.case]
    q, original = ctx.queries['matrix-block4'], ctx.instances.get(args.case)
    if original is None:
        manager = ctx.workspaces[args.case, 'matrix-block4'].borrow_mapping(ctx.anfs[args.case])
    else:
        shape = original.n, original.mod, original.b, original.m, original.l
        manager = ctx.plans[shape, 'matrix-block4'].borrow(original.xR)
    limits = ctx.limits
    remaining, check_remaining = 80000000, limits['max_check_work']
    r = dict(name=args.case, fixture=case, status='inconclusive', verified=False,
        algebra_verified=False, attempts=[], bridge_work=0, scan_work=0, sanitized=args.sanitized,
        timing_eligible=False, qualified_speedup=None, native_integration=True)

    def check(packed, view):
        nonlocal check_remaining
        result = q._check(packed.view, view, check_remaining, limits['max_terms'])
        check_remaining -= result['stats']['work']
        result['stats'] = counters(result['stats'])
        return result

    def accept(view, certificate):
        basis, proof = abi.export(view)
        r.update(status='gb', verified=True, algebra_verified=True, basis=basis, proof=proof, certificate=certificate)
        if original is not None:
            r.update(status='gb-no-verified-solution', verified=False)
            for assignment in range(1 << case['nvars']):
                if any(sum((m & assignment) == m for m in row) % 2 for row in basis):
                    continue
                if original.evaluate(assignment) == 0 and verify_solution(original, assignment):
                    r.update(status='solved', verified=True, assignment=assignment,
                        reference_equations_and_curve_replay=True)
                    break

    with manager as packed:
        assert packed.matches_mapping(ctx.anfs[args.case])
        layout = ctx.layouts[ctx.shapes[args.case, 'matrix-block4'], 'matrix-block4']
        matrix_stats = q.lib.macaulay_apply.argtypes[-1]._type_()
        matrix = q.lib.macaulay_apply(layout._handle, C.byref(packed.view),
            min(remaining, limits['matrix_cap']), limits['max_nodes'], limits['max_rows'], C.byref(matrix_stats))
        remaining -= matrix_stats.work
        first = dict(kind='macaulay', stats=counters(abi.fields(matrix_stats)),
            parity=counters(q._parity_local.stats), block=q._block_local.stats)
        r['attempts'].append(first)
        returned_seed = bool(matrix)
        try:
            if matrix:
                seed = q.lib.macaulay_view(matrix).contents
                certificate = check(packed, seed)
                first['certificate'] = certificate
                if certificate['verified']:
                    accept(seed, certificate)
                else:
                    # No Python polynomial/proof materialization or coefficient
                    # repacking occurs between the two native producers.
                    stats = SeededStats()
                    handle = native.lib.seeded_produce(C.byref(packed.view), C.byref(seed), remaining,
                        limits['max_nodes'], limits['max_rows'], limits['batch'], 1, C.byref(stats))
                    remaining -= stats.work
                    r['bridge_work'], r['scan_work'] = stats.bridge_work, stats.scan_work
                    r['native_stats'] = {name: getattr(stats, name) for name in
                        ('work', 'bridge_work', 'scan_work', 'f4_started', 'composition_started', 'reserved_seed_nodes', 'status')}
                    limbs = (packed.view.equations+63)//64
                    r['packed_scan'] = dict(nvars=packed.view.nvars, equations=packed.view.equations,
                        masks=[packed.view.masks[i] for i in range(packed.view.terms)],
                        coefficients=[packed.view.coefficients[i] for i in range(packed.view.terms*limbs)])
                    stage = dict(kind='seeded-f4', reserved_seed_nodes=stats.reserved_seed_nodes,
                        stats=counters(abi.fields(stats.producer)))
                    if stats.f4_started:
                        r['attempts'].append(stage)
                    if stats.composition_started:
                        r['composition'] = dict(status='composed-unverified' if handle else 'inconclusive',
                            stats=abi.fields(stats.composition))
                    try:
                        if handle:
                            continuation = native.lib.seeded_continuation_view(handle)
                            assert continuation
                            cb, cp = abi.export(continuation.contents)
                            r['continuation'] = dict(basis=cb, proof=cp)
                            view = native.lib.seeded_view(handle).contents
                            certificate = check(packed, view)
                            stage['certificate'] = certificate
                            if certificate['verified']:
                                accept(view, certificate)
                        else:
                            r['reason'] = native.lib.seeded_error().decode()
                    finally:
                        if handle:
                            native.lib.seeded_destroy(handle)
            else:
                first['reason'] = q.lib.macaulay_error().decode()
        finally:
            if matrix:
                q.lib.macaulay_result_destroy(matrix)
        if not returned_seed:
            producer = abi.ProducerStats()
            handle = q.base.producer.produce_packed(C.byref(packed.view), remaining,
                limits['max_nodes'], limits['max_rows'], limits['batch'], C.byref(producer))
            remaining -= producer.work
            stage = dict(kind='fresh-f4', reserved_seed_nodes=0, stats=counters(abi.fields(producer)))
            r['attempts'].append(stage)
            try:
                if handle:
                    view = q.base.producer.producer_view(handle).contents
                    certificate = check(packed, view)
                    stage['certificate'] = certificate
                    if certificate['verified']:
                        accept(view, certificate)
                else:
                    stage['reason'] = q.base.producer.producer_error().decode()
            finally:
                if handle:
                    q.base.producer.producer_destroy(handle)
    r.update(work=80000000-remaining, check_work=limits['max_check_work']-check_remaining)
    assert r['work'] == sum(a['stats']['work'] for a in r['attempts'])+r['bridge_work']+r['scan_work']+r.get('composition', {}).get('stats', {}).get('work', 0)
    assert 0 <= r['work'] <= 80000000 and 0 <= r['check_work'] <= limits['max_check_work']
    save(args.output, r)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case')
    parser.add_argument('--sanitized', action='store_true')
    args = parser.parse_args()
    if args.case:
        worker(args)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    build = json.loads((HERE/'build/receipt.json').read_text())
    record = dict(status='RUNNING', source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        scripts={p.name: sha(p) for p in HERE.glob('*.py')}, build=build,
        reference_plan=json.loads((HERE.parent/'round108/panel.json').read_text()), rows=[],
        timing_eligible=False, qualified_speedup=None, native_integration=True)
    save(args.output/'report.json', record)
    lock = Path('/private/tmp/cryptanalysis-overlap-evidence-20261003/local-heavy.lock' if sys.platform == 'darwin' else '/tmp/groebner-local-heavy.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        for path in HERE.glob('*.py'):
            assert path.read_bytes() == subprocess.check_output(['git', 'show', 'HEAD:'+str(path.relative_to(HERE.parents[2]))], cwd=HERE)
        for name, digest in build['sources'].items():
            assert sha(HERE/name) == digest
        for name, digest in build['binaries'].items():
            assert sha(HERE/'build'/name) == digest
        reference = HERE.parent/'round108'
        for name, digest in build['reference']['sources'].items():
            assert sha(HERE.parent.parent/name) == digest
        for group in ('generated', 'binaries', 'resources'):
            for name, digest in build['reference'][group].items():
                assert sha(reference/'build'/name) == digest
        for sanitized in (False, True):
            for name in record['reference_plan']['cases']:
                target = args.output/(name+('-ubsan' if sanitized else '')+'.json')
                command = [sys.executable, str(HERE/'discover.py'), '--output', str(target), '--case', name]+(['--sanitized'] if sanitized else [])
                with target.with_suffix('.log').open('w') as log:
                    try:
                        done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=60)
                        row = dict(name=name, sanitized=sanitized, exit_code=done.returncode,
                            execution='completed' if done.returncode == 0 else 'process-failure')
                    except subprocess.TimeoutExpired:
                        row = dict(name=name, sanitized=sanitized, execution='timeout')
                if row['execution'] == 'completed':
                    row.update(result=target.name, sha256=sha(target))
                record['rows'].append(row)
                save(args.output/'report.json', record)
                print(name, sanitized, row['execution'], flush=True)
    record['status'] = 'RECORDED_PENDING_AUDIT'
    save(args.output/'report.json', record)


if __name__ == '__main__':
    main()
