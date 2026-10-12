"""Freeze paired complete F4 queries for a qualifying isolated Linux host."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--validation-root', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--cgroup', type=Path, required=True)
    parser.add_argument('--cpus', required=True)
    parser.add_argument('--execution-cpu', type=int, required=True)
    parser.add_argument('--mem-nodes', required=True)
    parser.add_argument('--repetitions', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, validation = args.reference_root.resolve(), args.validation_root.resolve()
    assert all(path.is_absolute() for path in (args.python, args.cgroup, args.output))
    assert args.python.is_file() and args.repetitions > 0
    record = json.loads((validation/'validation.json').read_text())
    audit = json.loads((validation/'audit.json').read_text())
    report = json.loads((validation/'panel/report.json').read_text())
    assert record['status'] == audit['status'] == 'PASS'
    assert len(report['rows']) == audit['rows'] == 52
    assert all(step['exit_code'] == 0 for step in record['steps'])
    rows = {}
    for entry in report['rows']:
        if entry['sanitized']:
            continue
        path = validation/'panel'/entry['result']
        assert sha(path) == entry['sha256']
        row = json.loads(path.read_text())
        rows[entry['name'], entry['early_mode']] = row
    cases, excluded = [], []
    for name in sorted({name for name, _ in rows}):
        left, right = rows[name, 0], rows[name, 1]
        if left['fixture']['boundary'] != 'pdp':
            continue
        assert left['fixture'] == right['fixture']
        results = [left['result'], right['result']]
        if not all(result['status'] == 'solved' and result['verified'] and result['complete']
                   and result.get('reference_equations_and_curve_replay') is True
                   and result.get('proof_artifact') for result in results):
            excluded.append(dict(case=name, reference_status=results[0]['status'],
                                 candidate_status=results[1]['status'],
                                 reason='one or both variants lacked a verified complete query'))
            continue
        argv = []
        for mode, result in enumerate(results):
            artifact = result['proof_artifact']
            proof = validation/'panel'/artifact['path']
            assert sha(proof) == artifact['sha256']
            argv.append([str(args.python), str(HERE/'isolated_worker.py'),
                         '--reference-root', str(root), '--case', name,
                         '--early-mode', str(mode),
                         '--expected-proof-sha', artifact['sha256'],
                         '--expected-assignment', str(result['assignment'])])
        cases.append(dict(id=name, reference=argv[0], candidate=argv[1]))
    assert cases, 'no pair completed with independent equations and curve replay'
    receipt = json.loads((validation/'build-receipt.json').read_text())
    binaries = []
    for stage, spec in (('round112', receipt), ('round110', receipt['reference']),
                        ('round108', receipt['reference']['reference'])):
        build = root/'experiments/groebner-perf-20260924'/stage/'build'
        for name, digest in spec['binaries'].items():
            path = build/name
            assert sha(path) == digest
            binaries.append(str(path))
    artifacts = [str(HERE/'isolated_worker.py'),
                 str(root/'experiments/groebner-perf-20260924/round112/early_query.py'),
                 str(root/'experiments/groebner-perf-20260924/round112/panel.py'),
                 str(root/'experiments/groebner-perf-20260924/round111/panel.py'),
                 str(validation/'validation.json'), str(validation/'audit.json'),
                 str(validation/'panel/report.json'), *binaries]
    manifest = dict(schema=1, name='groebner-early-parity-complete-query',
        workdir=str(root), isolation=dict(cgroup=str(args.cgroup), cpus=args.cpus,
            execution_cpu=args.execution_cpu, mem_nodes=args.mem_nodes),
        build=dict(source_commit=record['source_commit'], source_tree=record['source_tree'],
            validation_sha256=sha(validation/'validation.json'),
            audit_sha256=sha(validation/'audit.json')),
        artifacts=artifacts, timeout_s=120, repetitions=args.repetitions,
        measurement_boundary='Context.run wall_ns: target-dependent coefficient borrowing through proof checked basis, original-equation and curve replay; reusable setup and proof-byte digest excluded',
        pair_fields=['case', 'fixture_sha', 'target_x', 'mod', 'b', 'm', 'nvars'],
        cases=cases, excluded_validation_cases=excluded,
        qualified_speedup=None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert not args.output.exists()
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n')
    print('ISOLATED_MANIFEST_READY', len(cases), 'verified pairs;',
          len(excluded), 'other PDP cases retained in validation')


if __name__ == '__main__':
    main()
