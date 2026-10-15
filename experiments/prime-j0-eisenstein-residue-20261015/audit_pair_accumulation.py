#!/usr/bin/env python3
"""Check the exact prototype source, executable, fixture, and replay receipt."""

from hashlib import sha256
from pathlib import Path
import json
import tarfile

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE/'pair-accumulation-native-provenance.tar.gz'
STEM = 'prime-j0-pair-accumulation-native/'
EXPECTED = {
    'src/bin/eisenstein_fixed.rs':'d01813e08de0b555111d6789cbf0b2fffa239cde4fa2d4e8d75b41da81effdbc',
    'src/bin/eisenstein_fixed/unit_orbit_windows.rs':'e4ac66d2817876e151b5600d252d80a2693fb0145ade46fce51294ca4dcca6fe',
    'target/release/eisenstein_fixed':'da5d55aadf9eefbf63f8cf36ff8ea82098e9442fe11fab84c4ab635f9b017c9a',
    'src/bin/mixed640_uniform_fixture.json':'a1c4964f174e36ea26f6a1897128f651a2ce7251e4bf4ffd532ff09221e721d3',
}


def main():
    assert sha256(ARCHIVE.read_bytes()).hexdigest() == '2f36e7c6d52a85790f17428daedec09c95d3c3e936f44a655c18725ecb2c9c1f'
    with tarfile.open(ARCHIVE,'r:gz') as archive:
        for member,expected in EXPECTED.items():
            assert sha256(archive.extractfile(STEM+member).read()).hexdigest() == expected
        overlay = archive.extractfile(STEM+'native_pair_accumulation_overlay.py').read()
        assert sha256(overlay).hexdigest() == sha256((HERE/'native_pair_accumulation_overlay.py').read_bytes()).hexdigest()
        assert archive.extractfile(STEM+'pair-full-replay.stderr').read() == b''
        raw = archive.extractfile(STEM+'pair-full-replay.stdout').read().decode().strip()
        fields = dict(word.split('=',1) for word in raw.split())
        assert fields['verified'] == '1' and fields['count'] == '12288'
        assert fields['fixture_sha256'] == EXPECTED['src/bin/mixed640_uniform_fixture.json']
        assert fields['retained_bytes'] == '28825228'
        fixture = json.loads(archive.extractfile(STEM+'src/bin/mixed640_uniform_fixture.json').read())
        assert fields['point'] == fixture['cases'][-1]['point_hex']
        assert fields['scalar'] == fixture['cases'][-1]['scalar_hex']
        assert b'error[E0369]' in archive.extractfile(STEM+'pair-build.stderr').read()
    print(json.dumps({'schema':1,'status':'verified_exact_replay','measurement_tier':'diagnostic',
                      'count':12288,'retained_bytes':28825228,
                      'online_ms_diagnostic':float(fields['online_ms']),
                      'preparation_ms_diagnostic':float(fields['preparation_ms']),
                      'archive_sha256':sha256(ARCHIVE.read_bytes()).hexdigest()},sort_keys=True,indent=2))


if __name__ == '__main__':
    main()
