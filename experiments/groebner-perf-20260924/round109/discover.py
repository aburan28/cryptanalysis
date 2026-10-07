"""Frozen, untimed seeded-F4 discovery using the recorded round108 libraries.

Only a completed matrix candidate may seed F4. Every original generator is
retained. Composed proofs are checked against the original packed coefficients.
No CPU timing or native-integration claim is made by this Python bridge.
"""
import argparse
import ctypes as C
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from compose import compose

HERE = Path(__file__).resolve().parent


class BridgeLimit(Exception):
    pass


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counters(value):
    return {k: v for k, v in value.items() if not k.endswith('seconds')}


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2)+'\n')
    temp.replace(path)


def worker(args):
    sys.path.insert(0, str(args.reference))
    from common import Context, abi, verify_solution
    ctx = Context(sanitizer=args.sanitized)
    case = ctx.cases[args.case]
    q = ctx.queries['matrix-block4']
    original = ctx.instances.get(args.case)
    if original is None:
        manager = ctx.workspaces[args.case, 'matrix-block4'].borrow_mapping(ctx.anfs[args.case])
    else:
        shape = original.n, original.mod, original.b, original.m, original.l
        manager = ctx.plans[shape, 'matrix-block4'].borrow(original.xR)
    limits = ctx.limits
    remaining, check_remaining = 80000000, limits['max_check_work']
    r = dict(name=args.case, fixture=case, status='inconclusive', verified=False,
             algebra_verified=False, attempts=[], bridge_work=0, sanitized=args.sanitized,
             timing_eligible=False, qualified_speedup=None, native_integration=False)

    def pay(amount):
        nonlocal remaining
        if amount > remaining:
            raise BridgeLimit('bridge work budget')
        remaining -= amount
        r['bridge_work'] += amount

    def check(packed, view):
        nonlocal check_remaining
        result = q._check(packed.view, view, check_remaining, limits['max_terms'])
        check_remaining -= result['stats']['work']
        result['stats'] = counters(result['stats'])
        return result

    def accept(basis, proof, certificate):
        assert certificate['verified']
        r.update(status='gb', verified=True, algebra_verified=True,
                 basis=basis, proof=proof, certificate=certificate)
        if original is not None:
            r.update(status='gb-no-verified-solution', verified=False)
            for assignment in range(1 << case['nvars']):
                if any(sum((m & assignment) == m for m in row) % 2 for row in basis):
                    continue
                if original.evaluate(assignment) == 0 and verify_solution(original, assignment):
                    r.update(status='solved', verified=True, assignment=assignment,
                             reference_equations_and_curve_replay=True)
                    break

    try:
        with manager as packed:
            assert packed.matches_mapping(ctx.anfs[args.case])
            layout = ctx.layouts[ctx.shapes[args.case, 'matrix-block4'], 'matrix-block4']
            stats = q.lib.macaulay_apply.argtypes[-1]._type_()
            matrix = q.lib.macaulay_apply(layout._handle, C.byref(packed.view),
                min(remaining, limits['matrix_cap']), limits['max_nodes'], limits['max_rows'], C.byref(stats))
            remaining -= stats.work
            attempt = dict(kind='macaulay', stats=counters(abi.fields(stats)),
                           parity=counters(q._parity_local.stats), block=q._block_local.stats)
            r['attempts'].append(attempt)
            seed_basis = seed_proof = None
            try:
                if matrix:
                    view = q.lib.macaulay_view(matrix).contents
                    certificate = check(packed, view)
                    attempt['certificate'] = certificate
                    if certificate['verified']:
                        basis, proof = abi.export(view)
                        accept(basis, proof, certificate)
                    else:
                        # This extra bridge is prospective producer work. Artifact
                        # export for already accepted results follows round108.
                        pay(view.nodes+view.rows+view.terms)
                        seed_basis, seed_proof = abi.export(view)
                else:
                    attempt['reason'] = q.lib.macaulay_error().decode()
            finally:
                if matrix:
                    q.lib.macaulay_result_destroy(matrix)
            if not r['algebra_verified']:
                if seed_basis is None:
                    source = packed
                    reserved = 0
                else:
                    rows = seed_basis+case['equations']
                    pay(len(rows)+sum(map(len, rows)))
                    source = abi.InputOwner(case['nvars'], len(rows), abi.anf_from_equations(rows))
                    reserved = len(seed_proof['nodes'])+len(case['equations'])
                if reserved >= limits['max_nodes']:
                    raise BridgeLimit('retained seed node budget')
                producer_stats = abi.ProducerStats()
                handle = q.base.producer.produce_packed(C.byref(source.view), remaining,
                    limits['max_nodes']-reserved, limits['max_rows'], limits['batch'], C.byref(producer_stats))
                remaining -= producer_stats.work
                stage = dict(kind='seeded-f4' if seed_basis is not None else 'fresh-f4',
                             reserved_seed_nodes=reserved, stats=counters(abi.fields(producer_stats)))
                r['attempts'].append(stage)
                try:
                    if not handle:
                        stage['reason'] = q.base.producer.producer_error().decode()
                    else:
                        view = q.base.producer.producer_view(handle).contents
                        if seed_basis is None:
                            certificate = check(packed, view)
                            stage['certificate'] = certificate
                            if certificate['verified']:
                                basis, proof = abi.export(view)
                                accept(basis, proof, certificate)
                        else:
                            pay(view.nodes+view.rows+view.terms)
                            basis, proof = abi.export(view)
                            composed = compose(seed_proof, proof, len(case['equations']),
                                               max_work=remaining, max_nodes=limits['max_nodes'])
                            remaining -= composed['stats']['work']
                            r['composition'] = {k: v for k, v in composed.items() if k != 'proof'}
                            if composed['proof'] is not None:
                                pay(sum(map(len, basis))+len(basis)+len(composed['proof']['nodes']))
                                owner = abi.ProofOwner(case['nvars'], basis, composed['proof'])
                                certificate = check(packed, owner.view)
                                stage['certificate'] = certificate
                                if certificate['verified']:
                                    accept(basis, composed['proof'], certificate)
                finally:
                    if handle:
                        q.base.producer.producer_destroy(handle)
    except BridgeLimit as error:
        r['reason'] = str(error)
    r.update(work=80000000-remaining, check_work=limits['max_check_work']-check_remaining)
    assert r['work'] == sum(a['stats']['work'] for a in r['attempts'])+r['bridge_work']+r.get('composition', {}).get('stats', {}).get('work', 0)
    assert 0 <= r['work'] <= 80000000 and 0 <= r['check_work'] <= limits['max_check_work']
    save(args.output, r)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case')
    parser.add_argument('--sanitized', action='store_true')
    args = parser.parse_args()
    args.reference = args.reference.resolve()
    if args.case:
        worker(args)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    build = json.loads((args.reference/'build/receipt.json').read_text())
    plan = json.loads((args.reference/'panel.json').read_text())
    record = dict(status='RUNNING', source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
                  scripts={p.name: sha(p) for p in HERE.glob('*.py')},
                  reference_build=build, reference_plan=plan, rows=[], timing_eligible=False,
                  qualified_speedup=None, purpose='untimed algorithmic discovery; Python proof bridge, existing native kernels')
    save(args.output/'report.json', record)
    lock = Path('/private/tmp/cryptanalysis-overlap-evidence-20261003/local-heavy.lock')
    with lock.open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        for p in HERE.glob('*.py'):
            relative = str(p.relative_to(HERE.parents[2]))
            assert subprocess.check_output(['git', 'show', 'HEAD:'+relative], cwd=HERE) == p.read_bytes()
        for name, digest in build['sources'].items():
            assert sha(args.reference.parent.parent/name) == digest
        for group in ('binaries', 'generated', 'resources'):
            for name, digest in build[group].items():
                assert sha(args.reference/'build'/name) == digest
        with (args.output/'unit-tests.log').open('w') as log:
            test = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(HERE), '-v'], stdout=log, stderr=subprocess.STDOUT)
        record['unit_exit_code'] = test.returncode
        if test.returncode:
            record['status'] = 'FAIL'
            save(args.output/'report.json', record)
            raise SystemExit(test.returncode)
        for sanitized in (False, True):
            for name in plan['cases']:
                target = args.output/(name+('-ubsan' if sanitized else '')+'.json')
                command = [sys.executable, str(HERE/'discover.py'), '--reference', str(args.reference),
                           '--output', str(target), '--case', name]+(['--sanitized'] if sanitized else [])
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
