"""Offline fixture construction only; never imported by the query runtime."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'pdp-scaling'))
from descend import make_instance
from gf2n import Curve, GF2n


def generate():
    fixture = HERE.parent / 'round13/results/confirmation.json.gz'
    cases = json.loads(gzip.decompress(fixture.read_bytes()))['inputs']
    targets = {}
    for case in cases:
        if case['boundary'] != 'pdp':
            continue
        inst = make_instance(case['n'], case['m'], case['ell'], seed=case['seed'], build_anf=False)
        point = Curve(GF2n(inst.n, inst.mod), inst.b).sum(inst.points)
        assert point.x == case['target_x'] and not point.inf
        targets[case['name']] = {'target': [point.x, point.y, False],
                                 'workload_sha256': case['workload_sha256'],
                                 'source': 'original frozen planted correctness fixture; not natural yield'}
    return targets


if __name__ == '__main__':
    target = HERE / 'public_targets.json'
    value = generate()
    if target.exists():
        assert json.loads(target.read_text()) == value
    else:
        target.write_text(json.dumps(value, indent=2) + '\n')
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    print('PUBLIC_TARGETS_CHECKED', len(value), digest)
