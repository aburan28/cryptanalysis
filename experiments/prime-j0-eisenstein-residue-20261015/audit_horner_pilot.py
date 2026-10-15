#!/usr/bin/env python3
"""Replay the frozen Horner pilot receipts against native and Lean provenance."""

from hashlib import sha256
from pathlib import Path
import json
import tarfile

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE/'horner-native-provenance.tar.gz'
HASHES = {
    'prime-j0-alt-radix-horner-pilot': {
        'src/bin/eisenstein_fixed.rs':'aa9a33724c6c909f429d68119e6b4a9912faa7d06c8226ef1f8f4e3134ac4093',
        'src/bin/eisenstein_fixed/unit_orbit_windows.rs':'8541856774a6246098499997c818a5dd301a9f1df8c0f55c330fbf49dca41a86',
        'target/release/eisenstein_fixed':'120643923bdf961f9d8c510ae656891d78617e2219592defd1740886a02e3078',
    },
    'prime-j0-alt-radix-horner-direct': {
        'src/bin/eisenstein_fixed.rs':'6cd0962b58b4673708af813a913474791400a7297142e4e5970e7af11faf0b34',
        'src/bin/eisenstein_fixed/unit_orbit_windows.rs':'4fdac347ce8cd1bf813d411b2c07ecb0b036644958b28d2af6bee6ed7b45036d',
        'target/release/eisenstein_fixed':'eefdefc12a3eb9d540acc4417444a29edefd86394c0bdc3734c7ac0ad6216afe',
    },
    'prime-j0-alt-radix-horner-terminal-g': {
        'src/bin/eisenstein_fixed.rs':'6cd0962b58b4673708af813a913474791400a7297142e4e5970e7af11faf0b34',
        'src/bin/eisenstein_fixed/unit_orbit_windows.rs':'6b0a9c23f8fbbd846b41da35779ea381e095eeeca2ce050fb5cc65e12249c76c',
        'target/release/eisenstein_fixed':'fd44f97a0201767923098a23a084b2a30ca24ec4a9028ab1e248f25d55adbf02',
    },
}


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def main():
    with tarfile.open(ARCHIVE,'r:gz') as archive:
        fixture_bytes = archive.extractfile(
            'prime-j0-alt-radix-horner-direct/src/bin/mixed640_uniform_fixture.json').read()
        cases = json.loads(fixture_bytes)['cases']
        for stem,files in HASHES.items():
            for name,expected in files.items():
                assert digest(archive.extractfile(f'{stem}/{name}').read()) == expected
            assert archive.extractfile(
                f'{stem}/src/bin/mixed640_uniform_fixture.json').read() == fixture_bytes
        overlay = archive.extractfile('native_alt_horner_overlay.py').read()
        assert overlay == (HERE/'native_alt_horner_overlay.py').read_bytes()
    receipt = {'schema':1,'fixture_sha256':digest(fixture_bytes),
               'provenance_sha256':digest(ARCHIVE.read_bytes()),
               'overlay_sha256':digest(overlay),'native_hashes':HASHES,
               'pilots':[]}
    for name,count,direct in (
        ('horner-pilot-1.stdout',1,False),
        ('horner-pilot-128.stdout',128,False),
        ('horner-pilot-12288.stdout',12288,False),
        ('horner-direct-pilot-12288.stdout',12288,True),
        ('horner-terminal-g-pilot-12288.stdout',12288,True),
    ):
        data=(HERE/name).read_bytes()
        fields=dict(word.split('=',1) for word in data.decode().split())
        assert fields['verified'] == '1'
        assert int(fields['count']) == count
        assert int(fields['retained_bytes']) == 2566612
        assert fields['point'] == cases[count-1]['point_hex']
        assert float(fields['online_ms']) > 0
        if direct:
            assert float(fields['preparation_ms']) > 0
        else:
            assert 'preparation_ms' not in fields
        receipt['pilots'].append({'file':name,'sha256':digest(data),
                                  'count':count,'fields':fields})
    proof=json.loads((HERE/'horner-lean-check.json').read_text())
    assert proof['toolchain'] == 'leanprover/lean4:v4.34.1'
    assert all(step['returncode'] == 0 for step in proof['steps'])
    assert 'sorryAx' not in proof['steps'][-1]['output']
    receipt['lean_receipt_sha256']=digest((HERE/'horner-lean-check.json').read_bytes())
    (HERE/'horner-pilot-audit.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'verified_counts':[1,128,12288,12288,12288],
                      'retained_bytes':2566612,'ok':True},sort_keys=True))


if __name__ == '__main__':
    main()
