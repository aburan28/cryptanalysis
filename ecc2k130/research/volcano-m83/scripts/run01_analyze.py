"""Run-01 synthesis: yield census, solver census and solver panel.

Writes outputs/run01-comparison/summary.json and comparison.csv.

    python3 run01_analyze.py
"""
import csv
import glob
import json
import statistics
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'outputs' / 'run01-comparison'


def jsonl(pattern):
    for path in sorted(glob.glob(str(OUT / pattern))):
        for line in open(path):
            yield json.loads(line)


def max_sat_dreg(row):
    ds = [c.get('degree_of_regularity') for c in row['cells']
          if c['kind'] == 'satisfiable' and c.get('degree_of_regularity') is not None]
    return max(ds) if ds else None


def main():
    census = {(r['curve_id'], r['k'], r['profile']): r for r in jsonl('yield-census-*.jsonl')}
    solver = {r['curve_id']: r for r in jsonl('census-*.jsonl') if r['k'] == 4 and r['profile'] == 'polynomial'}
    panel = {(r['curve_id'], r['k'], r['profile']): r for r in jsonl('panel-*.jsonl')}
    curves = sorted({c for c, _, _ in census})
    profiles = sorted({(k, p) for _, k, p in census})
    summary = {'curves': len(curves), 'profiles': {}}
    for k, p in profiles:
        rows = [census[(c, k, p)] for c in curves if (c, k, p) in census]
        e0 = census.get(('E0', k, p))
        desc = [r for r in rows if r['curve_id'] != 'E0']
        same = [r for r in desc if e0 and r['x_count'] == e0['x_count']]
        prof = {'rows': len(rows), 'x_range': [min(r['x_count'] for r in desc), max(r['x_count'] for r in desc)],
                'coverage_range': [min(r['prime_subgroup_distinct_targets'] for r in desc),
                                   max(r['prime_subgroup_distinct_targets'] for r in desc)],
                'formula_matches': sum(r['eligible_formula'] == r['eligible_signed_tuples'] for r in rows),
                'noninjective_rows': [r['curve_id'] for r in rows if r['eligible_duplicate_excess']],
                'infinity_rows': [r['curve_id'] for r in rows if r['eligible_infinity']]}
        if e0:
            prof['E0'] = {'x': e0['x_count'], 'coverage': e0['prime_subgroup_distinct_targets'],
                          'eligible': e0['eligible_signed_tuples'], 'excess': e0['eligible_duplicate_excess']}
            prof['descendants_above_E0_coverage'] = sum(r['prime_subgroup_distinct_targets']
                                                       > e0['prime_subgroup_distinct_targets'] for r in desc)
            if same:
                prof['matched_x_count'] = len(same)
                prof['matched_coverage_range'] = [min(r['prime_subgroup_distinct_targets'] for r in same),
                                                  max(r['prime_subgroup_distinct_targets'] for r in same)]
        summary['profiles']['%d:%s' % (k, p)] = prof
    # solver census, k = 4 polynomial
    status = Counter(c['status'] for r in solver.values() for c in r['cells'])
    dreg = Counter(max_sat_dreg(r) for r in solver.values())
    gb = lambda r: [c['groebner_cpu_seconds'] for c in r['cells'] if c.get('groebner_cpu_seconds') is not None]
    e0 = solver.get('E0')
    desc_med = [statistics.median(gb(r)) for cid, r in solver.items() if cid != 'E0' and gb(r)]
    summary['solver_census_k4_polynomial'] = {
        'curves': len(solver), 'cell_status': dict(status),
        'max_sampled_dreg_distribution': {str(k): v for k, v in sorted(dreg.items(), key=lambda t: (t[0] is None, t[0] or 0))},
        'E0_sampled_dregs': [c.get('degree_of_regularity') for c in e0['cells']] if e0 else None,
        'E0_gb_cpu_median': statistics.median(gb(e0)) if e0 and gb(e0) else None,
        'descendant_gb_cpu_median_of_medians': statistics.median(desc_med) if desc_med else None,
        'descendants_below_E0_dreg': sum(1 for cid, r in solver.items() if cid != 'E0' and max_sat_dreg(r) is not None
                                         and e0 and max_sat_dreg(r) < max_sat_dreg(e0)),
        'descendants_above_E0_dreg': sum(1 for cid, r in solver.items() if cid != 'E0' and max_sat_dreg(r) is not None
                                         and e0 and max_sat_dreg(r) > max_sat_dreg(e0))}
    # solver panel, k = 4 random and k = 5 polynomial
    for k, p in [(4, 'random'), (5, 'polynomial')]:
        rows = {c: r for (c, kk, pp), r in panel.items() if kk == k and pp == p}
        st = Counter(c['status'] for r in rows.values() for c in r['cells'])
        dr = Counter(max_sat_dreg(r) for r in rows.values())
        parity = Counter((r['factor_base_x_count'] % 2, max_sat_dreg(r)) for r in rows.values())
        summary['panel_%d_%s' % (k, p)] = {
            'curves': len(rows), 'cell_status': dict(st),
            'max_sampled_dreg_distribution': {str(a): b for a, b in sorted(dr.items(), key=lambda t: (t[0] is None, t[0] or 0))},
            'x_parity_vs_dreg': {'%d/%s' % a: b for a, b in sorted(parity.items(), key=lambda t: str(t))},
            'E0_sampled_dregs': [c.get('degree_of_regularity') for c in rows['E0']['cells']] if 'E0' in rows else None,
            'E0_statuses': [c['status'] for c in rows['E0']['cells']] if 'E0' in rows else None}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    with (OUT / 'comparison.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['curve_id', 'k', 'profile', 'x_count', 'n0', 'n2', 'no', 'eligible', 'distinct_targets',
                    'duplicate_excess', 'log2_coverage', 'k4poly_max_sampled_dreg'])
        for (c, k, p), r in sorted(census.items()):
            t = r['tag_types']
            w.writerow([c, k, p, r['x_count'], t['n0'], t['n2'], t['no'], r['eligible_signed_tuples'],
                        r['prime_subgroup_distinct_targets'], r['eligible_duplicate_excess'],
                        '%.4f' % r['log2_prime_subgroup_coverage'] if r['log2_prime_subgroup_coverage'] else '',
                        max_sat_dreg(solver[c]) if (k, p) == (4, 'polynomial') and c in solver else ''])
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
