#!/usr/bin/env python3
"""Audit the frozen sparse-radix one-scalar cold panel from its raw serial-worker archive."""

from hashlib import sha256
from math import exp, isfinite, log
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import random
import statistics
import tarfile

HERE = Path(__file__).resolve().parent
JOB = '6e215db536eb48428fef1ed7d40174fb'
ROOT = '/workspace/bench-sources/'
STEMS = {'reference':'prime-j0-alt-horner-cold-prefetch',
         'sparse':'prime-j0-sparse-tau-radix'}
ARCHIVE = HERE/'sparse-vs-prefetch-cold-tier1-raw.tar.gz'
PROVENANCE = HERE/'sparse-vs-prefetch-cold-native-provenance.tar.gz'


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
    rules = load(HERE/'tier1-sparse-vs-prefetch-cold-cpu40-rules.json')
    planned = load(HERE/'tier1-sparse-vs-prefetch-cold-cpu40-manifest.json')
    launch = load(HERE/'tier1-sparse-vs-prefetch-cold-cpu40-launch.json')
    assert launch['job_id'] == JOB
    assert launch['manifest_sha256'] == digest(HERE/'tier1-sparse-vs-prefetch-cold-cpu40-manifest.json')
    assert launch['rules_sha256'] == digest(HERE/'tier1-sparse-vs-prefetch-cold-cpu40-rules.json')
    manifest, summary = load(folder/'manifest.json'),load(folder/'summary.json')
    assert manifest == planned
    assert manifest['repetitions'] == rules['repetitions'] == 16
    assert summary['expected_pairs'] == 48
    runs = [json.loads(line) for line in (folder/'runs.jsonl').read_text().splitlines()]
    pairs = [json.loads(line) for line in (folder/'pairs.jsonl').read_text().splitlines()]
    assert len(runs) == 96 and len(pairs) == 48
    artifacts = summary['artifact_sha256']
    panel = '/workspace/isolated-bench/panels/'
    assert artifacts[panel+'tier1-sparse-vs-prefetch-cold-cpu40-rules.json'] == launch['rules_sha256']
    assert artifacts[panel+'native_horner_cold_panel_overlay.py'] == digest(HERE/'native_horner_cold_panel_overlay.py')
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
            first = json.loads(fixture)['cases'][0]
            assert first['scalar_hex'] == '8b0040cf2f698515cf9a3882de34f01c34bc772dbf003d2b8984ad92875d036c'
            assert first['point_hex'] == rules['expected_point_hex']
    cases = {case['id']:case for case in manifest['cases']}
    run_lookup = {}
    invalid = []
    for serial,run in enumerate(runs,1):
        assert run['serial'] == serial
        case = cases[run['case']]
        assert run['command'] == case[run['variant']]
        assert run['binary_sha256'] == artifacts[run['command'][0]]
        assert (folder/run['stderr_file']).read_text() == ''
        fields = dict(word.split('=',1) for word in (folder/run['stdout_file']).read_text().split())
        assert fields == run['fields']
        assert fields['verified'] == '1' and fields['count'] == '1'
        assert fields['point'] == rules['expected_point_hex'] == case['expected_result']
        assert all(fields.get(k) == v for k,v in case['expected_fields'].items())
        expected_kind = 'sparse' if run['case']=='compare_sparse_cold' and run['variant']=='candidate' else 'reference'
        assert int(fields['retained_bytes']) == rules['table_bytes'][expected_kind]
        assert all(isfinite(float(fields[key])) and float(fields[key]) > 0
                   for key in ('preparation_ms','online_ms'))
        run_lookup[(run['repeat'],run['case'],run['variant'])] = run
        if run['status'] != 'valid' or run['issues'] or run['returncode'] != 0 or run['timed_out'] or not run['postflight']['ok']:
            invalid.append({'serial':serial,'status':run['status'],'issues':run['issues']})
    assert all(pair['case'] in cases for pair in pairs)
    pair_lookup = {(pair['repeat'],pair['case']):pair for pair in pairs}
    assert len(pair_lookup) == 48
    def cold(run):
        return float(run['fields']['preparation_ms'])+float(run['fields']['online_ms'])
    low,high = rules['aa_acceptance']
    aa_failures, ratios, reference, sparse = [],[],[],[]
    reference_online, sparse_online = [],[]
    for repeat in range(16):
        for name in ('cal_before','cal_after'):
            pair = pair_lookup[(repeat,name)]
            a,b = (run_lookup[(repeat,name,variant)] for variant in ('reference','candidate'))
            ratio = cold(a)/cold(b)
            if pair['status'] != 'valid' or not low <= ratio <= high:
                aa_failures.append({'repeat':repeat,'case':name,'cold_ratio':ratio,'pair_status':pair['status']})
        pair = pair_lookup[(repeat,'compare_sparse_cold')]
        a,b = (run_lookup[(repeat,'compare_sparse_cold',variant)] for variant in ('reference','candidate'))
        if pair['status']=='valid' and not pair['issues']:
            reference.append(cold(a)); sparse.append(cold(b)); ratios.append(cold(a)/cold(b))
            reference_online.append(float(a['fields']['online_ms']))
            sparse_online.append(float(b['fields']['online_ms']))
    bounds = interval(ratios)
    tier_gate = summary['status']=='completed' and summary['artifacts_stable'] and not invalid and not aa_failures and len(ratios)==16
    qualified = tier_gate and bounds is not None and (bounds[0]>1 or bounds[1]<1)
    return {'schema':1,'job_id':JOB,'measurement_tier':'tier1_instance',
            'runner_status':summary['status'],'artifact_stable':summary['artifacts_stable'],
            'completed_arms':len(runs),'completed_pairs':len(pairs),'invalid_arms':invalid,
            'aa_failures':aa_failures,'tier_gate_passed':tier_gate,
            'raw_archive_sha256':digest(ARCHIVE),
            'provenance_sha256':digest(PROVENANCE),
            'runs_sha256':digest(folder/'runs.jsonl'),'pairs_sha256':digest(folder/'pairs.jsonl'),
            'comparison':{'valid_pairs':len(ratios),
                          'reference_cold_ms_mean':statistics.mean(reference) if reference else None,
                          'sparse_cold_ms_mean':statistics.mean(sparse) if sparse else None,
                          'reference_online_ms_mean':statistics.mean(reference_online) if reference_online else None,
                          'sparse_online_ms_mean':statistics.mean(sparse_online) if sparse_online else None,
                          'descriptive_reference_over_sparse_cold_median':statistics.median(ratios) if ratios else None,
                          'paired_bootstrap95_by_repeat':bounds,
                          'aggregate_status':'qualified' if qualified else 'unknown_after_tier_gate',
                          'qualified_cold_ratio':statistics.median(ratios) if qualified else None,
                          'reference_retained_bytes':rules['table_bytes']['reference'],
                          'sparse_retained_bytes':rules['table_bytes']['sparse']}}


def main():
    with TemporaryDirectory(prefix='sparse-cold-audit-') as temporary:
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
