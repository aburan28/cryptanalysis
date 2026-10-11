"""The weight bases behind this run are archived, and indexcalc.factorBase rebuilds them.

    python3 -m pytest experiments/sage-ic-campaign/pb-bulk-halftrace-20260924 -q
"""

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'fb-archive'))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'ecc2k130', 'runner', 'codegen'))
import fbarchive  # noqa: E402

with open(os.path.join(HERE, 'factor_bases.json')) as _f:
    MANIFEST = json.load(_f)


def test_recorded_orbit_counts_match_the_archive():
    by_n = {c['n']: c for c in MANIFEST['cells']}
    seen = set()
    for path in glob.glob(os.path.join(HERE, 'run-*', 'degree-*.json')):
        if path.endswith('-parent.json'):
            continue
        n = int(os.path.basename(path)[len('degree-'):-len('.json')])
        with open(path) as f:
            found = [int(v) for v in re.findall(r'"orbits":\s*(\d+)', f.read())]
        assert found, path
        assert set(found) == {by_n[n]['effective_columns']}, path
        seen.add(n)
    assert seen == set(by_n)


def test_indexcalc_rebuilds_the_archived_bases():
    import curves
    import indexcalc
    for c in MANIFEST['cells']:
        if c['n'] > 53:
            continue  # n = 131 is checked by fbarchive verify's digest; a rebuild here is slow
        nv = curves.NormalView(c['n'])
        base, orbits = indexcalc.factorBase(nv, curves.CurvePb(nv.pb), c['w'])
        doc = json.loads(fbarchive.decompress(fbarchive.ROOT / c['archive_path']))
        assert {p[0] for p in base.values()} == {x for x, _ in doc['points']}
        assert len(orbits) == c['effective_columns']
