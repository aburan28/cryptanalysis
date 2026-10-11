"""Summarize fresh paired toy-domain measurements without pricing timeouts."""
import argparse
import collections
import json
import statistics
from pathlib import Path


def summarize(path):
    data=json.loads(Path(path).read_text())
    if not data['complete']:
        raise ValueError('incomplete campaign')
    groups=collections.defaultdict(list)
    for pair in data['pairs']:
        a,b=pair['baseline'],pair['candidate']
        if a['target_sha256']!=b['target_sha256'] or a['targets']!=b['targets']:
            raise ValueError('mismatched corpus')
        if [(r['target'],r['oracle_sat']) for r in a['rows']] != [(r['target'],r['oracle_sat']) for r in b['rows']]:
            raise ValueError('mismatched target/verdict data')
        if any(r['correct'] is False for r in a['rows']+b['rows']):
            raise ValueError('incorrect solver result')
        groups[(a['n'],a['l'],tuple(a['phases']),a['seed'])].append(pair)
    lines=['# Toy-domain paired results','',
           'Times are medians of cold PDP campaigns, including domain enumeration.',
           'Completion counts pool all repetitions. A dash means no equal-work speed ratio.', '',
           '| n,l | phases | seed | repetitions | baseline decided | candidate decided | candidate SAT | baseline CPU s | candidate CPU s | stage ratio |',
           '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for (n,l,phases,seed),pairs in sorted(groups.items()):
        if len(set(p['repetition'] for p in pairs))!=len(pairs):
            raise ValueError('duplicate repetition')
        medians={name:statistics.median(p[name]['total_cpu_s'] for p in pairs)
                 for name in ('baseline','candidate')}
        decided={name:sum(r['correct'] is True for p in pairs for r in p[name]['rows'])
                 for name in ('baseline','candidate')}
        allrows=sum(p['baseline']['targets'] for p in pairs)
        equal=decided['baseline']==decided['candidate']==allrows
        ratio=medians['baseline']/medians['candidate'] if equal else None
        ratio_text=f'{ratio:.2f}x' if ratio is not None else '—'
        sat=sum(p['candidate']['verified'] for p in pairs)
        lines.append(f"| {n},{l} | {phases} | {seed} | {len(pairs)} | {decided['baseline']}/{allrows} | {decided['candidate']}/{allrows} | {sat} | {medians['baseline']:.6f} | {medians['candidate']:.6f} | {ratio_text} |")
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('result',type=Path)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args()
    if a.out.exists():
        p.error('choose a new output file')
    a.out.write_text(summarize(a.result))
