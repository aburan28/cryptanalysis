"""Validate and summarize the frozen compact-admissibility experiment."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from fixed_phase import scalar
from gf2n import Curve,GF2n,Point


def validate(data):
    if not data['complete']:
        raise ValueError('incomplete experiment')
    expected={('reliability',13,6,p,v) for p in ((0,0,0),(0,1,2))
              for v in ('table_chain','table_s4','compact_s4')}
    expected|={('scaling',n,l,(0,1,2),v) for n,l in ((7,4),(9,5),(13,6),(19,8))
               for v in ('table_s4','compact_s4')}
    runs={}
    root=Path(__file__).parent
    fixture=root/'results'/'compact_corpus_100.json'
    if hashlib.sha256(fixture.read_bytes()).hexdigest()!=data['corpus_sha256']:
        raise ValueError('frozen corpus hash mismatch')
    frozen=json.loads(fixture.read_text())['targets']
    for name,digest in data['source_sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError(f'source hash mismatch: {name}')
    inputs={}
    for run in data['runs']:
        key=(run['task'],run['n'],run['l'],tuple(run['phases']),run['variant'])
        if key in runs:
            raise ValueError('duplicate campaign')
        runs[key]=run
        rows=run['rows'];count=100 if run['task']=='reliability' else 12
        if len(rows)!=count or len({row['point'][0] for row in rows})!=count:
            raise ValueError('wrong count or duplicate target sign-orbit')
        if dict(Counter(row['status'] for row in rows))!=run['statuses']:
            raise ValueError('status counts mismatch')
        if sum(row['independent'] for row in rows)!=run['rank']:
            raise ValueError('rank count mismatch')
        paired=[(row['id'],row['point'],row['split'],row['oracle_sat']) for row in rows]
        group=key[:-1]
        if group in inputs and inputs[group]!=paired:
            raise ValueError('mismatched contender workloads')
        inputs[group]=paired
        if run['task']=='reliability':
            if [{k:row[k] for k in ('id','point','split')} for row in rows]!=frozen:
                raise ValueError('reliability inputs differ from frozen corpus')
        E=Curve(GF2n(run['n']),1)
        for row in rows:
            if row['status'] not in ('sat','unsat','timeout'):
                raise ValueError('unknown verdict')
            correct=None if row['status']=='timeout' else (row['status']=='sat')==row['oracle_sat']
            if correct is False or correct!=row['correct']:
                raise ValueError('incorrect verdict')
            if row['within_budget']!=(row['search_wall_s']<=data['timeout_s']):
                raise ValueError('budget flag mismatch')
            if row['status']=='sat':
                target=Point(*row['point'])
                points=[Point(*p) for p in row['points']]
                reconstructed=[scalar(E,c,Point(x,y)) for x,y,c in row['coefficient_row']]
                if E.sum(points)!=target or E.sum(reconstructed)!=target:
                    raise ValueError('point witness or coefficient row does not reconstruct target')
    if set(runs)!=expected:
        raise ValueError('missing or unexpected campaigns')
    return runs


def render(data):
    indexed=validate(data)
    reliability=sorted((r for r in indexed.values() if r['task']=='reliability'),
                       key=lambda r:(r['phases'],r['variant']))
    compact=[r for r in reliability if r['variant']=='compact_s4']
    gate1=all(row['correct'] is True and row['within_budget'] for r in compact for row in r['rows'])
    ratios=[]
    for r in compact:
        baseline=indexed[('reliability',13,6,tuple(r['phases']),'table_s4')]
        equal=all(x['correct'] is True for x in r['rows']+baseline['rows']) and r['rank']==baseline['rank']
        ratios.append(r['total_cpu_s']/baseline['total_cpu_s'] if equal else None)
    gate2=all(ratio is not None and ratio<=1 for ratio in ratios)
    out=['# Compact-admissibility milestone results','',
         'One sequential run; timings are observations, not confidence intervals. '
         'All verdicts, point witnesses, orbit-coefficient rows, input pairing and source hashes validate.','',
         '| Milestone | Decision |','|---|---|',
         f'| Reliable n=13 decomposition decisions | {"Passed" if gate1 else "Not passed"}: both frozen phase patterns, including fresh holdouts. |',
         f'| Compact admissibility at table cost | {"Passed in this run" if gate2 else "Not passed"}: no payload enumeration, but compact/table CPU ratios are '+
         ', '.join('unavailable' if x is None else f'{x:.3f}' for x in ratios)+'. |',
         '| Improving scaling | Not established: retain unresolved runs; no exponent fit or rho claim. |','',
         '## Frozen 100-target results','',
         'Each phase pattern uses the same 100 distinct sign-orbits. '
         'SAT counts are verified decompositions; UNSAT counts are correct negative decisions. '
         'Most targets have no decomposition in this small factor space.','',
         '| Phases | Variant | Decided | SAT | UNSAT | Timeout | Holdout decided | Max query wall (s) |',
         '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in reliability:
        s=r['statuses'];rows=r['rows'];hold=sum(x['correct'] is True for x in rows if x['split']=='holdout')
        out.append(f"| {tuple(r['phases'])} | {r['variant']} | {r['correct']}/100 | {s.get('sat',0)} | {s.get('unsat',0)} | {s.get('timeout',0)} | {hold}/50 | {max(x['search_wall_s'] for x in rows):.4f} |")
    out+=['','Setup includes construction and both solver loads (including the holdout reset). '
          'All these costs are in total CPU. Rank is factor-base coefficient rank after folding sign/Frobenius.','',
          '| Phases | Variant | Setup + loads CPU (s) | Total CPU (s) | Rank | CPU / independent row (s) |',
          '|---|---|---:|---:|---:|---:|']
    for r in reliability:
        setup=sum(r[k] for k in ('common_and_rank_setup_cpu_s','build_cpu_s','load_cpu_s'))
        cost=r['cpu_s_per_independent_row']
        out.append(f"| {tuple(r['phases'])} | {r['variant']} | {setup:.4f} | {r['total_cpu_s']:.4f} | {r['rank']} | {cost:.4f} |")
    compact_total=sum(r['total_cpu_s'] for r in compact)
    table_total=sum(r['total_cpu_s'] for r in reliability if r['variant']=='table_s4')
    out+=['',f'Across both patterns, compact total CPU is {compact_total:.4f} s versus '
          f'{table_total:.4f} s for table S4 ({compact_total/table_total:.3f} times the cost). '
          'Treat per-campaign ranks separately; summing them would double-count shared columns. '
          'The chain has unresolved targets in (0,1,2), so no equal-work speed ratio against it is reported.','',
          '## Four-size ladder','',
          'Twelve fresh targets per rung and variant, phases (0,1,2). '
          'All timeouts and correct negative decisions remain charged.','',
          '| n | l | Variant | Decided | SAT | Timeout | Rank | Total CPU (s) | CPU / independent row (s) |',
          '|---:|---:|---|---:|---:|---:|---:|---:|---:|']
    for r in sorted((r for r in indexed.values() if r['task']=='scaling'),key=lambda r:(r['n'],r['variant'])):
        s=r['statuses'];cost=r['cpu_s_per_independent_row'];formatted='undefined' if cost is None else f'{cost:.4f}'
        out.append(f"| {r['n']} | {r['l']} | {r['variant']} | {r['correct']}/12 | {s.get('sat',0)} | {s.get('timeout',0)} | {r['rank']} | {r['total_cpu_s']:.4f} | {formatted} |")
    out+=['','The table domains contain 1, 1, 4 and 27 admissible source payloads, respectively. '
          'This very small and uneven factor space is a material limitation. '
          'Both n=19 runs return zero independent rows; their cost per independent row is undefined, '
          'not zero and not an extrapolated runtime. These censored observations do not demonstrate improving scaling.','',
          '## Next gate','',
          'Keep the compact implementation experimental. The next useful target is to preserve '
          '100/100 decisions while reducing charged compact S4 CPU to at most the matched explicit-domain S4 cost '
          'in both n=13 phase patterns, then validate on a newly frozen holdout. '
          'The current run localizes the remaining cost to SAT search: compact setup is cheaper, '
          'but the larger inverse circuit costs more to solve. '
          'Do not count a smaller representation as a faster decomposition or retune on this already-observed holdout.','',
          'A Gröbner/F4 replay, robust measurements across larger completed rungs, final linear algebra, '
          'and a full equal-work comparison with folded rho remain unmeasured.','',
          f"Environment: Python {data['python']}, pycryptosat {data['pycryptosat']}, {data['platform']}. "
          'See [COMPACT.md](../COMPACT.md) for the proof, protocol and exclusions, '
          'and [compact_milestones.json](compact_milestones.json) for every observation.','']
    return '\n'.join(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    args=parser.parse_args()
    print(render(json.loads(args.input.read_text())),end='')
