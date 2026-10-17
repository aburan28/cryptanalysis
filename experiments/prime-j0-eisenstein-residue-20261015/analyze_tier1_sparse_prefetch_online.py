#!/usr/bin/env python3
"""Audit each paired 122880-output prepared-table sparse-radix RunPod receipt."""

from hashlib import sha256
from math import exp, isfinite, log
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import random
import statistics
import tarfile

HERE = Path(__file__).resolve().parent
JOB = json.loads((HERE/'tier1-sparse-vs-prefetch-online-cpu40-launch.json').read_text())['job_id']
ROOT = '/workspace/bench-sources/'
STEMS = {'reference':'prime-j0-alt-radix-prefetch-long10',
         'sparse':'prime-j0-sparse-tau-radix'}
ARCHIVE = HERE/'sparse-vs-prefetch-online-tier1-raw.tar.gz'
PROVENANCE = HERE/'sparse-vs-prefetch-online-native-provenance.tar.gz'


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def interval(ratios):
    if len(ratios) != 16:
        return None
    logs = [log(value) for value in ratios]
    rng = random.Random(20261015)
    draws = sorted(exp(statistics.median(logs[rng.randrange(16)] for _ in range(16)))
                   for _ in range(10000))
    return [draws[250],draws[9749]]


def audit(folder):
    rules = load(HERE/'tier1-sparse-vs-prefetch-online-cpu40-rules.json')
    planned = load(HERE/'tier1-sparse-vs-prefetch-online-cpu40-manifest.json')
    launch = load(HERE/'tier1-sparse-vs-prefetch-online-cpu40-launch.json')
    assert launch['job_id'] == JOB
    assert launch['manifest_sha256'] == digest(HERE/'tier1-sparse-vs-prefetch-online-cpu40-manifest.json')
    assert launch['rules_sha256'] == digest(HERE/'tier1-sparse-vs-prefetch-online-cpu40-rules.json')
    manifest,summary = load(folder/'manifest.json'),load(folder/'summary.json')
    assert manifest == planned
    assert manifest['repetitions'] == rules['repetitions'] == 16
    assert summary['expected_pairs'] == 48
    runs = [json.loads(line) for line in (folder/'runs.jsonl').read_text().splitlines()]
    pairs = [json.loads(line) for line in (folder/'pairs.jsonl').read_text().splitlines()]
    assert len(runs) == 96 and len(pairs) == 48
    artifacts = summary['artifact_sha256']
    panel = '/workspace/isolated-bench/panels/'
    assert artifacts[panel+'tier1-sparse-vs-prefetch-online-cpu40-rules.json'] == launch['rules_sha256']
    assert artifacts[panel+'native_sparse_tau_radix_overlay.py'] == digest(HERE/'native_sparse_tau_radix_overlay.py')
    for label,stem in STEMS.items():
        for name,rel in (('front','src/bin/eisenstein_fixed.rs'),
                         ('windows','src/bin/eisenstein_fixed/unit_orbit_windows.rs'),
                         ('binary','target/release/eisenstein_fixed')):
            assert artifacts[ROOT+stem+'/'+rel] == rules['hashes'][label+'_'+name]
        assert artifacts[ROOT+stem+'/src/bin/mixed640_uniform_fixture.json'] == rules['fixture_sha256']
    with tarfile.open(PROVENANCE,'r:gz') as archive:
        for label,stem in STEMS.items():
            for name,rel in (('front','src/bin/eisenstein_fixed.rs'),
                             ('windows','src/bin/eisenstein_fixed/unit_orbit_windows.rs'),
                             ('binary','target/release/eisenstein_fixed')):
                assert sha256(archive.extractfile(stem+'/'+rel).read()).hexdigest() == rules['hashes'][label+'_'+name]
            fixture = archive.extractfile(stem+'/src/bin/mixed640_uniform_fixture.json').read()
            assert sha256(fixture).hexdigest() == rules['fixture_sha256']
    cases = {case['id']:case for case in manifest['cases']}
    run_lookup,invalid = {},[]
    for serial,run in enumerate(runs,1):
        assert run['serial'] == serial
        case = cases[run['case']]
        assert run['command'] == case[run['variant']]
        assert run['binary_sha256'] == artifacts[run['command'][0]]
        assert (folder/run['stderr_file']).read_text() == ''
        fields = dict(word.split('=',1) for word in (folder/run['stdout_file']).read_text().split())
        assert fields == run['fields']
        assert fields['verified'] == '1' and fields['count'] == '122880'
        assert fields['fixture_sha256'] == rules['fixture_sha256']
        assert fields['point'] == rules['expected_point_hex'] == case['expected_result']
        assert fields['scalar'] == '95b06c1557a0423404d994b331b00f68708a365398129dffcd000a8cce5e4d25'
        assert all(fields.get(k) == v for k,v in case['expected_fields'].items())
        expected_kind = 'sparse' if run['case']=='compare_sparse_online' and run['variant']=='candidate' else 'reference'
        assert int(fields['retained_bytes']) == rules['table_bytes'][expected_kind]
        assert isfinite(float(fields['online_ms'])) and float(fields['online_ms']) > 0
        assert isfinite(float(fields['preparation_ms'])) and float(fields['preparation_ms']) > 0
        run_lookup[(run['repeat'],run['case'],run['variant'])] = run
        if run['status'] != 'valid' or run['issues'] or run['returncode'] != 0 or run['timed_out'] or not run['postflight']['ok']:
            invalid.append({'serial':serial,'status':run['status'],'issues':run['issues']})
    pair_lookup = {(pair['repeat'],pair['case']):pair for pair in pairs}
    assert len(pair_lookup) == 48
    low,high = rules['aa_acceptance']
    aa_failures,ratios,reference,sparse = [],[],[],[]
    for repeat in range(16):
        for name in ('cal_before','cal_after'):
            pair = pair_lookup[(repeat,name)]
            a,b = (run_lookup[(repeat,name,variant)] for variant in ('reference','candidate'))
            ratio = a['online_ms']/b['online_ms']
            if pair['status'] != 'valid' or not low <= ratio <= high:
                aa_failures.append({'repeat':repeat,'case':name,'online_ratio':ratio,'pair_status':pair['status']})
        pair = pair_lookup[(repeat,'compare_sparse_online')]
        a,b = (run_lookup[(repeat,'compare_sparse_online',variant)] for variant in ('reference','candidate'))
        if pair['status']=='valid' and not pair['issues']:
            reference.append(a['online_ms']); sparse.append(b['online_ms'])
            ratios.append(a['online_ms']/b['online_ms'])
    bounds = interval(ratios)
    tier_gate = summary['status']=='completed' and summary['artifacts_stable'] and not invalid and not aa_failures and len(ratios)==16
    qualified = tier_gate and bounds is not None and (bounds[0]>1 or bounds[1]<1)
    return {'schema':1,'job_id':JOB,'measurement_tier':'tier1_instance',
            'runner_status':summary['status'],'artifact_stable':summary['artifacts_stable'],
            'completed_arms':len(runs),'completed_pairs':len(pairs),'invalid_arms':invalid,
            'aa_failures':aa_failures,'tier_gate_passed':tier_gate,
            'raw_archive_sha256':digest(ARCHIVE),'provenance_sha256':digest(PROVENANCE),
            'runs_sha256':digest(folder/'runs.jsonl'),'pairs_sha256':digest(folder/'pairs.jsonl'),
            'comparison':{'valid_pairs':len(ratios),
                          'reference_online_ms_mean':statistics.mean(reference) if reference else None,
                          'sparse_online_ms_mean':statistics.mean(sparse) if sparse else None,
                          'descriptive_reference_over_sparse_online_median':statistics.median(ratios) if ratios else None,
                          'paired_bootstrap95_by_repeat':bounds,
                          'aggregate_status':'qualified' if qualified else 'unknown_after_tier_gate',
                          'qualified_online_ratio':statistics.median(ratios) if qualified else None,
                          'reference_retained_bytes':rules['table_bytes']['reference'],
                          'sparse_retained_bytes':rules['table_bytes']['sparse']}}


def main():
    with TemporaryDirectory(prefix='sparse-prefetch-online-audit-') as temporary:
        with tarfile.open(ARCHIVE,'r:gz') as archive:
            for member in archive.getmembers():
                if member.isdir():
                    continue
                assert member.isfile() and member.name.startswith(JOB+'/')
                path = Path(temporary)/member.name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(archive.extractfile(member).read())
        print(json.dumps(audit(Path(temporary)/JOB),indent=2,sort_keys=True))


if __name__ == '__main__':
    main()
