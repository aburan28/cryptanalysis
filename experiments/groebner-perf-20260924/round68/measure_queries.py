"""Balanced complete-query diagnostic against the unchanged producer and explicit transform modes."""
import argparse
from contextlib import ExitStack
import gzip
import hashlib
import json
import os
from pathlib import Path
import time
import subprocess
from adapter import HERE, ProjectionQuery, base
from bindings import bindings
from public_replay import Point
from query_cases import check_accounting


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
    variants=('reference','cpu','metal','metal_tiled') if args.metal else ('reference','cpu')
    arms=[(backend, mode) for backend in (('cpu','metal_simd') if args.metal else ('cpu',))
          for mode in variants]
    # Even-size Williams design: every position and every ordered neighbor pair
    # is balanced in one block. Repeat three times, retaining all observations.
    first=(0,1,7,2,6,3,5,4) if args.metal else (0,1)
    count=len(arms)
    block=[[(value+offset)%count for value in first] for offset in range(count)]
    pairs=[(a,b) for order in block for a,b in zip(order,order[1:])]
    assert len(set(pairs))==count*(count-1)
    orders=block*3
    frozen=bindings()
    assert str(HERE/'build/receipt.json') in frozen
    assert frozen[str(Path(__file__).resolve())] == sha(Path(__file__))
    frozen[str(fixture)]=sha(fixture)
    assert subprocess.check_output(['git','status','--porcelain'],cwd=HERE,text=True)==''
    plan={'schema':'shared-producer-transform-complete-query-diagnostic/1',
          'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip(),'names':names,'arms':arms,
          'orders':orders,'producer':'metal' if args.metal else 'cpu',
          'preparation':'serial','timing_eligible':False,'host_isolation_receipt':None,
          'interval':'Fresh solve through independent basis certificate, original equations and public-point replay; all per-query coefficient transforms, witness preparation, copies and synchronization charged; context allocation/pipeline setup separately recorded.',
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
                    record={'name':name,'arm':[backend,mode]}
                    try:
                        factory=base.ProjectionQuery if mode=='reference' else ProjectionQuery
                        flags={} if mode=='reference' else {'producer_transform':mode}
                        context=stack.enter_context(factory(*shape,
                            backend=plan['producer'],transform_backend=backend,
                            constant_identity='prepared',identity='factored_local',
                            preparation='serial',transform='full',**flags))
                        assert context.basis.producer.path.parent.parent.name==('round51' if mode=='reference' else 'round68')
                        assert context.checker.path.parent.parent.name=='round66'
                        contexts.append(context)
                    except BaseException as error:
                        record.update(error=repr(error),wall_ns=time.perf_counter_ns()-started)
                        report['setup'].append(record); report['status']='FAIL'
                        save(args.output/'report.json',report)
                        raise
                    record.update(wall_ns=time.perf_counter_ns()-started)
                    report['setup'].append(record)
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
                            assert constant['requested']==constant['used']==1
                            if arms[arm][1]=='reference':
                                assert 'producer_transform_stats' not in answer
                            else:
                                check_accounting(answer,item,plan['producer'],arms[arm][1])
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
