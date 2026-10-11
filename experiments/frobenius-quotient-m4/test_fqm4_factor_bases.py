"""Every ladder cell's factor base is archived in experiments/fb-archive, and the base
indexcalc.factorBase builds (what ladder.py runs on) is exactly the archived point set.

    python3 -m pytest experiments/frobenius-quotient-m4 -q
"""

import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'fb-archive'))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'ecc2k130', 'runner', 'codegen'))
import fbarchive  # noqa: E402
import ps1  # noqa: E402

MANIFEST = os.path.join(HERE, 'results', 'factor_bases.json')


def loadManifest():
    with open(MANIFEST) as f:
        return json.load(f)


def archived(cell):
    doc = json.loads(fbarchive.decompress(fbarchive.ROOT / cell['archive_path']))
    return doc


def test_every_result_cell_has_an_archived_base():
    cells = {(c['n'], c['l']) for c in loadManifest()['cells']}
    for path in glob.glob(os.path.join(HERE, 'results', 'cell_*.json')) + [os.path.join(HERE, 'results', 'smoke_n7.json')]:
        with open(path) as f:
            rec = json.load(f)
        assert (rec['n'], rec['weight']) in cells, path


def test_manifest_matches_index_and_file():
    for c in loadManifest()['cells']:
        row = ps1.index_row(c['n'], 'nbweight', c['l'])
        assert row['factor_base_sha256'] == c['factor_base_sha256']
        data = (fbarchive.ROOT / c['archive_path']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['file_sha256']
        doc = archived(c)
        assert doc['factor_base_sha256'] == c['factor_base_sha256']


def test_ladder_base_is_the_archived_base():
    import curves
    import indexcalc
    for c in loadManifest()['cells']:
        nv = curves.NormalView(c['n'])
        E = curves.CurvePb(nv.pb)
        base, orbits = indexcalc.factorBase(nv, E, c['l'])
        doc = archived(c)
        want = {x for x, _ in doc['points']}
        got = {p[0] for p in base.values()}
        assert got == want, (c['n'], c['l'])
        assert len(orbits) == doc['factor_base']['effective_columns']
