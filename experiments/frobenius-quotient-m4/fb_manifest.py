# Write results/factor_bases.json: for every ladder cell, the archived factor base
# (experiments/fb-archive, family nbweight with l = w) and its PS1 label.
#
#   python3 fb_manifest.py
#
# No type hints, camelCase identifiers (codegen convention).

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'fb-archive'))
import fbarchive  # noqa: E402,F401  (puts pdp-degree-heuristics on sys.path)
import ps1  # noqa: E402

# (n, w) of every cell run, including the n = 7 smoke run
CELLS = [(7, 2), (9, 2), (11, 2), (11, 3), (13, 2), (15, 2)]

SOURCES = ['experiments/frobenius-quotient-m4/ladder.py',
           'ecc2k130/runner/codegen/decomp.py',
           'ecc2k130/runner/codegen/indexcalc.py',
           'ecc2k130/runner/codegen/cnf.py',
           'ecc2k130/runner/codegen/curves.py']


def pdpRecord():
    return {
        'm': 4,
        'summation': 'three chained S_3 links, two intermediate abscissae (decomp.buildSystemPb); S_5 never formed',
        'encoding': 'CNF + native XOR over normal-basis coordinates; weight bound as a cardinality constraint; x != 0',
        'solver': 'sat',
        'engine': 'CryptoMiniSat via python-sat, one thread, per-instance CPU budget',
        'implementation_sha256': ps1.source_sha256(SOURCES),
    }


def main():
    pdp = pdpRecord()
    out = {'point_decomposition': pdp,
           'cells': [ps1.cell_manifest(n, 'nbweight', w, pdp) for n, w in CELLS]}
    path = os.path.join(HERE, 'results', 'factor_bases.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write('\n')
    for c in out['cells']:
        print(c['ps1_label'], c['archive_path'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
