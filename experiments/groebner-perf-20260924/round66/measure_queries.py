"""Balanced complete-query diagnostic for independent constant-witness checking."""
import argparse
from contextlib import ExitStack
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import time
from adapter import HERE, ProjectionQuery
from bindings import bindings
from public_replay import Point


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value): path.write_text(json.dumps(value, indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--metal', action='store_true')
    args=parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    fixture=HERE.parent/'round40/fixtures/inputs.json.gz'
    inputs={v['name']:v for v in json.loads(gzip.decompress(fixture.read_bytes()))}
    names=('n31-m3-ell6-seed101','n31-m3-ell8-seed201','n31-m3-ell9-seed201')
    arms=[(backend, mode) for backend in (('cpu','metal_simd') if args.metal else ('cpu',))
          for mode in ('original','prepared','folded')]
    if args.metal:
        # Williams design: each arm occurs once at each position and each
        # ordered pair occurs once as a neighbor in the six-order block.
        first=(0,1,5,2,4,3)
        block=[[(v+offset)%6 for v in first] for offset in range(6)]
        pairs=[(a,b) for order in block for a,b in zip(order,order[1:])]
        assert len(set(pairs))==30
    else: block=list(itertools.permutations(range(3)))
    orders=block*3
    frozen=bindings()
    assert str(HERE/'build/native-receipt.json') in frozen
    assert frozen[str(Path(__file__).resolve())] == sha(Path(__file__))
    frozen[str(fixture)]=sha(fixture)
    plan={'schema':'constant-identity-complete-query-diagnostic/1','names':names,'arms':arms,
          'orders':orders,'producer':'metal' if args.metal else 'cpu',
          'preparation':'serial','timing_eligible':False,'host_isolation_receipt':None,
          'interval':'Fresh solve through independent basis certificate, original equations and public-point replay; all per-query witness preparation, copies and synchronization charged; context allocation separately recorded.',
          'executed_bindings':frozen}
    save(args.output/'plan.json',plan)
    report={'status':'RUNNING','plan_sha256':sha(args.output/'plan.json'),'setup':[],
            'queries':[],'timing_eligible':False,'candidate_id':None,'online_speedup':None,
            'aggregate_speedup':None}
    save(args.output/'report.json',report)
    with (args.output/'queries.jsonl').open('x') as journal:
        for name in names:
            item=inputs[name]; shape=tuple(item[k] for k in ('n','mod','b','m','ell'))
            target=Point(**item['target'])
            with ExitStack() as stack:
                contexts=[]
                for backend, mode in arms:
                    started=time.perf_counter_ns()
                    contexts.append(stack.enter_context(ProjectionQuery(*shape,
                        backend=plan['producer'], transform_backend=backend,
                        constant_identity=mode, identity='factored_local',
                        preparation='serial',transform='full')))
                    report['setup'].append({'name':name,'arm':[backend,mode],
                                           'wall_ns':time.perf_counter_ns()-started})
                expected=None
                for trial,order in enumerate(orders):
                    for arm in order:
                        load=os.getloadavg(); started=time.perf_counter_ns()
                        record={'name':name,'arm':arm,'configuration':arms[arm],
                                'trial':trial,'order':order,'load_start':load}
                        try:
                            answer=contexts[arm].solve(target)
                            record.update(wall_ns=time.perf_counter_ns()-started,load_end=os.getloadavg())
                            raw=answer.pop('proof_bytes'); record['result']=answer
                            assert answer['verified'] and answer['status']=='solved'
                            assert hashlib.sha256(raw).hexdigest()==answer['proof_sha256']
                            exact=tuple(answer[k] for k in ('basis_sha256','proof_sha256','assignment'))
                            if expected is None: expected=exact
                            assert exact==expected
                            assert sum(answer['phases_ns'].values())==answer['complete_query_ns']
                            constant=answer['basis_certificate']['constant_identity_stats']
                            assert constant['requested']==('original','prepared','folded').index(arms[arm][1])
                            assert constant['used']==int(arms[arm][1]!='original')
                        except BaseException as error:
                            record.update(error=repr(error),wall_ns=time.perf_counter_ns()-started)
                            report['queries'].append(record); report['status']='FAIL'
                            journal.write(json.dumps(record,separators=(',',':'))+'\n'); journal.flush()
                            save(args.output/'report.json',report)
                            raise
                        report['queries'].append(record)
                        journal.write(json.dumps(record,separators=(',',':'))+'\n'); journal.flush()
                save(args.output/'report.json',report)
            print('COMPLETE_QUERY_DIAGNOSTIC_PASS',name,len(orders)*len(arms),flush=True)
    for path,digest in frozen.items(): assert sha(Path(path))==digest,path
    report['status']='PASS'; save(args.output/'report.json',report)


if __name__=='__main__': main()
