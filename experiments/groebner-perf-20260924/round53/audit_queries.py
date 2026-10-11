"""Offline original-ANF proof and basis audit; independent of all native libraries."""
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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = json.loads(gzip.decompress(args.input.read_bytes()))
    assert report['schema'] == 'independent-preparation-validation/1' and report['status'] == 'PASS'
    assert report['validator_sha256'] == sha(HERE/'validate_native.py')
    fixture = HERE.parent/'round40/fixtures/inputs.json.gz'
    assert sha(fixture) == report['fixture_sha256']
    fixtures = {i['name']: i for i in json.loads(gzip.decompress(fixture.read_bytes()))}
    for path, digest in report['executed_bindings'].items():
        assert sha(Path(path)) == digest, path
    modes = [('cpu', False), ('cpu', True)]
    if report['metal']['status'] == 'AVAILABLE':
        modes.append(('metal', False))
    expected = {(name, backend, sanitizer, symmetry, transform, preparation)
                for name in fixtures for backend, sanitizer in modes
                for symmetry in (False, True) for transform in ('full', 'tile16')
                for preparation in ('serial', 'prepared', 'overlap')}
    records, seen, proofs, audited = [], set(), set(), {}
    with args.output.with_suffix('.jsonl').open('x') as journal:
        for row in report['queries']:
            key = tuple(row[k] for k in ('name', 'backend', 'sanitizer', 'symmetry', 'transform', 'preparation'))
            assert key in expected and key not in seen
            seen.add(key)
            item, answer = fixtures[row['name']], row['result']
            assert row['workload_sha256'] == item['workload_sha256']
            assert answer['status'] == 'solved' and answer['verified']
            raw = base64.b64decode(report['proofs'][answer['proof_sha256']], validate=True)
            assert hashlib.sha256(raw).hexdigest() == answer['proof_sha256']
            audit_key = item['name'], answer['proof_sha256'], answer['proof_byteorder'], json.dumps(answer['basis_terms'])
            if audit_key not in audited:
                roots, _, _, _, _ = certify_roots(
                    2*item['ell'], item['ell'], item['n'], tuple(tuple(v) for v in item['reference_anf']),
                    raw, answer['proof_byteorder'])
                roots = list(roots)
                assert verify_basis(item['nvars'], item['reference_anf'], roots, answer['basis_terms'], len(roots))
                audited[audit_key] = roots
            roots = audited[audit_key]
            assert roots == answer['basis_certificate']['solutions']
            assert answer['assignment'] in roots
            schedule = answer['preparation_schedule']
            assert schedule['mode'] == row['preparation'] and schedule['drained']
            assert schedule['worker_count'] == (2 if row['preparation'] == 'overlap' else 1)
            if row['preparation'] != 'serial':
                assert schedule['certification_reached'] and not schedule['serial_fallback']
                assert schedule['preparation_code'] == 0
                assert schedule['prepare_end_ns'] >= schedule['prepare_start_ns']
                assert answer['basis_certificate']['preparation_stats']['used'] == 1
            assert sum(answer['phases_ns'].values()) == answer['complete_query_ns']
            proofs.add(answer['proof_sha256'])
            record = {k: row[k] for k in ('name', 'backend', 'sanitizer', 'symmetry', 'transform', 'preparation')}
            record.update(proof_sha256=answer['proof_sha256'], roots=roots, reduced_basis_verified=True)
            records.append(record)
            journal.write(json.dumps(record, separators=(',', ':'))+'\n')
            journal.flush()
            print('ORIGINAL_ANF_AUDIT_PASS', *key, flush=True)
    assert seen == expected
    for path, digest in report['executed_bindings'].items():
        assert sha(Path(path)) == digest, path
    result = {'schema': 'independent-preparation-original-anf-audit/1', 'status': 'PASS',
              'input_sha256': sha(args.input), 'fixture_sha256': sha(fixture), 'records': records,
              'source_sha256': report['executed_bindings'], 'unique_proofs': len(proofs),
              'scope': 'Original-equation witnesses, independently recomputed affine ranks, complete residual assignments and exact reduced Boolean bases. Audit-only reuse is outside query timing.',
              'timing_eligible': False, 'candidate_id': None, 'online_speedup': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('INDEPENDENT_AUDIT_PASS', len(records), 'query records;', len(proofs), 'unique proofs', flush=True)


if __name__ == '__main__':
    main()
