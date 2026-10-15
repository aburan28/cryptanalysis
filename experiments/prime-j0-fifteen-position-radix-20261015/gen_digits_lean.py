#!/usr/bin/env python3
"""Instantiate the finite selected-digit certificate at norm 71023."""
from hashlib import sha256
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-variable-orbit-radix-20261014' / 'NearestOrbit19183Digits.lean'
PARENT_SHA256 = '233bf2956463eda3f0edd13dac7e3fa7c06e9e22b04dc95164794ca595a40d77'


def main():
    source = PARENT.read_text()
    assert sha256(source.encode()).hexdigest() == PARENT_SHA256
    source = source.replace('NearestOrbit19183','NearestOrbit71023')
    for old,new in [('19183','71023'),('140','268'),
                    ('9592','35512'),('6348','23497')]:
        source = re.sub(r'\b'+old+r'\b',new,source)
    assert '19183' not in source
    output = HERE / 'NearestOrbit71023Digits.lean'
    output.write_text(source)
    print(sha256(source.encode()).hexdigest())


if __name__ == '__main__':
    main()
