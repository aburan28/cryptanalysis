"""Verify measured source bytes and all paired correctness results."""
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    records = checked = 0
    for name in ('screen', 'confirmation'):
        report = json.loads(gzip.decompress((HERE/'results'/f'{name}.json.gz').read_bytes()))
        assert report['status'] == 'PASS'
        for relative, expected in report['source_sha256'].items():
            path = Path(relative)
            assert not path.is_absolute() and '..' not in path.parts
            path = ROOT/path
            if name == 'screen' and path.parent == HERE and path.name in ('packed_query.py','benchmark.py'):
                path = HERE/'screen'/path.name
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, str(path)
            checked += 1
        for row in report['rows']:
            results = [row[arm]['result'] for arm in row['order']]
            assert all(result.get('verified') and result.get('groebner_verified') for result in results)
            assert len({(result['basis_sha256'],result['assignment']) for result in results}) == 1
            records += len(results)
    print(json.dumps({'status':'PASS','source_hash_checks':checked,'verified_query_records':records,
                      'scope':'Source/evidence audit; historical native binaries rebuilt and checked separately'}))


if __name__ == '__main__':
    main()
