"""Audit the shipped source patch and historical measurements without Sage."""
import collections
import hashlib
import json
import math
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verify_patch():
    manifest = read(HERE/'source-manifest.json')
    patch = HERE/'sage-binary-batch.patch'
    assert sha(patch) == manifest['patch_sha256']
    for name, digest in manifest['source_sha256'].items():
        assert sha(HERE/'source'/name) == digest, name
    for name, digest in manifest['upstream_base_sha256'].items():
        assert sha(HERE/'upstream-base'/name) == digest, name
    with tempfile.TemporaryDirectory(prefix='sage-batch-patch-') as directory:
        checkout = Path(directory)
        shutil.copytree(HERE/'upstream-base', checkout, dirs_exist_ok=True)
        subprocess.run(['git','init','--quiet',str(checkout)],check=True)
        subprocess.run(['git','apply','--check','--whitespace=error-all',str(patch)],cwd=checkout,check=True)
        subprocess.run(['git','apply',str(patch)],cwd=checkout,check=True)
        for name, digest in manifest['source_sha256'].items():
            assert sha(checkout/'src/sage/schemes/elliptic_curves'/name) == digest, name


def verify_run(directory, run, expected_cells, omitted):
    root = HERE.parent/directory
    manifest = read(root/'evidence-manifest.json')
    missing = {}
    for name, digest in manifest.items():
        path = root/name
        if path.exists():
            assert sha(path) == digest, f'{directory}/{name}'
        else:
            missing[name] = digest
    assert missing == omitted, (directory, missing)
    assert all(name.endswith('.so') for name in omitted)
    intent = read(root/'intent-v1.json')
    assert sha(root/'intent-v1.json') == (root/'intent-v1.sha256').read_text().split()[0]
    plan = read(root/run/'execution-plan.json')
    assert plan['intent_sha256'] == sha(root/'intent-v1.json')
    for name, digest in plan['source_sha256'].items():
        path = root/run/'sources'/name
        if path.exists():
            assert sha(path) == digest, path
        else:
            assert omitted[f'{run}/sources/{name}'] == digest
    report = read(root/run/'summary.json')
    paths = sorted((root/run).glob('cell-[0-9][0-9].json'))
    assert len(paths) == len(plan['cases']) == len(report['cells']) == expected_cells
    completed = 0
    for i, path in enumerate(paths):
        row = read(path)
        assert row['case'] == plan['cases'][i]
        assert row['exact_output_agreement']
        assert len(row['rounds']) == 12
        assert collections.Counter(tuple(r['order']) for r in row['rounds']) == {
            ('incumbent','candidate'):6, ('candidate','incumbent'):6}
        count = row['case']['side']**2
        calls = 4 if expected_cells == 26 else max(4, math.ceil(4096/count))
        assert row.get('calls_per_sample', calls) == calls
        assert row['completed_outputs'] == count*calls*24
        completed += row['completed_outputs']
        assert read(root/run/f'cell-{i:02d}-parent.json')['returncode'] == 0
        logs = [math.log(r['arms']['incumbent']['wall_seconds']/r['arms']['candidate']['wall_seconds'])
                for r in row['rounds']]
        assert math.isclose(math.exp(statistics.median(logs)), report['cells'][i]['speedup'])
        cpu = statistics.median(r['arms']['candidate']['cpu_seconds']/r['arms']['incumbent']['cpu_seconds']
                                for r in row['rounds'])
        assert math.isclose(cpu,report['cells'][i]['cpu_ratio'])
        # Check binary identity as recorded, without pretending that omitted
        # machine-specific extensions were loaded or rebuilt by this audit.
        assert set(row['installed_sha256'].values()) == {
            plan['source_sha256']['binary_batch.py'],
            next(d for n,d in plan['source_sha256'].items() if n.startswith('binary_batch_ntl.') and n.endswith('.so'))}
        if expected_cells == 40:
            assert row['incumbent_native_sha256'] == intent['incumbent_revision_and_binary_hash']['native_binary_sha256']
    for phase in ('primary','confirmation'):
        cells = [c for c in report['cells'] if c['phase'] == phase]
        speedup = math.exp(statistics.mean(math.log(c['speedup']) for c in cells))
        assert math.isclose(speedup,report[phase]['geomean_speedup'])
        assert report[phase]['pass_gate'] == (speedup > intent['criteria'][phase+'_geomean_speedup_min']
                                              and report[phase]['bootstrap_95'][0] > 1)
    assert report['per_cell_gate'] == all(c['speedup'] >= 1/1.02 for c in report['cells'])
    assert report['cpu_gate'] == all(c['cpu_ratio'] <= 1.05 for c in report['cells'])
    for api, values in report['rss_bytes'].items():
        for arm, value in values.items():
            assert read(root/run/f'rss-{api}-{arm}.json')['max_rss_bytes'] == value
    assert report['rss_gate'] == all(v['candidate'] <= max(1.05*v['incumbent'], v['incumbent']+2*1024**2)
                                   for v in report['rss_bytes'].values())
    assert report['decision'] == 'PASS_LOCAL'
    assert all([report['primary']['pass_gate'],report['confirmation']['pass_gate'],
                report['per_cell_gate'],report['cpu_gate'],report['rss_gate']])
    return {'directory':directory,'cells':expected_cells,'verified_recorded_outputs':completed,
            'verified_files':len(manifest)-len(omitted),'omitted_native_binaries':len(omitted)}


def main():
    verify_patch()
    layout = read(HERE/'archive-layout.json')
    rows = [verify_run(a['directory'],'run-001',26 if a['directory'].endswith('native-addition') else 40,
                       a['omitted_native_binaries']) for a in layout['archives']]
    print(json.dumps({'source_patch':'PASS','historical_record_audit':rows},indent=2))


if __name__ == '__main__':
    main()
