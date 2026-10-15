#!/usr/bin/env python3
"""Instantiate the checked norm-step proof structure at the 15-position radix."""
from hashlib import sha256
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-variable-orbit-radix-20261014' / 'NearestOrbit19183Bound.lean'
PARENT_SHA256 = '557173d193fdee0e91885cd10c87d57b45ff4e45a9e4cf63f954780a4ad05b5b'


def main():
    original = PARENT.read_text()
    assert sha256(original.encode()).hexdigest() == PARENT_SHA256
    radii = json.loads((HERE / 'screen268.json').read_text())['radius_sequence']
    assert len(radii) == 16 and radii[-1] == 82
    start = original.index('def radius (i : Nat) : Int :=')
    end = original.index('theorem radius_checks',start)
    source = original[:start]+original[end:]
    source = source.replace('List.range 137','List.range 265')
    source = source.replace('theorem norm_trial_division :',
                            'set_option maxRecDepth 100000 in\ntheorem norm_trial_division :')
    source = source.replace('NearestOrbit19183','NearestOrbit71023')
    for old,new in [('19183','71023'),('140','268'),('137','265'),
                    ('17','15'),('16','14'),('80','154'),('78','82')]:
        source = re.sub(r'\b'+old+r'\b',new,source)
    location = source.index('theorem radius_checks')
    radius_def = ('def radius (i : Nat) : Int :=\n  ([\n    '
                  + ',\n    '.join(str(r) for r in radii)
                  + '] : List Int).getD i 0\n\n')
    source = source[:location]+radius_def+source[location:]
    assert '19183' not in source and 'NearestOrbit71023' in source
    output = HERE / 'NearestOrbit71023Bound.lean'
    output.write_text(source)
    print(sha256(source.encode()).hexdigest())


if __name__ == '__main__':
    main()
