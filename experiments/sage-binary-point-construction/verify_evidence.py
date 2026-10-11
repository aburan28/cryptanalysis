"""Verify preserved receipts and that the measured extension is still installed."""
import collections
import hashlib
import json
import math
import statistics
from pathlib import Path

from sage.schemes.elliptic_curves import binary_batch, binary_batch_ntl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    run = HERE/'run-001'
    manifest = json.loads((HERE/'evidence-manifest.json').read_text())
    for name, digest in manifest.items():
        assert sha(HERE/name) == digest, name
    intent = json.loads((HERE/'intent-v1.json').read_text())
    assert sha(HERE/'intent-v1.json') == (HERE/'intent-v1.sha256').read_text().split()[0]
    plan = json.loads((run/'execution-plan.json').read_text())
    assert plan['intent_sha256'] == sha(HERE/'intent-v1.json')
    for name, digest in plan['source_sha256'].items():
        assert sha(run/'sources'/name) == digest, name
    native_old = HERE/'baseline'/intent['incumbent_revision_and_binary_hash']['native_filename']
    assert sha(HERE/'baseline/binary_batch.py') == intent['incumbent_revision_and_binary_hash']['source_sha256']
    assert sha(HERE/'baseline/binary_batch_ntl.pyx') == intent['incumbent_revision_and_binary_hash']['native_source_sha256']
    assert sha(native_old) == intent['incumbent_revision_and_binary_hash']['native_binary_sha256']
    assert sha(native_old) != sha(binary_batch_ntl.__file__)
    report = json.loads((run/'summary.json').read_text())
    cell_paths = sorted(run.glob('cell-[0-9][0-9].json'))
    assert len(cell_paths) == len(plan['cases']) == len(report['cells']) == 40
    completed = 0
    for i, path in enumerate(cell_paths):
        row = json.loads(path.read_text())
        assert row['case'] == plan['cases'][i]
        assert row['exact_output_agreement']
        assert row['incumbent_native_sha256'] == sha(native_old)
        assert len(row['rounds']) == 12
        orders = collections.Counter(tuple(r['order']) for r in row['rounds'])
        assert orders == {('incumbent','candidate'):6, ('candidate','incumbent'):6}
        count = row['case']['side']**2
        assert row['calls_per_sample'] == max(4, math.ceil(4096/count))
        assert row['completed_outputs'] == count*row['calls_per_sample']*24
        completed += row['completed_outputs']
        for installed, digest in row['installed_sha256'].items():
            assert sha(installed) == digest, installed
        assert json.loads((run/f'cell-{i:02d}-parent.json').read_text())['returncode'] == 0
        logs = [math.log(r['arms']['incumbent']['wall_seconds'])
                - math.log(r['arms']['candidate']['wall_seconds']) for r in row['rounds']]
        assert math.isclose(math.exp(statistics.median(logs)), report['cells'][i]['speedup'])
    for phase in ('primary','confirmation'):
        cells = [c for c in report['cells'] if c['phase'] == phase]
        geometric_mean = math.exp(statistics.mean(math.log(c['speedup']) for c in cells))
        assert math.isclose(geometric_mean, report[phase]['geomean_speedup'])
        assert report[phase]['pass_gate'] == (
            geometric_mean > intent['criteria'][phase+'_geomean_speedup_min']
            and report[phase]['bootstrap_95'][0] > 1)
    assert report['per_cell_gate'] == all(c['speedup'] >= 1/1.02 for c in report['cells'])
    assert report['cpu_gate'] == all(c['cpu_ratio'] <= 1.05 for c in report['cells'])
    assert report['rss_gate'] == all(r['candidate'] <= max(1.05*r['incumbent'], r['incumbent']+2*1024**2)
                                   for r in report['rss_bytes'].values())
    decision = 'PASS_LOCAL' if all([report['primary']['pass_gate'], report['confirmation']['pass_gate'],
        report['per_cell_gate'], report['cpu_gate'], report['rss_gate']]) else 'HOLD'
    assert report['decision'] == decision
    source = ROOT/'third_party/sage-binary/src/sage/schemes/elliptic_curves'
    contract = json.loads((HERE/'constructor-contract.json').read_text())
    for name, digest in contract['source_sha256'].items():
        assert sha(ROOT/'third_party/sage-binary'/name) == digest, name
    assert sha(source/'binary_batch.py') == sha(binary_batch.__file__)
    assert sha(source/'binary_batch_ntl.pyx') == sha(run/'sources/binary_batch_ntl.pyx')
    assert binary_batch._native is binary_batch_ntl
    install = json.loads((HERE/'install-001/install.json').read_text())
    assert install['returncode'] == 0
    for item in install['files']:
        assert sha(item['source']) == sha(item['target']) == item['sha256']
    receipt = dict(status='PASS', decision=decision, manifest_files_verified=len(manifest),
        timing_cells_verified=len(cell_paths), timed_outputs_verified=completed,
        installed_module=binary_batch.__file__, installed_native=binary_batch_ntl.__file__,
        installed_native_sha256=sha(binary_batch_ntl.__file__),
        incumbent_native_sha256=sha(native_old))
    (HERE/'validation-final.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
