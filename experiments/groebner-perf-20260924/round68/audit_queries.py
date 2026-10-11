"""Check original ANF identities and exact bases without loading native libraries."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'round44'))
from tagged_reference import certify_roots
sys.path.insert(0, str(HERE.parent/'round27'))
from reference import verify_basis
from query_cases import query_modes, check_accounting


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    report = json.loads(gzip.decompress(args.input.read_bytes()))
    assert report['schema'] == 'shared-producer-transform-query-validation/1' and report['status'] == 'PASS'
    assert report['validator_sha256'] == sha(HERE/'validate_queries.py')
    fixture = HERE.parent/'round40/fixtures/inputs.json.gz'
    assert sha(fixture) == report['fixture_sha256']
    fixtures = {item['name']: item for item in json.loads(gzip.decompress(fixture.read_bytes()))}
    for path, digest in report['executed_bindings'].items(): assert sha(Path(path)) == digest, path
    modes = query_modes(report['metal']['status'] == 'AVAILABLE')
    expected = {(name, backend, transform_backend, sanitizer, preparation, 'prepared', producer_transform)
                for name in fixtures for backend, transform_backend, sanitizer, producer_transform in modes
                for preparation in ('serial', 'prepared', 'overlap')}
    fields = ('name', 'backend', 'transform_backend', 'sanitizer', 'preparation', 'constant_identity', 'producer_transform')
    seen, audited, records = set(), {}, []
    with args.output.with_suffix('.jsonl').open('x') as journal:
        for row in report['queries']:
            key = tuple(row[k] for k in fields)
            assert key in expected and key not in seen
            seen.add(key)
            item, answer = fixtures[row['name']], row['result']
            assert row['workload_sha256'] == item['workload_sha256']
            if answer['status'] == 'unsupported':
                assert row['backend'] == 'metal' and item['n'] > 32 and row['producer_transform'] != 'cpu'
                assert row['attempted_query'] is False and row['wall_ns'] is None
                assert answer['complete'] is False and answer['verified'] is False
                setup = report['unsupported_setups'][row['setup_failure_id']]
                shape = [item[key] for key in ('n', 'mod', 'b', 'm', 'ell')]
                setup_id = hashlib.sha256(json.dumps([shape, row['backend'], row['transform_backend'],
                                                     row['sanitizer'], row['producer_transform']]).encode()).hexdigest()
                assert setup_id == row['setup_failure_id'] and setup['shape'] == shape
                assert setup['detail'] == answer['detail'] == 'producer transform requires a compatible Metal producer'
                for field in ('backend', 'transform_backend', 'sanitizer', 'producer_transform'):
                    assert setup[field] == row[field]
                assert setup['queries_executed'] == 0 and setup['wall_ns'] >= 0
                record = {key: row[key] for key in fields}
                record.update(status='unsupported', exact_basis_verified=False, attempted_query=False,
                              setup_failure_id=setup_id)
                records.append(record)
                journal.write(json.dumps(record, separators=(',', ':'))+'\n'); journal.flush()
                continue
            assert row['attempted_query'] is True
            assert answer['status'] == 'solved' and answer['verified']
            raw = base64.b64decode(report['proofs'][answer['proof_sha256']], validate=True)
            assert hashlib.sha256(raw).hexdigest() == answer['proof_sha256']
            audit_key = item['name'], answer['proof_sha256'], answer['proof_byteorder'], json.dumps(answer['basis_terms'])
            if audit_key not in audited:
                roots, _, _, _, _ = certify_roots(2*item['ell'], item['ell'], item['n'],
                    tuple(tuple(v) for v in item['reference_anf']), raw, answer['proof_byteorder'])
                roots = list(roots)
                assert verify_basis(item['nvars'], item['reference_anf'], roots, answer['basis_terms'], len(roots))
                audited[audit_key] = roots
                print('ORIGINAL_ANF_PASS', item['name'], flush=True)
            roots = audited[audit_key]
            check_accounting(answer, item, row['backend'], row['producer_transform'])
            cert = answer['basis_certificate']
            assert cert['solutions'] == roots and answer['assignment'] in roots
            constant = cert['constant_identity_stats']
            assert constant['requested'] == ('original', 'prepared', 'folded').index(row['constant_identity'])
            assert constant['used'] == int(row['constant_identity'] != 'original')
            words = (1 << (2*item['ell']))*((item['n']+63)//64) if row['constant_identity'] != 'original' else 0
            assert constant['prepared_words'] == words
            assert constant['workspace_bytes'] == words*(4 if item['n'] <= 32 else 8)
            assert constant['features'] == 1 + item['ell']*(item['ell']+1)//2
            assert constant['avoided_parities'] == cert['symmetry_check_stats']['avoided_constant_parities']
            device = cert['device_transform_stats']
            assert device['requested'] == device['executed'] == int(row['transform_backend'] != 'cpu')
            if device['executed']:
                slices = (1 + item['ell'] * (item['ell']+1)//2) * ((item['n']+63)//64)
                size = slices * (1 << (2*item['ell'])) * (4 if item['n'] <= 32 else 8)
                assert device['input_bytes'] == device['output_bytes'] == device['scratch_bytes'] == size
                low = min(2*item['ell'], 5 if item['n'] <= 32 else 4) if row['transform_backend'] == 'metal_simd' else 0
                assert device['fused_stages'] == low
                assert device['dispatches'] == 2 * item['ell'] - low + int(low > 0)
                assert cert['transform_check_stats']['actual_xors'] == slices * item['ell'] * (1 << (2*item['ell']))
            schedule = answer['preparation_schedule']
            assert schedule['mode'] == row['preparation'] and schedule['drained']
            assert cert['preparation_stats']['used'] == int(row['preparation'] != 'serial')
            assert sum(answer['phases_ns'].values()) == answer['complete_query_ns']
            record = {k: row[k] for k in fields}
            record.update(proof_sha256=answer['proof_sha256'], roots=roots, exact_basis_verified=True)
            records.append(record)
            journal.write(json.dumps(record, separators=(',', ':'))+'\n'); journal.flush()
    assert seen == expected
    unavailable = [row for row in report['queries'] if not row['attempted_query']]
    assert len(unavailable) == (24 if report['metal']['status'] == 'AVAILABLE' else 0)
    assert len(report['unsupported_setups']) == (8 if unavailable else 0)
    assert set(report['unsupported_setups']) == {row['setup_failure_id'] for row in unavailable}
    for setup_id in report['unsupported_setups']:
        assert sum(row['setup_failure_id'] == setup_id for row in unavailable) == 3
    for path, digest in report['executed_bindings'].items(): assert sha(Path(path)) == digest, path
    output = {'status': 'PASS', 'input_sha256': sha(args.input), 'records': records,
              'independent_proofs': len(audited), 'timing_eligible': False,
              'scope': 'Original polynomial identities, affine ranks, complete residual assignments and exact reduced Boolean bases; audit-only reuse outside all query timing.'}
    args.output.write_text(json.dumps(output, indent=2)+'\n')
    print('INDEPENDENT_ORIGINAL_ANF_AUDIT_PASS', len(records), 'queries;', len(audited), 'proofs', flush=True)


if __name__ == '__main__':
    main()
