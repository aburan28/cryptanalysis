#!/usr/bin/env python3
"""Audit the rotated-radix full-fixture serial exact-output replay."""

from hashlib import sha256
from pathlib import Path
import json
import tarfile

from check_secp256k1_tau_generator import G, N, mul

HERE = Path(__file__).resolve().parent
STEM = 'tier1-tau32-rotated-step-full-replay-cpu40'
RAW = HERE / 'tau32-rotated-step-full-replay-raw.tar.gz'
PROVENANCE = HERE / 'tau32-rotated-step-native-provenance.tar.gz'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    launch = json.loads((HERE / f'{STEM}-launch.json').read_text())
    planned = json.loads((HERE / f'{STEM}-manifest.json').read_text())
    rules = json.loads((HERE / f'{STEM}-rules.json').read_text())
    assert digest(RAW) == launch['raw_archive_sha256']
    assert digest(HERE / f'{STEM}-manifest.json') == launch['manifest_sha256']
    assert digest(HERE / f'{STEM}-rules.json') == launch['rules_sha256']
    job = launch['job_id']
    with tarfile.open(PROVENANCE, 'r:gz') as provenance:
        prefix = 'bench-sources/prime-j0-sparse-tau32-rotated-step/'
        fixture = provenance.extractfile(prefix + 'src/bin/mixed640_uniform_fixture.json').read()
        assert sha256(fixture).hexdigest() == rules['fixture_sha256']
        cases = json.loads(fixture)['cases']
        assert len(cases) == rules['expected_count'] == 12288
        last = cases[-1]
        point = mul(int(last['scalar_hex'], 16) % N, G)
        replayed_last = ':'.join(f'{coordinate:064x}' for coordinate in point)
        assert replayed_last == last['point_hex'] == rules['expected_last_point_hex']
        front = provenance.extractfile(prefix + 'src/bin/eisenstein_fixed.rs').read().decode()
        assert 'assert_eq!(point,inputs[index].1,"pilot case {index}")' in front
        binary = provenance.extractfile('bench-target-tau32-rotated-step/release/eisenstein_fixed').read()
        assert sha256(binary).hexdigest() == launch['binary_sha256']
        assert digest(PROVENANCE) == launch['provenance_sha256']
    with tarfile.open(RAW, 'r:gz') as archive:
        def read(name):
            return archive.extractfile(job + '/' + name).read()

        manifest = json.loads(read('manifest.json'))
        summary = json.loads(read('summary.json'))
        runs = [json.loads(line) for line in read('runs.jsonl').splitlines()]
        pairs = [json.loads(line) for line in read('pairs.jsonl').splitlines()]
        assert manifest == planned
        assert planned['cases'][0]['reference'] == planned['cases'][0]['candidate']
        assert planned['cases'][0]['candidate'][1] == '--pilot-alt-rotated-step'
        assert summary['status'] == 'completed'
        assert summary['artifacts_stable']
        assert summary['measurement_tier'] == 'tier1_instance'
        assert len(runs) == 2 and len(pairs) == 1
        assert pairs[0]['status'] == 'valid' and not pairs[0]['issues']
        assert summary['artifact_sha256'][planned['cases'][0]['reference'][0]] == launch['binary_sha256']
        assert summary['artifact_sha256']['/workspace/isolated-bench/panels/' + f'{STEM}-rules.json'] == launch['rules_sha256']
        results = []
        for serial, run in enumerate(runs, 1):
            assert run['serial'] == serial
            assert run['status'] == 'valid' and not run['issues']
            assert run['returncode'] == 0 and not run['timed_out']
            assert run['command'] == planned['cases'][0][run['variant']]
            assert run['postflight']['ok'] and run['binary_sha256'] == launch['binary_sha256']
            assert read(run['stderr_file']) == b''
            fields = dict(word.split('=', 1) for word in read(run['stdout_file']).decode().split())
            assert fields == run['fields']
            assert fields['verified'] == '1' and int(fields['count']) == 12288
            assert fields['point'] == replayed_last
            assert float(fields['preparation_ms']) == 0
            assert 0 < int(fields['max_selected']) <= 22
            results.append({'variant': run['variant'], 'online_ms': float(fields['online_ms']),
                            'max_selected': int(fields['max_selected'])})
    receipt = {'schema': 1, 'job_id': job, 'measurement_tier': 'tier1_instance',
               'full_fixture_outputs_verified_per_arm': 12288,
               'independent_last_scalar_replay': True, 'valid_arms': len(runs),
               'valid_pairs': len(pairs), 'artifacts_stable': True,
               'binary_sha256': launch['binary_sha256'], 'raw_archive_sha256': digest(RAW),
               'provenance_sha256': digest(PROVENANCE), 'results': results,
               'speedup_claim': None}
    (HERE / f'{STEM}-audit.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
