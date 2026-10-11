# Tabulate results/cell_*.json: per arm, status mix, median CPU seconds,
# oracle agreement; and a least-squares slope of log2(median random-arm CPU)
# against log2(B), the exponent in factor-base size that budget.py compares
# with the required exponent at n = 131.
#
#   python3 summarize.py [--md results/summary.md]

import argparse
import glob
import json
import math


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--md')
    a = ap.parse_args()
    cells = []
    for p in sorted(glob.glob('results/cell_*.json')):
        with open(p) as f:
            cells.append(json.load(f))
    cells.sort(key=lambda c: (c['n'], c['weight']))
    lines = ['| n | w | B (x-classes) | log2 B | orbits | arm | sat | unsat | censored | spurious | '
             'oracle disagreements | median CPU s (completed) |',
             '|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|']
    fitPts = []
    for c in cells:
        lb = math.log2(c['base_points'])
        for arm in ('planted', 'random'):
            rows = c['arms'].get(arm, [])
            if not rows:
                continue
            cnt = {}
            for r in rows:
                cnt[r['status']] = cnt.get(r['status'], 0) + 1
            dis = 0
            for r in rows:
                if 'oracle_reachable' in r:
                    if r['status'] == 'sat' and not r['oracle_reachable']:
                        dis += 1
            done = [r['cpu_s'] for r in rows if r['status'] in ('sat', 'unsat')]
            med = median(done)
            if arm == 'random' and med and cnt.get('budget', 0) == 0:
                fitPts.append((lb, math.log2(med)))
            lines.append('| %d | %d | %d | %.2f | %d | %s | %d | %d | %d | %d | %d | %s |' % (
                c['n'], c['weight'], c['base_points'], lb, c['orbits'], arm,
                cnt.get('sat', 0), cnt.get('unsat', 0), cnt.get('budget', 0),
                cnt.get('spurious', 0), dis, '%.2f' % med if med is not None else '—'))
    out = '\n'.join(lines)
    if len(fitPts) >= 2:
        mx = sum(x for x, _ in fitPts) / len(fitPts)
        my = sum(y for _, y in fitPts) / len(fitPts)
        sxx = sum((x - mx) ** 2 for x, _ in fitPts)
        sxy = sum((x - mx) * (y - my) for x, y in fitPts)
        out += ('\n\nSlope of log2(median random-arm CPU) on log2 B over %d uncensored cells: '
                '%.2f (descriptive; cells differ in n as well as B).' % (len(fitPts), sxy / sxx))
    print(out)
    if a.md:
        with open(a.md, 'w') as f:
            f.write(out + '\n')


if __name__ == '__main__':
    main()
