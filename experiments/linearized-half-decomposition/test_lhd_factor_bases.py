"""Every LHD cell's factor base is archived in experiments/fb-archive (family prefix), and
the base lhd.py enumerates is the archived usable set plus only 4-torsion points
(which the archive's cofactor_projection policy drops and a random relation never needs).

    python3 -m pytest experiments/linearized-half-decomposition -q
"""

import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'fb-archive'))
import fbarchive  # noqa: E402
import lhd  # noqa: E402
import ps1  # noqa: E402

with open(os.path.join(HERE, 'results', 'factor_bases.json')) as _f:
    MANIFEST = json.load(_f)


def test_every_result_cell_has_an_archived_base():
    cells = {(c['n'], c['l']) for c in MANIFEST['cells']}
    for path in glob.glob(os.path.join(HERE, 'results', 'lhd_*.json')):
        with open(path) as f:
            rec = json.load(f)
        assert (rec['n'], rec['l']) in cells, path
    for n, l in ((17, 6), (23, 8), (31, 8)):     # oracle checks and the stopped cell
        assert (n, l) in cells


def test_manifest_matches_index_and_file():
    for c in MANIFEST['cells']:
        row = ps1.index_row(c['n'], 'prefix', c['l'])
        assert row['factor_base_sha256'] == c['factor_base_sha256']
        data = (fbarchive.ROOT / c['archive_path']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['file_sha256']


def test_lhd_base_is_the_archived_base():
    for c in MANIFEST['cells']:
        doc = json.loads(fbarchive.decompress(fbarchive.ROOT / c['archive_path']))
        assert doc['factor_base']['construction']['basis'] == [1 << j for j in range(c['l'])]
        exps = doc['field']['modulus_exponents']
        assert sorted(exps, reverse=True) == sorted([c['n']] + lhd.POLYS[c['n']], reverse=True)
        L = lhd.Lhd(c['n'], c['l'])
        mine = set()
        for x in range(1, 1 << c['l']):
            P = L.E.lift(x)
            if P is not None:
                mine.add(P)
                mine.add(L.E.neg(P))
        want = {tuple(p) for p in doc['points']}
        assert want <= mine, (c['n'], c['l'])
        for P in mine - want:
            Q = L.E.add(P, P)
            assert L.E.add(Q, Q) is None, (c['n'], c['l'], P)
