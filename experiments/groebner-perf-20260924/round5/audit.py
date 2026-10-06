"""Audit measured source versions and independently replay retained proofs."""
import gzip
import hashlib
import json
from pathlib import Path

from algebraic_certificate import verify

HERE=Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks=certificates=records=0
    for name in ('proof-benchmark-before-product.json.gz','proof-benchmark.json.gz'):
        old='before-product' in name
        report=json.loads(gzip.decompress((HERE/'results'/name).read_bytes()))
        assert report['status']=='RECORDED'
        for relative,expected in report['source_sha256'].items():
            path=Path(relative)
            assert not path.is_absolute() and '..' not in path.parts
            if old and relative=='algebraic_certificate.py':
                path=Path('baseline')/path
            assert digest(HERE/path)==expected,str(path)
            checks+=1
        for key,case in report['certificates'].items():
            encoded=json.dumps(case['proof'],separators=(',',':')).encode()
            assert hashlib.sha256(encoded).hexdigest()==key
            result=verify(case['nvars'],case['equations'],case['basis'],case['proof'],
                          max_work=20_000_000,max_retained_terms=2_000_000)
            assert result['verified'],result
            certificates+=1
        workloads={c['name']:c for c in report['cases']}
        for name,case in workloads.items():
            identity={key:value for key,value in case.items() if key!='workload_sha256'}
            assert hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()==case['workload_sha256']
        for row in report['rows']:
            for arm in row['order']:
                result=row[arm]
                if result.get('verified'):
                    certificate=report['certificates'][result['proof_sha256']]
                    assert certificate['basis']==result['basis']
                    assert certificate['equations']==workloads[row['name']]['equations']
                    assert certificate['nvars']==workloads[row['name']]['nvars']
                else:
                    assert result['status']=='inconclusive' or (arm=='untraced' and result['status']=='gb')
                records+=1
    for name,old in (('singular-validation.json',False),('singular-before-product.json.gz',True),
                     ('checker-benchmark.json',False)):
        path=HERE/'results'/name
        report=json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())
        assert report['status']=='PASS'
        for relative,expected in report['source_sha256'].items():
            path=Path(relative)
            assert not path.is_absolute() and '..' not in path.parts
            if old and relative=='algebraic_certificate.py':
                path=Path('baseline')/path
            assert digest(HERE/path)==expected,str(path)
            checks+=1
    print(json.dumps({'status':'PASS','source_hash_checks':checks,'replayed_certificates':certificates,
                      'preserved_attempt_records':records}))


if __name__=='__main__':
    main()
