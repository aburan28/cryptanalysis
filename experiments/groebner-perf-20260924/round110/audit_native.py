"""Native-free exact reference comparison and fresh original-input math replay."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REFERENCE = HERE.parent/'round109'
sys.path.insert(0, str(REFERENCE))
spec = importlib.util.spec_from_file_location('seeded_reference_audit', REFERENCE/'audit.py')
reference_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference_audit)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source(commit, path):
    assert len(commit) == 40 and set(commit) <= set('0123456789abcdef')
    return subprocess.check_output(['git', 'show', commit+':'+path], cwd=ROOT)


def frozen_reference():
    receipt = json.loads((REFERENCE/'archive.json').read_text())
    path = REFERENCE/'results.tar.gz'
    assert digest(path.read_bytes()) == receipt['sha256'] == 'd6b5f9cf321100d5cd15f18500a059df89c5618f10e5b2a1bcfed914af74a52f'
    with tarfile.open(path, 'r:gz') as archive:
        manifest = json.load(archive.extractfile('manifest.json'))
        def read(name):
            entry = manifest['logical_files']['seeded-completion-validation-v2/discovery/'+name]
            data = archive.extractfile('objects/'+entry['sha256']).read()
            assert len(data) == entry['size'] and digest(data) == entry['sha256']
            return json.loads(data)
        report = read('report.json')
        records = {(row['name'], row['sanitized']): read(row['result']) for row in report['rows']}
    return report, records


def audit(report, folder):
    folder = Path(folder)
    assert report['status'] == 'RECORDED_PENDING_AUDIT' and report['native_integration'] is True
    assert report['timing_eligible'] is False and report['qualified_speedup'] is None
    commit = report['source_commit']
    prefix = str(HERE.relative_to(ROOT))+'/'
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit, '--', prefix], cwd=ROOT, text=True).splitlines()
    expected = {Path(name).name for name in names if name.endswith('.py') and Path(name).parent == Path(prefix)}
    assert set(report['scripts']) == expected
    for name, value in report['scripts'].items():
        assert digest(source(commit, prefix+name)) == value
    build = report['build']
    assert build['schema'] == 'native-seeded-build/1' and len(build['binaries']) == len(build['commands']) == 2
    for name, value in build['sources'].items():
        assert Path(name).name == name
        data = source(build['source_commit'], prefix+name)
        assert digest(data) == value
        assert source(commit, prefix+name) == data
    for name, value in build['reference']['sources'].items():
        assert '..' not in Path(name).parts and not Path(name).is_absolute()
        assert digest(source(build['source_commit'], 'experiments/'+name)) == value
        assert digest((ROOT/'experiments'/name).read_bytes()) == value
    assert build['engine_sha256'] == build['reference']['generated']['engine.inc']
    assert build['timing_eligible'] is False and build['qualified_speedup'] is None
    baseline_report, baseline = frozen_reference()
    assert report['reference_plan'] == baseline_report['reference_plan']
    assert build['reference']['sources'] == baseline_report['reference_build']['sources']
    assert build['reference']['generated'] == baseline_report['reference_build']['generated']
    assert build['reference']['resources'] == baseline_report['reference_build']['resources']
    assert len(report['rows']) == len(baseline_report['rows']) == 26
    normalized_report = copy.deepcopy(baseline_report)
    scan_work, native_successes = {}, 0
    with tempfile.TemporaryDirectory(dir=folder) as temporary:
        normalized = Path(temporary)
        for row, original_row, normalized_row in zip(report['rows'], baseline_report['rows'], normalized_report['rows']):
            key = row['name'], row['sanitized']
            assert key == (original_row['name'], original_row['sanitized'])
            assert row['execution'] == 'completed' and row['exit_code'] == 0
            name = row['result']
            assert Path(name).name == name and not (folder/name).is_symlink()
            data = (folder/name).read_bytes()
            assert digest(data) == row['sha256']
            r = json.loads(data)
            assert r['native_integration'] is True and r['scan_work'] >= 0
            assert r['work'] <= 80000000 and r['check_work'] <= 200000000
            expected = baseline[key]
            assert r['work'] == expected['work']+r['scan_work']
            if 'native_stats' in r:
                stats, packed = r['native_stats'], r['packed_scan']
                fixture = r['fixture']
                assert packed['nvars'] == fixture['nvars'] and packed['equations'] == len(fixture['equations'])
                # These frozen inputs contain precisely the nonzero coefficient
                # support. Order may differ; every coefficient must match exactly.
                coefficients = {}
                for i, equation in enumerate(fixture['equations']):
                    for mask in equation: coefficients[mask] = coefficients.get(mask, 0) ^ (1 << i)
                coefficients = {m: c for m, c in coefficients.items() if c}
                assert len(set(packed['masks'])) == len(packed['masks']) == len(coefficients)
                limbs = (packed['equations']+63)//64
                assert len(packed['coefficients']) == limbs*len(packed['masks'])
                actual = {mask: sum(packed['coefficients'][j*limbs+i] << (64*i) for i in range(limbs))
                    for j, mask in enumerate(packed['masks'])}
                assert actual == coefficients
                charge = packed['equations'] + len(packed['masks'])*(1+limbs)+2*sum(c.bit_count() for c in coefficients.values())
                assert r['scan_work'] == stats['scan_work'] == charge
                assert stats['work'] == r['work']-r['attempts'][0]['stats']['work']
                assert stats['bridge_work'] == r['bridge_work']
                assert stats['reserved_seed_nodes'] == r['attempts'][1]['reserved_seed_nodes']
                assert stats['f4_started'] == stats['composition_started'] == 1 and stats['status'] == 0
                assert r['algebra_verified'] is True and r['verified'] is True
                native_successes += 1
                scan_work[str(key)] = charge
            else:
                assert r['scan_work'] == 0 and 'packed_scan' not in r
            projected = {k: v for k, v in r.items() if k not in ('scan_work', 'packed_scan', 'native_stats')}
            projected['native_integration'] = False
            projected['work'] -= r['scan_work']
            assert projected == expected, key
            # Reuse only the reference's metadata envelope and mathematical
            # checker. Every normalized polynomial/proof/counter comes from
            # this native run; the extra scan charge was checked above.
            encoded = (json.dumps(projected, indent=2)+'\n').encode()
            (normalized/normalized_row['result']).write_bytes(encoded)
            normalized_row['sha256'] = digest(encoded)
        mathematical = reference_audit.audit(normalized_report, normalized)
    assert native_successes == 4
    assert mathematical['rows'] == 26 and mathematical['process_failures'] == 0
    return dict(status='PASS', native_binaries_loaded=False, native_seeded_successes=native_successes,
        exact_reference_records=26, extra_scan_work=scan_work, mathematical_audit=mathematical,
        timing_eligible=False, qualified_speedup=None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.report.read_text()), args.report.parent)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)
