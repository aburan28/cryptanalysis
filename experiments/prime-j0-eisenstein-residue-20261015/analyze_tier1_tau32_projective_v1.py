#!/usr/bin/env python3
"""Classify the frozen v1 projective panels as A/A after a dispatch error."""

from hashlib import sha256
from pathlib import Path
import json
import tarfile

HERE = Path(__file__).resolve().parent


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def audit(count):
    stem = f'tier1-tau32-projective-{count}-cpu40'
    launch = json.loads((HERE / f'{stem}-launch.json').read_text())
    manifest = json.loads((HERE / f'{stem}-manifest.json').read_text())
    rules = json.loads((HERE / f'{stem}-rules.json').read_text())
    raw = HERE / f'tau32-projective-{count}-raw.tar.gz'
    assert digest(raw) == launch['raw_archive_sha256']
    assert digest(HERE / f'{stem}-manifest.json') == launch['manifest_sha256']
    assert digest(HERE / f'{stem}-rules.json') == launch['rules_sha256']
    assert digest(HERE / 'tau32-projective-native-provenance.tar.gz') == launch['provenance_sha256']
    assert all(case['reference'] == case['candidate'] for case in manifest['cases'])
    assert all(case['reference'][1] == '--pilot-alt-on-demand' for case in manifest['cases'])
    job = launch['job_id']
    with tarfile.open(raw, 'r:gz') as archive:
        def read(name):
            return archive.extractfile(job + '/' + name).read()

        assert json.loads(read('manifest.json')) == manifest
        summary = json.loads(read('summary.json'))
        runs = [json.loads(line) for line in read('runs.jsonl').splitlines()]
        pairs = [json.loads(line) for line in read('pairs.jsonl').splitlines()]
        assert summary['status'] == 'completed' and summary['artifacts_stable']
        assert len(runs) == 96 and len(pairs) == 48
        assert all(pair['status'] == 'valid' and not pair['issues'] for pair in pairs)
        assert summary['artifact_sha256']['/workspace/isolated-bench/panels/' + stem + '-rules.json'] == launch['rules_sha256']
        for run in runs:
            assert run['status'] == 'valid' and not run['issues']
            assert run['returncode'] == 0 and not run['timed_out']
            assert run['command'] == manifest['cases'][('cal_before','compare_demand_cold','cal_after').index(run['case'])][run['variant']]
            fields = dict(word.split('=', 1) for word in read(run['stdout_file']).decode().split())
            assert fields == run['fields']
            assert fields['verified'] == '1' and int(fields['count']) == count
            assert fields['point'] == rules['expected_point_hex']
            assert read(run['stderr_file']) == b''
    receipt = {'schema': 1, 'job_id': job, 'measurement_tier': 'tier1_instance',
               'completed_arms': 96, 'completed_pairs': 48,
               'artifact_stable': True, 'raw_archive_sha256': digest(raw),
               'provenance_sha256': launch['provenance_sha256'],
               'classification': 'A/A control only',
               'comparison_status': 'invalid_plan_candidate_equals_reference',
               'speedup_claim': None}
    (HERE / f'{stem}-audit.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps([audit(1), audit(128)], indent=2, sort_keys=True))
