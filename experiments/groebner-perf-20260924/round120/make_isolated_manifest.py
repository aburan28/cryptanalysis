"""Freeze scratch/bitset complete F4 queries for an isolated Linux host."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
CASES = [f'pdp-12-seed-{seed}' for seed in range(1, 6)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(directory, commit):
    report_path = directory / 'report.json'
    report = json.loads(report_path.read_text())
    assert report['status'] == 'PASS' and report['source_commit'] == commit
    assert len(report['rows']) == 10
    rows = {}
    for entry in report['rows']:
        assert entry['execution'] == 'completed' and entry['exit_code'] == 0
        path = directory / entry['result']
        assert sha(path) == entry['sha256']
        row = json.loads(path.read_text())
        assert row['result']['status'] == 'solved'
        assert row['result']['verified'] and row['result']['complete']
        assert row['result']['reference_equations_and_curve_replay']
        assert row['reference_match']['original_equations_and_curve_verified']
        artifact = row['result']['proof_artifact']
        assert artifact['sha256'] == row['reference_match']['proof_sha256']
        assert sha(path.with_suffix('.gbp')) == artifact['sha256']
        if not entry['sanitized']:
            assert entry['name'] not in rows
            rows[entry['name']] = row
    assert set(rows) == set(CASES)
    return report_path, rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--validation-root', type=Path, required=True)
    parser.add_argument('--scratch-panel', type=Path, required=True)
    parser.add_argument('--bitset-panel', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--cgroup', type=Path, required=True)
    parser.add_argument('--cpus', required=True)
    parser.add_argument('--execution-cpu', type=int, required=True)
    parser.add_argument('--mem-nodes', required=True)
    parser.add_argument('--repetitions', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, validation = args.reference_root.resolve(), args.validation_root.resolve()
    assert root == HERE.parents[2].resolve(), 'manifest and binaries must share one checkout'
    assert all(path.is_absolute() for path in (args.python, args.cgroup, args.output))
    assert args.python.is_file() and args.repetitions > 0
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=root, text=True).strip()
    assert subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip() == ''
    scratch_report, scratch = records(args.scratch_panel, commit)
    bitset_report, bitset = records(args.bitset_panel, commit)
    record = json.loads((validation / 'validation.json').read_text())
    audit = json.loads((validation / 'audit.json').read_text())
    assert record['status'] == audit['status'] == 'PASS' and audit['rows'] == 52
    assert all(step['exit_code'] == 0 for step in record['steps'])
    assert sha(validation / 'panel/report.json') == json.loads(scratch_report.read_text())['reference_sha256']
    assert sha(validation / 'panel/report.json') == json.loads(bitset_report.read_text())['reference_sha256']
    cases = []
    for name in CASES:
        left, right = scratch[name], bitset[name]
        assert left['fixture'] == right['fixture']
        a, b = left['result'], right['result']
        assert a['assignment'] == b['assignment'] and a['basis'] == b['basis']
        assert a['work'] == b['work'] and a['check_work'] == b['check_work']
        assert a['proof_artifact']['sha256'] == b['proof_artifact']['sha256']
        argv = []
        for arm in ('scratch', 'bitset'):
            result = (left if arm == 'scratch' else right)['result']
            argv.append([str(args.python), str(HERE / 'isolated_worker.py'),
                         '--reference-root', str(root), '--case', name, '--arm', arm,
                         '--expected-proof-sha', result['proof_artifact']['sha256'],
                         '--expected-assignment', str(result['assignment']),
                         '--expected-work', str(result['work']),
                         '--expected-check-work', str(result['check_work'])])
        cases.append(dict(id=name, reference=argv[0], candidate=argv[1]))
    artifacts = [str(HERE / 'isolated_worker.py'), str(HERE / 'make_isolated_manifest.py'),
                 str(HERE / 'test_manifest.py'),
                 str(validation / 'validation.json'), str(validation / 'audit.json'),
                 str(validation / 'panel/report.json'), str(scratch_report), str(bitset_report)]
    for round_number in (108, 110, 112, 116, 118, 119):
        directory = BASE / f'round{round_number}'
        receipt = directory / 'build/receipt.json'
        build = json.loads(receipt.read_text())
        artifacts.append(str(receipt))
        for name, digest in build['binaries'].items():
            binary = directory / 'build' / name
            assert sha(binary) == digest
            artifacts.append(str(binary))
    for directory in (BASE / 'round118', BASE / 'round119'):
        artifacts.extend(str(path) for path in sorted(directory.glob('*.py')))
    manifest = dict(schema=1, name='groebner-bitset-complete-query',
        workdir=str(root), isolation=dict(cgroup=str(args.cgroup), cpus=args.cpus,
            execution_cpu=args.execution_cpu, mem_nodes=args.mem_nodes),
        build=dict(source_commit=commit, source_tree=tree,
            reference_validation_sha256=sha(validation / 'validation.json'),
            reference_audit_sha256=sha(validation / 'audit.json'),
            scratch_report_sha256=sha(scratch_report), bitset_report_sha256=sha(bitset_report)),
        artifacts=sorted(set(artifacts)), timeout_s=120, repetitions=args.repetitions,
        measurement_boundary='Context.run wall_ns: target-dependent coefficient borrowing through independently checked proof, original equations, and curve replay; setup and proof-byte digest excluded',
        pair_fields=['case', 'fixture_sha', 'target_x', 'mod', 'b', 'm', 'nvars',
                     'proof_sha', 'work', 'check_work'], cases=cases,
        qualified_speedup=None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert not args.output.exists()
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    print('ISOLATED_BITSET_MANIFEST_READY', len(cases), 'verified pairs', flush=True)


if __name__ == '__main__':
    main()
