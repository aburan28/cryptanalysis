#!/usr/bin/env python3
"""Audit the frozen checkpoint5 repeated-stream cold panel from its raw serial-worker archive."""

from hashlib import sha256
from math import exp, isfinite, log
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import random
import statistics
import tarfile

HERE = Path(__file__).resolve().parent
JOB = json.loads((HERE/'tier1-checkpoint5-repeat4-cold-cpu40-launch.json').read_text())['job_id']
ROOT = '/workspace/bench-sources/'
STEMS = {'reference':'prime-j0-sparse-tau-repeat',
         'checkpoint':'prime-j0-sparse-checkpoint5-repeat'}
ARCHIVE = HERE/'checkpoint5-repeat4-cold-tier1-raw.tar.gz'
PROVENANCE = HERE/'checkpoint5-repeat8-native-provenance.tar.gz'


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
    rules = load(HERE/'tier1-checkpoint5-repeat4-cold-cpu40-rules.json')
    planned = load(HERE/'tier1-checkpoint5-repeat4-cold-cpu40-manifest.json')
    launch = load(HERE/'tier1-checkpoint5-repeat4-cold-cpu40-launch.json')
    assert launch['job_id'] == JOB
    assert launch['manifest_sha256'] == digest(HERE/'tier1-checkpoint5-repeat4-cold-cpu40-manifest.json')
    assert launch['rules_sha256'] == digest(HERE/'tier1-checkpoint5-repeat4-cold-cpu40-rules.json')
    manifest, summary = load(folder/'manifest.json'),load(folder/'summary.json')
    assert manifest == planned
    assert manifest['repetitions'] == rules['repetitions'] == 16
    assert summary['expected_pairs'] == 48
    runs = [json.loads(line) for line in (folder/'runs.jsonl').read_text().splitlines()]
    pairs = [json.loads(line) for line in (folder/'pairs.jsonl').read_text().splitlines()]
    assert len(runs) == 96 and len(pairs) == 48
    artifacts = summary['artifact_sha256']
    panel = '/workspace/isolated-bench/panels/'
    assert artifacts[panel+'tier1-checkpoint5-repeat4-cold-cpu40-rules.json'] == launch['rules_sha256']
    assert artifacts[panel+'native_checkpointed_sparse_overlay.py'] == rules['hashes']['base_overlay'] == digest(HERE/'native_checkpointed_sparse_overlay.py')
    assert artifacts[panel+'native_checkpointed_sparse_width5_overlay.py'] == rules['hashes']['overlay'] == digest(HERE/'native_checkpointed_sparse_width5_overlay.py')
    assert artifacts[panel+'native_alt_horner_repeat_overlay.py'] == rules['hashes']['repeat_overlay'] == digest(HERE/'native_alt_horner_repeat_overlay.py')
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
            frozen_cases = json.loads(fixture)['cases']
            assert len(frozen_cases) == rules['expected_unique_points']
            assert frozen_cases[-1]['point_hex'] == rules['expected_point_hex']
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
        assert fields['verified'] == '1'
        assert fields['count'] == str(rules['expected_count'])
        assert fields['unique_points'] == str(rules['expected_unique_points'])
        assert fields['passes'] == str(rules['expected_passes'])
        assert fields['point'] == rules['expected_point_hex'] == case['expected_result']
        assert all(fields.get(k) == v for k,v in case['expected_fields'].items())
        expected_kind = 'checkpoint' if run['case']=='compare_checkpoint5_repeat4_cold' and run['variant']=='candidate' else 'reference'
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
    aa_failures, ratios, reference, checkpoint = [],[],[],[]
    reference_online, checkpoint_online = [],[]
    for repeat in range(16):
        for name in ('cal_before','cal_after'):
            pair = pair_lookup[(repeat,name)]
            a,b = (run_lookup[(repeat,name,variant)] for variant in ('reference','candidate'))
            ratio = cold(a)/cold(b)
            if pair['status'] != 'valid' or not low <= ratio <= high:
                aa_failures.append({'repeat':repeat,'case':name,'cold_ratio':ratio,'pair_status':pair['status']})
        pair = pair_lookup[(repeat,'compare_checkpoint5_repeat4_cold')]
        a,b = (run_lookup[(repeat,'compare_checkpoint5_repeat4_cold',variant)] for variant in ('reference','candidate'))
        if pair['status']=='valid' and not pair['issues']:
            reference.append(cold(a)); checkpoint.append(cold(b)); ratios.append(cold(a)/cold(b))
            reference_online.append(float(a['fields']['online_ms']))
            checkpoint_online.append(float(b['fields']['online_ms']))
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
                          'checkpoint_cold_ms_mean':statistics.mean(checkpoint) if checkpoint else None,
                          'reference_online_ms_mean':statistics.mean(reference_online) if reference_online else None,
                          'checkpoint_online_ms_mean':statistics.mean(checkpoint_online) if checkpoint_online else None,
                          'descriptive_reference_over_checkpoint_cold_median':statistics.median(ratios) if ratios else None,
                          'paired_bootstrap95_by_repeat':bounds,
                          'aggregate_status':'qualified' if qualified else 'unknown_after_tier_gate',
                          'qualified_cold_ratio':statistics.median(ratios) if qualified else None,
                          'reference_retained_bytes':rules['table_bytes']['reference'],
                          'checkpoint_retained_bytes':rules['table_bytes']['checkpoint']}}


def main():
    with TemporaryDirectory(prefix='checkpoint5-cold-audit-') as temporary:
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
