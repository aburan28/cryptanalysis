"""Native-free matrix replay, strict-size proof checks and final ideal verification."""
import argparse
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(HERE.parent/'round108'), str(HERE.parent/'round109')]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


oracle = load('early_oracle112', HERE/'matrix_model.py')
# The legacy audit imports its own matrix oracle by the unqualified name.
# Put its reference path first after explicitly loading ours.
sys.path.insert(0, str(HERE.parent/'round108'))
mathematical = load('math109_for112', HERE.parent/'round109/audit.py')
reference_audit = load('audit111_for112', HERE.parent/'round111/audit.py')
from proof_reader import decode


def digest(data):
    return hashlib.sha256(data).hexdigest()


def deterministic(value):
    if isinstance(value, dict):
        return {k: deterministic(v) for k, v in value.items() if not k.endswith('seconds')}
    if isinstance(value, list):
        return [deterministic(v) for v in value]
    return value


@lru_cache(maxsize=32)
def matrix(encoded, mode):
    c = json.loads(encoded)
    return oracle.model(c['nvars'], c['equations'],
        min(c['nvars'], 6 if c['boundary'] == 'pdp' else 2), 2,
        early_mode=mode, max_work=20000000, max_nodes=2000000, max_rows=4096,
        packed_masks=list(dict.fromkeys(m for row in c['equations'] for m in row)))


def one(row, expected, folder):
    c, r = row['fixture'], row['result']
    mode = row['early_mode']
    assert type(mode) is int and mode in (0, 1)
    assert row['name'] == expected['name'] and c == expected['fixture']
    assert row['sanitized'] is expected['sanitized']
    assert r['early_parity_mode'] == mode
    for value in (row, r):
        assert value['timing_eligible'] is False and value['qualified_speedup'] is None
        assert type(value['wall_ns']) is int and value['wall_ns'] >= 0
        assert all(type(v) is int and v >= 0 for v in value['phases'].values())
        assert sum(value['phases'].values()) == value['wall_ns']
    assert r['wall_ns'] <= row['phases']['algebra_and_certificate_ns']
    assert 0 <= r['work'] <= 80000000 and 0 <= r['check_work'] <= 200000000
    assert r['work'] == sum(a['stats']['work'] for a in r['attempts'])
    assert r['check_work'] == sum(a.get('certificate', {}).get('stats', {}).get('work', 0) for a in r['attempts'])
    assert r['complete'] is r['algebra_verified']
    first = r['attempts'][0]
    assert first['kind'] == 'macaulay'
    exact = matrix(json.dumps(c, sort_keys=True), mode)
    for key in ('stats', 'parity', 'block', 'early'):
        assert deterministic(first[key]) == exact[key], (row['name'], mode, key)
    if mode == 0:
        # Same late-compression kernel and query as the frozen reference.
        for key in ('status', 'verified', 'algebra_verified', 'work', 'check_work'):
            assert r[key] == expected[key], (row['name'], key)
        for a, b in zip(r['attempts'], expected['attempts']):
            assert a['kind'] == b['kind']
            assert deterministic(a.get('certificate')) == b.get('certificate')
    if first['early']['bound_selected']:
        ordinary = matrix(json.dumps(c, sort_keys=True), 0)
        # A complete late-parity model may exhaust its final rewrite budget.
        # Independently recover the ordinary pruned graph at a generous cap.
        raw = oracle.raw_model(c['nvars'], c['equations'],
            min(c['nvars'], 6 if c['boundary'] == 'pdp' else 2), 2,
            minimal=True, block=True, max_work=100000000)
        assert len(exact['proof']['nodes']) < first['early']['active_nodes'] <= len(raw['proof']['nodes'])
        assert first['early']['prune_visits'] == 0 and first['parity']['selected'] == 1
    if r['algebra_verified']:
        assert r['certificate']['verified'] is True
        artifact = r['proof_artifact']
        assert Path(artifact['path']).name == artifact['path']
        path = Path(folder)/artifact['path']
        assert not path.is_symlink()
        data = path.read_bytes()
        assert digest(data) == artifact['sha256'] and len(data) == artifact['bytes']
        proof = decode(data)
        assert len(proof['nodes']) == artifact['nodes'] and len(proof['outputs']) == artifact['outputs']
        mathematical.mathematics(json.dumps([c['nvars'], c['equations'], r['basis'], proof]))
        if expected['algebra_verified']:
            assert r['basis'] == expected['basis'] and proof == expected['proof']
        if c['boundary'] == 'pdp':
            assert r['status'] == 'solved' and r['verified'] is True
            assert r['reference_equations_and_curve_replay'] is True and r['curve_replay'] is True
            mathematical.curve(json.dumps(c), r['assignment'])
    else:
        assert not {'basis', 'proof', 'proof_artifact', 'certificate'} & r.keys()
        assert r['verified'] is False
    for attempt in r['attempts'][1:]:
        if attempt['kind'] == 'seeded-f4':
            s = attempt['stats']
            assert s['work'] == attempt['producer']['work']+attempt['composition']['work']+s['bridge_work']+s['scan_work']
            assert s['f4_started'] in (0, 1) and s['composition_started'] in (0, 1)
    return dict(algebra_verified=int(r['algebra_verified']), curve_verified=int(r.get('curve_replay', False)),
        selected=int(bool(first['early']['bound_selected'])))


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
    build = report['build']
    assert build['schema'] == 'early-parity-build/1' and len(build['binaries']) == 2
    for name, value in build['sources'].items():
        assert digest((HERE/name).read_bytes()) == value
    baseline_report, baseline = reference_audit.frozen()
    assert report['plan'] == baseline_report['reference_plan']
    reference = build['reference']
    assert reference['sources'] == baseline_report['build']['sources']
    for group in ('sources', 'generated', 'resources'):
        assert reference['reference'][group] == baseline_report['build']['reference'][group]
    assert len(report['rows']) == 52
    seen, summaries = set(), {str(mode): dict(rows=0, algebra_verified=0, curve_verified=0, selected=0) for mode in (0, 1)}
    for record in report['rows']:
        key = record['name'], record['sanitized'], record['early_mode']
        assert key not in seen and key[:2] in baseline
        seen.add(key)
        assert record['execution'] == 'completed' and record['exit_code'] == 0
        name = record['result']
        assert Path(name).name == name and not (Path(folder)/name).is_symlink()
        data = (Path(folder)/name).read_bytes()
        assert digest(data) == record['sha256']
        result = one(json.loads(data), baseline[key[:2]], folder)
        summary = summaries[str(key[2])]
        summary['rows'] += 1
        for field, value in result.items(): summary[field] += value
        print('AUDITED', *key, flush=True)
    assert summaries['0']['algebra_verified'] == 20 and summaries['0']['curve_verified'] == 18
    assert summaries['1']['algebra_verified'] >= summaries['0']['algebra_verified']
    return dict(status='PASS', rows=52, modes=summaries, native_binaries_loaded=False,
        timing_eligible=False, qualified_speedup=None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.report.read_text()), args.report.parent)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)
