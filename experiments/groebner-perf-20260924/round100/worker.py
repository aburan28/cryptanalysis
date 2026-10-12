"""One complete fresh query; proof artifact serialization follows the timer."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
from common import Context,plan

def compact(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()

def run(name,arm,budget,*,sanitized=False,output):
    protocol=plan()
    if name not in protocol['cases'] or arm not in protocol['arms'] or budget not in protocol['budgets']:
        raise ValueError('query is outside the frozen panel')
    context=Context(sanitizer=sanitized)
    measured=context.run(name,arm,limits={'max_work':budget})
    # Context includes proof materialization and independent replay in its timer.
    # Only artifact hashing/storage occurs here, after that complete interval.
    result=measured['result']
    if 'proof' in result:
        data=compact(result.pop('proof'));digest=hashlib.sha256(data).hexdigest()
        proofs=output.parent.parent/'proofs';proofs.mkdir(exist_ok=True)
        path=proofs/(digest+'.json')
        if path.exists():
            if path.read_bytes()!=data:raise ValueError('proof artifact digest collision')
        else:
            temp=path.with_suffix('.tmp');temp.write_bytes(data);temp.replace(path)
        result['proof_sha256']=digest
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    record=dict(**measured,preparation_seconds=context.preparation_seconds,
        preparation=dict(cases=list(context.cases),plans=len(context.plans),workspaces=len(context.workspaces)),
        process_peak_rss_bytes=int(peak if sys.platform=='darwin' else peak*1024))
    temp=output.with_suffix('.tmp');temp.write_text(json.dumps(record,sort_keys=True)+'\n');temp.replace(output)
    print(result['status'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--arm',required=True)
    p.add_argument('--budget',required=True,type=int);p.add_argument('--sanitized',action='store_true')
    p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    run(a.name,a.arm,a.budget,sanitized=a.sanitized,output=a.output)
