"""Write results/factor_bases.json: for every LHD cell, the archived factor base
(experiments/fb-archive, family prefix: V = span{1, z, ..., z^(l-1)}) and its PS1 label.

    python3 fb_manifest.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'fb-archive'))
import fbarchive  # noqa: E402,F401  (puts pdp-degree-heuristics on sys.path)
import ps1  # noqa: E402

# (n, l) of every cell run: oracle checks at (17, 6) and (23, 8), decompositions at the rest;
# (31, 8) was stopped (below the existence condition) and is recorded, not reported
CELLS = [(17, 6), (23, 8), (31, 8), (31, 10), (41, 13), (41, 14)]


def pdp_record():
    return {
        'm': 4,
        'summation': 'S_3 linear in (e1, e2) = (x1 + x2, x1 x2); n x (3l - 1) F_2 solve for the second pair',
        'encoding': 'sample Q = P_a + P_b from the base, linearized two-point oracle on R - Q',
        'solver': 'lin',
        'engine': 'pure Python Gaussian elimination over F_2 (lhd.solveAffine)',
        'implementation_sha256': ps1.source_sha256(['experiments/linearized-half-decomposition/lhd.py']),
    }


def main():
    pdp = pdp_record()
    out = {'point_decomposition': pdp,
           'cells': [ps1.cell_manifest(n, 'prefix', l, pdp) for n, l in CELLS]}
    with open(os.path.join(HERE, 'results', 'factor_bases.json'), 'w') as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write('\n')
    for c in out['cells']:
        print(c['ps1_label'], c['archive_path'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
