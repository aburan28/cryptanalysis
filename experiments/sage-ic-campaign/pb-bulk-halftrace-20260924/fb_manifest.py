# Write factor_bases.json: the archived factor base (experiments/fb-archive, family
# nbweight, l = w) behind each degree in this run. The run records only counts;
# test_pbbulk_factor_bases.py checks that indexcalc.factorBase rebuilds each
# archived set and that the counts in run-*/degree-*.json match it.
#
#   python3 fb_manifest.py
#
# No type hints, camelCase identifiers (codegen convention).

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'fb-archive'))
import fbarchive  # noqa: E402,F401  (puts pdp-degree-heuristics on sys.path)
import ps1  # noqa: E402

# (degree n, weight bound w) of every degree this run measured
CELLS = [(11, 3), (13, 3), (53, 2), (131, 2)]


def main():
    cells = []
    for n, w in CELLS:
        row = ps1.index_row(n, 'nbweight', w)
        cells.append({'n': n, 'w': w, 'curve_id': row['curve_id'],
                      'factor_base_sha256': row['factor_base_sha256'],
                      'enumerated_set_sha256': row['enumerated_set_sha256'],
                      'fb_points': int(row['fb_points']),
                      'effective_columns': int(row['effective_columns']),
                      'archive_path': 'experiments/fb-archive/' + row['path']})
    with open(os.path.join(HERE, 'factor_bases.json'), 'w') as f:
        json.dump({'cells': cells}, f, indent=1, sort_keys=True)
        f.write('\n')
    for c in cells:
        print(c['n'], c['w'], c['archive_path'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
