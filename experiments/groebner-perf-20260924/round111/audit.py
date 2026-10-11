"""Native-free comparison to frozen round110 plus fresh mathematical replay."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE.parent/'round109'), str(HERE.parent/'round108')]
from proof_reader import decode
spec = importlib.util.spec_from_file_location('mathematics109', HERE.parent/'round109/audit.py')
mathematical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mathematical)
ARCHIVE_SHA = 'ec795cf9d2c65aa7199b28291c2af5f8c59a181a04ed517555052becf49d01d1'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def counters(stats):
    return {k: v for k, v in stats.items() if not k.endswith('seconds')}


def certificate(value):
    if value is None:
        return None
    return {**value, 'stats': counters(value['stats'])}


def frozen():
    path = HERE.parent/'round110/results.tar.gz'
    assert digest(path.read_bytes()) == ARCHIVE_SHA
    with tarfile.open(path, 'r:gz') as archive:
        manifest = json.load(archive.extractfile('manifest.json'))
        def read(name):
            item = manifest['logical_files']['native-seeded-validation-v1/discovery/'+name]
            data = archive.extractfile('objects/'+item['sha256']).read()
            assert len(data) == item['size'] and digest(data) == item['sha256']
            return json.loads(data)
        report = read('report.json')
        records = {(r['name'], r['sanitized']): read(r['result']) for r in report['rows']}
        return report, records


def one(row, expected, folder):
    assert (row['name'], row['sanitized'], row['fixture']) == (
        expected['name'], expected['sanitized'], expected['fixture'])
    assert row['timing_eligible'] is False and row['qualified_speedup'] is None
    result = row['result']
    assert result['timing_eligible'] is False and result['qualified_speedup'] is None
    assert result['continuation_policy'] == 'native-seeded'
    assert result['proof_transport_policy'] == 'owned-binary' and result['layout_policy'] == 'reused'
    for value in (row, result):
        assert type(value['wall_ns']) is int and value['wall_ns'] >= 0
        assert all(type(v) is int and v >= 0 for v in value['phases'].values())
        assert sum(value['phases'].values()) == value['wall_ns']
    assert result['wall_ns'] <= row['phases']['algebra_and_certificate_ns']
    assert set(result['phases']) == {'matrix_ns', 'seeded_production_ns', 'fresh_f4_ns',
        'checker_ns', 'basis_ns', 'proof_copy_ns', 'teardown_ns', 'overhead_ns'}
    for key in ('status', 'verified', 'algebra_verified', 'work', 'check_work'):
        assert result[key] == expected[key], (row['name'], key)
    assert 0 <= result['work'] <= 80000000 and 0 <= result['check_work'] <= 200000000
    assert result['complete'] is result['algebra_verified']
    assert len(result['attempts']) == len(expected['attempts'])
    for actual, reference in zip(result['attempts'], expected['attempts']):
        assert actual['kind'] == reference['kind']
        assert certificate(actual.get('certificate')) == reference.get('certificate')
        assert actual['verified'] is bool(reference.get('certificate', {}).get('verified', False))
        if actual['kind'] == 'seeded-f4':
            assert actual['stats'] == expected['native_stats']
            assert counters(actual['producer']) == reference['stats']
            assert actual['composition'] == expected['composition']['stats']
            assert actual['stats']['work'] == actual['producer']['work']+actual['composition']['work']+actual['stats']['bridge_work']+actual['stats']['scan_work']
        else:
            assert counters(actual['stats']) == reference['stats']
        if actual['kind'] == 'macaulay':
            assert counters(actual['parity']) == reference['parity'] and actual['block'] == reference['block']
    assert result['work'] == sum(a['stats']['work'] for a in result['attempts'])
    assert result['check_work'] == sum(a.get('certificate', {}).get('stats', {}).get('work', 0) for a in result['attempts'])
    if result['algebra_verified']:
        assert result['basis'] == expected['basis'] and certificate(result['certificate']) == expected['certificate']
        artifact = result['proof_artifact']
        assert Path(artifact['path']).name == artifact['path']
        path = Path(folder)/artifact['path']
        assert not path.is_symlink()
        data = path.read_bytes()
        assert digest(data) == artifact['sha256'] and len(data) == artifact['bytes']
        proof = decode(data)
        assert proof == expected['proof']
        assert len(proof['nodes']) == artifact['nodes'] and len(proof['outputs']) == artifact['outputs']
        mathematical.mathematics(json.dumps([row['fixture']['nvars'], row['fixture']['equations'], result['basis'], proof]))
    else:
        assert not {'basis', 'proof', 'proof_artifact', 'certificate'} & result.keys()
    if expected.get('reference_equations_and_curve_replay'):
        assert result['assignment'] == expected['assignment']
        assert result['reference_equations_and_curve_replay'] is True and result['curve_replay'] is True
        mathematical.curve(json.dumps(row['fixture']), result['assignment'])
    return dict(algebra_verified=int(result['algebra_verified']), curve_verified=int(result.get('curve_replay', False)))


def audit(report, folder):
    assert report['status'] == 'RECORDED_PENDING_AUDIT'
    assert report['timing_eligible'] is False and report['qualified_speedup'] is None
    commit = report['source_commit']
    assert len(commit) == 40 and set(commit) <= set('0123456789abcdef')
    prefix = str(HERE.relative_to(ROOT))+'/'
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit, '--', prefix], cwd=ROOT, text=True).splitlines()
    assert set(report['scripts']) == {Path(n).name for n in names if n.endswith('.py')}
    for name, value in report['scripts'].items():
        assert digest(subprocess.check_output(['git', 'show', commit+':'+prefix+name], cwd=ROOT)) == value
        assert digest((HERE/name).read_bytes()) == value
    baseline_report, baseline = frozen()
    assert report['plan'] == baseline_report['reference_plan']
    build = report['native_build']
    assert build['sources'] == baseline_report['build']['sources']
    for group in ('sources', 'generated', 'resources'):
        assert build['reference'][group] == baseline_report['build']['reference'][group]
    for name, value in build['sources'].items():
        assert digest((HERE.parent/'round110'/name).read_bytes()) == value
    for name, value in build['reference']['sources'].items():
        assert digest((ROOT/'experiments'/name).read_bytes()) == value
    assert len(report['rows']) == len(baseline) == 26
    seen, algebra, curve = set(), 0, 0
    for record in report['rows']:
        key = record['name'], record['sanitized']
        assert key in baseline and key not in seen
        seen.add(key)
        assert record['execution'] == 'completed' and record['exit_code'] == 0
        name = record['result']
        assert Path(name).name == name and not (Path(folder)/name).is_symlink()
        data = (Path(folder)/name).read_bytes()
        assert digest(data) == record['sha256']
        result = one(json.loads(data), baseline[key], folder)
        algebra += result['algebra_verified']
        curve += result['curve_verified']
    assert (algebra, curve) == (20, 18)
    return dict(status='PASS', rows=26, algebra_verified=algebra, curve_verified=curve,
        inconclusive=6, native_binaries_loaded=False, exact_native_reference_records=26,
        timing_eligible=False, qualified_speedup=None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.report.read_text()), args.report.parent)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)
