#!/usr/bin/env python3
"""Instantiate the exact six-candidate selector proof at norm 71023."""
from hashlib import sha256
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-variable-orbit-radix-20261014' / 'NearestOrbit19183Selector.lean'
PARENT_SHA256 = 'c1d78ecec4a7b74473dd405e38ba773b2ed5784a9d6f2e49565caa830e87c462'


def main():
    source = PARENT.read_text()
    assert sha256(source.encode()).hexdigest() == PARENT_SHA256
    source = source.replace('NearestOrbit19183','NearestOrbit71023')
    for old,new in [('19183','71023'),('140','268'),('277','533'),
                    ('38366','142046'),('6348','23497')]:
        source = re.sub(r'\b'+old+r'\b',new,source)
    assert '19183' not in source
    output = HERE / 'NearestOrbit71023Selector.lean'
    output.write_text(source)
    print(sha256(source.encode()).hexdigest())


if __name__ == '__main__':
    main()
