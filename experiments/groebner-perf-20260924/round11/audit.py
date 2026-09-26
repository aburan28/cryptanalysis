"""Integrity and paired-result audit; timings are historical local observations."""
import gzip
import hashlib
import json
import sys
import math
from pathlib import Path
import random
import statistics

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
from measured_source import measured_bytes


def paired(rows,numerator,denominator):
    logs=[math.log(row[numerator]['wall_ns']/row[denominator]['wall_ns']) for row in rows]
    rng=random.Random(2026092517)
    boots=sorted(math.exp(sum(rng.choices(logs,k=len(logs)))/len(logs)) for _ in range(4000))
    return {'geometric_mean':math.exp(sum(logs)/len(logs)),'bootstrap_95':[boots[99],boots[3899]]}


def audit_report(name):
    report=json.loads(gzip.decompress((HERE/'results'/f'{name}.json.gz').read_bytes()))
    assert report['status']=='RECORDED'
    assert report['candidate_id'] is None and report['IC_online_ms'] is None and report['rho_online_ms'] is None
    for relative,expected in report['source_sha256'].items():
        path=Path(relative)
        assert not path.is_absolute() and '..' not in path.parts
        actual=ROOT/path
        if name=='screen' and actual.parent==HERE and actual.name in (
                'packed_producer.cpp','native_checker.cpp','test_packed_proof.py'):
            actual=HERE/'screen'/actual.name
        if actual.parent==HERE and actual.name=='proof_abi.h':
            actual=HERE/'measured/proof_abi.h.txt'
        if name=='comparison' and actual.parent==HERE and actual.name=='audit.py':
            actual=HERE/'measured/audit.py.txt'
        assert hashlib.sha256(measured_bytes(actual,expected)).hexdigest()==expected,relative
    assert len(report['inputs'])==23
    attempts=verified=0;cells=[]
    for fixture in report['inputs']:
        identity={k:v for k,v in fixture.items() if k not in ('workload_sha256','repetitions','fixture_ns')}
        assert hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()==fixture['workload_sha256']
        rows=[r for r in report['rows'] if r['workload_sha256']==fixture['workload_sha256']]
        arms=['cli-python','packed-python','packed-native']+(['evaluation'] if fixture['boundary']=='pdp' else [])
        assert len(rows)==fixture['repetitions']+1
        assert sorted(r['repetition'] for r in rows)==list(range(fixture['repetitions']+1))
        assert sum(r['warmup'] for r in rows)==1
        for row in rows:
            assert row['name']==fixture['name'] and row['boundary']==fixture['boundary']
            assert sorted(row['order'])==sorted(arms)
            successful=[]
            for arm in arms:
                result=row[arm]['result'];attempts+=1
                assert row[arm]['wall_ns']>0
                assert result['status'] in ('gb','solved','inconclusive','timeout','gb-no-verified-solution'),result
                if result.get('verified'):
                    verified+=1;successful.append(result)
                    if arm!='evaluation':
                        assert result['certificate']['verified']
                        assert result['certificate']['ideal_equality'] and result['certificate']['reduced_groebner_basis']
                    if fixture['boundary']=='pdp':assert result['status']=='solved'
                else:
                    assert result['status'] not in ('gb','solved')
            if successful:
                assert len({r['basis_sha256'] for r in successful})==1,(fixture['name'],successful)
                if fixture['boundary']=='pdp':assert len({r['assignment'] for r in successful})==1
        measured=[r for r in rows if not r['warmup']]
        cell={'name':fixture['name'],'boundary':fixture['boundary'],'repetitions':len(measured),
            'statuses':{arm:{status:sum(r[arm]['result']['status']==status for r in measured)
                for status in sorted({r[arm]['result']['status'] for r in measured})} for arm in arms},
            'median_ms':{arm:statistics.median(r[arm]['wall_ns'] for r in measured)/1e6 for arm in arms}}
        for numerator,denominator in [('cli-python','packed-native'),('cli-python','packed-python'),
                                       ('packed-python','packed-native')]+([('packed-native','evaluation')] if 'evaluation' in arms else []):
            key=numerator+'_over_'+denominator
            # No survivor-only speedup: every declared repetition must verify
            # both arms on the same input. Failures are reported above.
            cell[key]=paired(measured,numerator,denominator) if all(
                r[numerator]['result'].get('verified') and r[denominator]['result'].get('verified') for r in measured) else None
        cells.append(cell)
    log=(HERE/'results'/('screen-validation-final.log' if name=='screen' else 'validation-final.log')).read_text()
    assert '\nOK\n' in log and '"random_controls_verified": 95' in log and '"random_controls_inconclusive": 1' in log
    return {'audit':'PASS','scope':'retained evidence integrity and paired accounting',
        'attempts_including_warmups':attempts,'verified_attempts':verified,'cells':cells}


def main():
    # The post-measurement ABI edit changes whitespace only.
    assert ''.join((HERE/'proof_abi.h').read_text().split())==''.join((HERE/'measured/proof_abi.h.txt').read_text().split())
    formatting=json.loads((HERE/'results/formatting-build-receipt.json').read_text())
    measured=json.loads((HERE/'results/build-receipt.json').read_text())['binary_sha256']
    assert formatting['identical'] and formatting['before']==formatting['after']
    assert all(measured[name]==value for name,value in formatting['before'].items())
    inventory=json.loads((HERE/'results/inventory.json').read_text())
    for relative,expected in inventory['sha256'].items():
        path=Path(relative)
        assert not path.is_absolute() and '..' not in path.parts
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,relative
    print(json.dumps({name:audit_report(name) for name in ('screen','comparison')},indent=2))


if __name__=='__main__':
    main()
