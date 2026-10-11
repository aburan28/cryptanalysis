# Tabulate results/lhd_*.json: samples per four-point decomposition against the
# predicted 2^(n - 2l) and meet-in-the-middle's 2^(2l).
#
#   python3 summarize.py [--md results/summary.md]

import argparse
import glob
import json
import math


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--md')
    a = ap.parse_args()
    lines = ['| n | l | targets solved | median samples | log2 median samples | predicted log2 (n - 2l) '
             '| MITM log2 (2l) | exponent in \\|F\\| (log2 samples / l) | median CPU s |',
             '|--:|--:|--:|--:|--:|--:|--:|--:|--:|']
    recs = []
    for p in glob.glob('results/lhd_*.json'):
        with open(p) as f:
            recs.append(json.load(f))
    recs.sort(key=lambda r: (r['n'], r['l']))
    for r in recs:
        ts = r['targets']
        ok = [t for t in ts if t['solved']]
        if not ok:
            continue
        sm = sorted(t['samples'] for t in ok)[len(ok) // 2]
        cpu = sorted(t['cpu_s'] for t in ok)[len(ok) // 2]
        lines.append('| %d | %d | %d/%d | %d | %.1f | %d | %d | %.2f | %.1f |' % (
            r['n'], r['l'], len(ok), len(ts), sm, math.log2(sm), r['n'] - 2 * r['l'],
            2 * r['l'], math.log2(sm) / r['l'], cpu))
    out = '\n'.join(lines)
    print(out)
    if a.md:
        with open(a.md, 'w') as f:
            f.write(out + '\n')


if __name__ == '__main__':
    main()
