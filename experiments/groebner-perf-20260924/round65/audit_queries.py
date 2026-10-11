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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    report = json.loads(gzip.decompress(args.input.read_bytes()))
    assert report['schema'] == 'independent-transform-query-validation/1' and report['status'] == 'PASS'
    assert report['validator_sha256'] == sha(HERE/'validate_queries.py')
    fixture = HERE.parent/'round40/fixtures/inputs.json.gz'
    assert sha(fixture) == report['fixture_sha256']
    fixtures = {item['name']: item for item in json.loads(gzip.decompress(fixture.read_bytes()))}
    for path, digest in report['executed_bindings'].items(): assert sha(Path(path)) == digest, path
    modes = [('cpu', 'cpu', False), ('cpu', 'cpu', True)]
    if report['metal']['status'] == 'AVAILABLE':
        modes += [('cpu', 'metal', False), ('metal', 'metal', False),
                  ('cpu', 'metal_simd', False), ('metal', 'metal_simd', False)]
    expected = {(name, backend, transform_backend, sanitizer, preparation)
                for name in fixtures for backend, transform_backend, sanitizer in modes
                for preparation in ('serial', 'prepared', 'overlap')}
    fields = ('name', 'backend', 'transform_backend', 'sanitizer', 'preparation')
    seen, audited, records = set(), {}, []
    with args.output.with_suffix('.jsonl').open('x') as journal:
        for row in report['queries']:
            key = tuple(row[k] for k in fields)
            assert key in expected and key not in seen
            seen.add(key)
            item, answer = fixtures[row['name']], row['result']
            assert row['workload_sha256'] == item['workload_sha256']
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
            cert = answer['basis_certificate']
            assert cert['solutions'] == roots and answer['assignment'] in roots
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
    for path, digest in report['executed_bindings'].items(): assert sha(Path(path)) == digest, path
    output = {'status': 'PASS', 'input_sha256': sha(args.input), 'records': records,
              'independent_proofs': len(audited), 'timing_eligible': False,
              'scope': 'Original polynomial identities, affine ranks, complete residual assignments and exact reduced Boolean bases; audit-only reuse outside all query timing.'}
    args.output.write_text(json.dumps(output, indent=2)+'\n')
    print('INDEPENDENT_ORIGINAL_ANF_AUDIT_PASS', len(records), 'queries;', len(audited), 'proofs', flush=True)


if __name__ == '__main__':
    main()
