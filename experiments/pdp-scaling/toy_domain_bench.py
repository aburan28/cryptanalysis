"""Paired fresh measurements, including setup, for explicit toy-domain filtering."""
import argparse
import hashlib
import itertools
import json
import platform
import random
import subprocess
from pathlib import Path

import pycryptosat
from fixed_phase import Template, benchmark
from toy_domain import ToyDomainTemplate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--repetitions', type=int, default=3)
    args = p.parse_args()
    if args.out.exists() or args.repetitions < 1:
        p.error('choose a new output file and positive repetitions')
    configs = list(itertools.product([(7,4,8), (13,6,4)], [17,911],
                                    [(0,0,0),(0,1,2)], range(args.repetitions)))
    random.Random(20260926).shuffle(configs)
    data = {'schema':'toy-domain-pdp/v1', 'scope':'PDP diagnostic; explicit exponential domain',
            'python':platform.python_version(), 'platform':platform.platform(),
            'pycryptosat':pycryptosat.__version__, 'timeout_s':1.0, 'guess_bits':2,
            'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'source_sha256':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                             for name in ('fixed_phase.py','toy_domain.py','toy_domain_bench.py','gf2n.py')},
            'complete':False,'pairs':[]}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    for index, ((n,l,count),seed,phases,rep) in enumerate(configs):
        pair = {'repetition':rep}
        factories = [('baseline',Template),('candidate',ToyDomainTemplate)]
        if index % 2:
            factories.reverse()
        pair['execution_order'] = [name for name,_ in factories]
        for name,factory in factories:
            pair[name] = benchmark(n,l,phases,'s3-chain','incremental',2,count,seed,1.0,
                                   template_factory=factory)
        a,b = pair['baseline'],pair['candidate']
        if a['target_sha256'] != b['target_sha256']:
            raise AssertionError('unmatched targets')
        if [r['oracle_sat'] for r in a['rows']] != [r['oracle_sat'] for r in b['rows']]:
            raise AssertionError('unmatched truth')
        pair['equal_completions'] = all(r['correct'] is True for r in a['rows']+b['rows'])
        # A timeout is a censored observation, not the time needed to finish.
        pair['stage_speedup'] = a['total_cpu_s']/b['total_cpu_s'] if pair['equal_completions'] else None
        data['pairs'].append(pair)
        args.out.write_text(json.dumps(data,indent=2)+'\n')
        print(n,l,seed,phases,rep,a['statuses'],b['statuses'],pair['stage_speedup'],flush=True)
    data['complete'] = True
    args.out.write_text(json.dumps(data,indent=2)+'\n')


if __name__ == '__main__':
    main()
