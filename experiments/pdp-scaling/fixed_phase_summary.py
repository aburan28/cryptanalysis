"""Render matched PDP cost ratios; refuse comparisons across different corpora."""
import argparse
import collections
import json
from pathlib import Path


def summarize(paths):
    groups = collections.defaultdict(list)
    baseline = {}
    for path in paths:
        data = json.loads(Path(path).read_text())
        for r in data['runs']:
            workload = (r['n'], r['l'], tuple(r['phases']), r['seed'])
            if r['encoding'] == 'anf-s4':
                if workload in baseline:
                    raise ValueError('duplicate baseline workload; summarize each repetition separately')
                baseline[workload] = r
            key = (r['n'], r['l'], tuple(r['phases']), r['encoding'], r['mode'], r['guess_bits'])
            groups[key].append(r)
    lines = ['# Matched PDP stage results', '',
             'CPU seconds include setup and all PDP attempts. Ratios are candidate/baseline;',
             'lower is cheaper. A dash means unmatched completions. No DLP/rho ratio is measured.', '',
             '| n,l | phases | encoding / mode / guess | decided / targets | verified | CPU s | CPU / ANF baseline | gate |',
             '|---|---|---|---:|---:|---:|---:|---|']
    for (n,l,phases,encoding,mode,g), runs in sorted(groups.items()):
        expected_seeds = {key[3] for key in baseline if key[:3] == (n,l,phases)}
        if {r['seed'] for r in runs} != expected_seeds or len(runs) != len(expected_seeds):
            raise ValueError('missing or duplicate seed: incomplete matched workload')
        refs = [baseline[(n,l,phases,r['seed'])] for r in runs]
        comparable = True
        for r, b in zip(runs, refs):
            if r['target_sha256'] != b['target_sha256'] or r['targets'] != b['targets']:
                raise ValueError('different corpus for claimed matched ratio')
            if [(x['target'], x['oracle_sat']) for x in r['rows']] != [(x['target'], x['oracle_sat']) for x in b['rows']]:
                raise ValueError('oracle/corpus mismatch')
            comparable &= all(x['correct'] is True for x in r['rows'] + b['rows'])
        total = sum(r['total_cpu_s'] for r in runs)
        ratio = total / sum(r['total_cpu_s'] for r in refs) if comparable else None
        gate = comparable and all(r['total_cpu_s'] <= 0.8*b['total_cpu_s'] for r,b in zip(runs, refs))
        decided = sum(sum(x['status'] != 'timeout' for x in r['rows']) for r in runs)
        verified = sum(r['verified'] for r in runs)
        targets = sum(r['targets'] for r in runs)
        cost = f'{ratio:.3f}' if ratio is not None else '—'
        outcome = 'baseline' if encoding == 'anf-s4' else ('pass (stage only)' if gate else 'fail')
        lines.append(f'| {n},{l} | {phases} | {encoding} / {mode} / {g} | {decided}/{targets} | {verified} | {total:.4f} | {cost} | {outcome} |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('results', nargs='+', type=Path)
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    result = summarize(args.results)
    if args.out:
        if args.out.exists():
            p.error('output exists; choose a new path')
        args.out.write_text(result)
    else:
        print(result, end='')
