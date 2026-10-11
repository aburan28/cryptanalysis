"""Independently certify fresh complete queries before admitting timed pairs."""
import argparse
import gzip
import json
from pathlib import Path
import platform
from common import HERE,P,Context,arms,bindings,fixtures,host_identity,identity,read,sha,verify_bindings
from algebraic_certificate import verify
from analyze import validate_measurement

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    bound=bindings();contexts={}
    previous={(r['name'],r['variant'],r['sanitizer']):r['result'] for r in read(P/'round58/results/frozen-screen.json.gz')['rows']}
    report={'schema':'sparse-f4-query-preflight/1','status':'RUNNING','plan_sha256':sha(HERE/'measurement_plan.json'),
            'bindings':bound,'inputs':fixtures(),'rows':[],'platform':platform.platform(),'architecture':platform.machine(),
            'host':host_identity(),'timing_eligible':False}
    def save():args.output.write_bytes(gzip.compress(json.dumps(report,separators=(',',':')).encode(),mtime=0))
    save()
    try:
        for sanitizer in (False,True):contexts[sanitizer]=Context(sanitizer)
        for case in fixtures():
            results={}
            for arm in arms(case):
                for sanitizer,context in contexts.items():
                    row=context.run(case['name'],arm,export_proof=True);result=row['result']
                    validate_measurement(row)
                    assert result['status'] in ('solved','gb','inconclusive'),(case['name'],arm,result)
                    if result['verified']:
                        audit=verify(case['nvars'],case['equations'],result['basis'],result['proof'])
                        assert audit['verified'],(case['name'],arm,audit)
                        result['python_original_equations_audit']=audit
                    old=previous[case['name'],arm,sanitizer]
                    for key in ('basis','proof','top_stats','column_stats'):
                        assert old.get(key)==result.get(key),(case['name'],arm,key)
                    logical=lambda value:{k:v for k,v in value['producer_stats'].items() if not k.endswith('_seconds')}
                    assert logical(old)==logical(result) and old['verified']==result['verified']
                    if old['verified']:
                        counters=lambda value:{k:v for k,v in value['certificate']['stats'].items() if not k.endswith('_seconds')}
                        assert counters(old)==counters(result)
                    results[arm,sanitizer]=result
                    report['rows'].append({'name':case['name'],'arm':arm,'sanitizer':sanitizer,
                                           'identity':identity(result),'measurement':row})
                    save();print('PREFLIGHT',case['name'],arm,sanitizer,result['status'],flush=True)
                assert identity(results[arm,False])==identity(results[arm,True]),(case['name'],arm)
            bases=[sorted(tuple(sorted(row)) for row in value['basis']) for value in results.values() if value['verified']]
            if bases:assert all(basis==bases[0] for basis in bases)
    except BaseException as error:
        report.update(status='FAIL',error=repr(error));save();raise
    finally:
        for context in contexts.values():context.close()
    verify_bindings(bound);assert len(report['rows'])==92
    report['status']='PASS';save();print('PREFLIGHT_PASS',len(report['rows']),flush=True)
if __name__=='__main__':main()
