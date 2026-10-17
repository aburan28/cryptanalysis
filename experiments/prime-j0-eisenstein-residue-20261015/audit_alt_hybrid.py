#!/usr/bin/env python3
"""Check both exact-replay hybrid reduction receipts and frozen provenance."""

from hashlib import sha256
from pathlib import Path
import json
import tarfile

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE/'alt-hybrid-native-provenance.tar.gz'
STEM = 'prime-j0-alt-hybrid-native/'
EXPECTED = {
    'src/bin/eisenstein_fixed.rs':'de40496bb017b072ca6290282da9a7484f967adfaef9d50093f1a186b6c1b8ed',
    'src/bin/eisenstein_fixed/unit_orbit_windows.rs':'63016940c38510331f776aa7e9f77d7b3e34aaf11d941bc816023c0760bc74fd',
    'target/release/eisenstein_fixed':'7828311ea3bc43822c2db50cacf3c2e17b5158328cef03e536fca75c8df3ff0f',
    'src/bin/mixed640_uniform_fixture.json':'a1c4964f174e36ea26f6a1897128f651a2ce7251e4bf4ffd532ff09221e721d3',
}


def main():
    assert sha256(ARCHIVE.read_bytes()).hexdigest() == '18cd292b61920873fa67cac896021ca5778d33d39a3ea803ee1fe31abfb25df5'
    with tarfile.open(ARCHIVE,'r:gz') as archive:
        for member,expected in EXPECTED.items():
            assert sha256(archive.extractfile(STEM+member).read()).hexdigest() == expected
        overlay = archive.extractfile(STEM+'native_alt_hybrid_overlay.py').read()
        assert sha256(overlay).hexdigest() == sha256((HERE/'native_alt_hybrid_overlay.py').read_bytes()).hexdigest()
        fixture = json.loads(archive.extractfile(STEM+'src/bin/mixed640_uniform_fixture.json').read())
        results = {}
        for depth in (2,3):
            prefix=f'hybrid{depth}-full-replay'
            assert archive.extractfile(STEM+prefix+'.stderr').read() == b''
            raw=archive.extractfile(STEM+prefix+'.stdout').read().decode().strip()
            fields=dict(word.split('=',1) for word in raw.split())
            assert fields['verified']=='1' and fields['count']=='12288'
            assert fields['fixture_sha256']==EXPECTED['src/bin/mixed640_uniform_fixture.json']
            assert fields['retained_bytes']=='27429548'
            assert fields['scalar']==fixture['cases'][-1]['scalar_hex']
            assert fields['point']==fixture['cases'][-1]['point_hex']
            results[str(depth)]={'online_ms_diagnostic':float(fields['online_ms']),
                                 'preparation_ms_diagnostic':float(fields['preparation_ms'])}
    print(json.dumps({'schema':1,'status':'verified_exact_replay','measurement_tier':'diagnostic',
                      'count_per_variant':12288,'retained_bytes':27429548,
                      'archive_sha256':sha256(ARCHIVE.read_bytes()).hexdigest(),
                      'hybrid_depths':results},sort_keys=True,indent=2))


if __name__=='__main__':
    main()
