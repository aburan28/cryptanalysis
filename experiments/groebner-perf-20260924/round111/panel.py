"""Complete-query profiling; independent artifact decoding is outside the timer."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from seeded_query import HERE, Query, abi
from query import PackedDescentPlan
from common import Context as ReferenceContext, fixtures, plan, prepare_polynomials, make_instance


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


class Context(ReferenceContext):
    """Prepare only one frozen case; inherited run includes both curve replays."""
    def __init__(self, name, sanitized=False):
        prepare_polynomials()
        case = next(c for c in fixtures() if c['name'] == name)
        self.cases = {name: case}
        self.limits = {**plan()['limits'], 'max_work': 80000000}
        q = Query(sanitizer=sanitized)
        self.queries = {'matrix-block4': q}
        anf = abi.anf_from_equations(case['equations'])
        self.anfs = {name: anf}
        self.instances, self.plans, self.workspaces = {}, {}, {}
        shape = (case['nvars'], len(case['equations']),
                 min(case['nvars'], 6 if case['boundary'] == 'pdp' else 2), 2)
        self.shapes = {(name, 'matrix-block4'): shape}
        self.layouts = {(shape, 'matrix-block4'): q.layout(*shape)}
        if case['boundary'] == 'pdp':
            original = make_instance(case['n'], case['m'], case['ell'], seed=case['seed'])
            assert (original.mod, original.b, original.xR) == (case['mod'], case['b'], case['target_x'])
            assert [sorted(row) for row in original.equations()] == case['equations']
            self.instances[name] = original
            shape = original.n, original.mod, original.b, original.m, original.l
            self.plans[shape, 'matrix-block4'] = PackedDescentPlan(q, *shape)
        else:
            self.workspaces[name, 'matrix-block4'] = q.workspace(case['nvars'], len(case['equations']), list(anf))


def worker(args):
    ctx = Context(args.case, args.sanitized)
    try:
        row = ctx.run(args.case, 'matrix-block4')
    finally:
        for layout in ctx.layouts.values():
            layout.close()
    result = row['result']
    if 'proof' in result:
        owned = result.pop('proof')
        path = args.output.with_suffix('.gbp')
        path.write_bytes(owned.serialized())
        result['proof_artifact'] = dict(path=path.name, sha256=sha(path),
            bytes=path.stat().st_size, nodes=owned.nodes, outputs=owned.outputs)
    row.update(name=args.case, sanitized=args.sanitized, fixture=ctx.cases[args.case],
        timing_eligible=False, qualified_speedup=None)
    save(args.output, row)


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
    report = dict(status='RUNNING', source_commit=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        scripts={p.name: sha(p) for p in HERE.glob('*.py')},
        native_build=json.loads((HERE.parent/'round110/build/receipt.json').read_text()),
        plan=plan(), rows=[], timing_eligible=False, qualified_speedup=None)
    save(args.output/'report.json', report)
    for sanitized in (False, True):
        for name in plan()['cases']:
            target = args.output/(name+('-ubsan' if sanitized else '')+'.json')
            command = [sys.executable, str(HERE/'panel.py'), '--case', name, '--output', str(target)]
            if sanitized: command.append('--sanitized')
            with target.with_suffix('.log').open('w') as log:
                try:
                    done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=60)
                    row = dict(name=name, sanitized=sanitized, exit_code=done.returncode,
                        execution='completed' if done.returncode == 0 else 'process-failure')
                except subprocess.TimeoutExpired:
                    row = dict(name=name, sanitized=sanitized, execution='timeout')
            if row['execution'] == 'completed':
                row.update(result=target.name, sha256=sha(target))
            report['rows'].append(row)
            save(args.output/'report.json', report)
            print(name, sanitized, row['execution'], flush=True)
    report['status'] = 'RECORDED_PENDING_AUDIT'
    save(args.output/'report.json', report)


if __name__ == '__main__':
    main()
