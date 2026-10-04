"""Freeze kernel-only controls directly from original ANF and audited proof bytes."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    report = json.loads(gzip.decompress(args.validation.read_bytes()))
    fixture = HERE.parent/'round40/fixtures/inputs.json.gz'
    assert report['status'] == 'PASS' and report['fixture_sha256'] == sha(fixture)
    inputs = {v['name']: v for v in json.loads(gzip.decompress(fixture.read_bytes()))}
    names = ['n31-m3-ell6-seed101', 'n31-m3-ell8-seed201', 'n31-m3-ell9-seed201']
    records = []
    for name in names:
        item = inputs[name]
        rows = [r for r in report['queries'] if r['name'] == name and r['backend'] == 'metal'
                and r['transform_backend'] == 'metal_simd' and not r['sanitizer']
                and r['preparation'] == 'serial']
        assert len(rows) == 1 and rows[0]['result']['verified']
        answer = rows[0]['result']
        digest = answer['proof_sha256']
        raw = base64.b64decode(report['proofs'][digest], validate=True)
        assert hashlib.sha256(raw).hexdigest() == digest and item['n'] <= 32
        coefficients = {}
        # The frozen ANF is (monomial mask, packed equation coefficients),
        # not a list of per-equation monomial supports.
        for mask, value in item['reference_anf']:
            assert type(mask) is int and 0 <= mask < (1 << item['nvars'])
            assert type(value) is int and 0 <= value < (1 << item['n'])
            coefficients[mask] = coefficients.get(mask, 0) ^ value
        terms = sorted((m, c) for m, c in coefficients.items() if c)
        x, y = 2*item['ell'], item['ell']
        prefix = [int.from_bytes(raw[i*8:i*8+8], answer['proof_byteorder']) for i in range(1 << x)]
        path = args.output/(name+'.bin')
        with path.open('wb') as output:
            output.write(struct.pack('<5Q', 0x3636524e52454b, x, y, item['n'], len(terms)))
            for pair in terms: output.write(struct.pack('<2Q', *pair))
            for value in prefix: output.write(struct.pack('<Q', value))
        records.append({'name': name, 'input_sha256': sha(path), 'proof_sha256': digest,
                        'workload_sha256': item['workload_sha256'], 'x': x, 'y': y,
                        'equations': item['n'], 'terms': len(terms), 'symmetry_skips': False})
    plan = {'scope': 'Constant-identity kernel only; original ANF reconstructed independently; no symmetry skips.',
            'validation_sha256': sha(args.validation), 'fixture_sha256': sha(fixture),
            'arms': ['original', 'prepared_builtin', 'prepared_folded'],
            'arm_orders': [[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]]*5,
            'preparation_charged': True, 'transform_and_allocation_charged': False,
            'timing_eligible': False, 'host_isolation_receipt': None, 'aggregate_speedup': None,
            'records': records}
    (args.output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')


if __name__ == '__main__':
    main()
