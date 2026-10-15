#!/usr/bin/env python3
"""Instantiate selected-step and trajectory proofs for the 15-position radix."""
from hashlib import sha256
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-variable-orbit-radix-20261014'
SOURCES = {
    'Step': 'd915b110cb1f8c270485d37dc3d3e00c3abc6555af79865414ad3f6281cf2848',
    'Complete': '23edc987ab52f6e32d11b924d45b08be73e40bfc77ea8e94aa1b54f43ebb0a8c',
}


def main():
    for suffix, expected in SOURCES.items():
        source = (PARENT / f'NearestOrbit19183{suffix}.lean').read_text()
        assert sha256(source.encode()).hexdigest() == expected
        source = source.replace('NearestOrbit19183','NearestOrbit71023')
        for old,new in [('19183','71023'),('140','268'),('137','265'),
                        ('9591','35511'),('9592','35512'),('6348','23497'),
                        ('80','154'),('17','15'),('16','14'),('78','82')]:
            source = re.sub(r'\b'+old+r'\b',new,source)
        assert '19183' not in source
        output = HERE / f'NearestOrbit71023{suffix}.lean'
        output.write_text(source)
        print(output.name, sha256(source.encode()).hexdigest())


if __name__ == '__main__':
    main()
