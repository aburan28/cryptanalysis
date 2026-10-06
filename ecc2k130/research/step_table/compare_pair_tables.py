"""Check that a larger complete table embeds the smaller table's directions.

H changes the direction stride, so old byte offsets are not new byte offsets.
This audit compares all old directions and remapped samples of pair sums.
"""
import argparse
import hashlib
import json
import pathlib
import random

import generate_large_pairs as large


def compare(small, big, samples=2048):
    sm = json.loads((small / 'manifest.json').read_text())
    bm = json.loads((big / 'manifest.json').read_text())
    if not sm['complete'] or not bm['complete']:
        raise ValueError('both tables must be complete')
    sh, bh = sm['branches'], bm['branches']
    if not 0 < sh < bh:
        raise ValueError('expected a larger branch count')
    sc = json.loads((small / 'coefficients.json').read_text())
    bc = json.loads((big / 'coefficients.json').read_text())
    for key in ('scope', 'seed', 'ell', 'frobeniusEigenvalue', 'knownScalar',
                'generatorPolynomial', 'targetPolynomial'):
        if sc[key] != bc[key]:
            raise AssertionError('different coefficient domain: ' + key)
    if sc['rows'] != bc['rows'][:sh]:
        raise AssertionError('base coefficient prefix differs')
    smallDirections = (small / 'directions.bin').read_bytes()
    bigDirections = (big / 'directions.bin').read_bytes()
    if len(smallDirections) != 2 * 131 * sh * 36 or len(bigDirections) != 2 * 131 * bh * 36:
        raise AssertionError('incorrect direction file size')

    def remap(direction):
        phase, branch = divmod(direction // 2, sh)
        return 2 * (phase * bh + branch) + (direction & 1)

    n = len(smallDirections) // 36
    for d in range(n):
        target = remap(d)
        if smallDirections[d * 36:(d + 1) * 36] != bigDirections[target * 36:(target + 1) * 36]:
            raise AssertionError('direction mismatch at %d' % d)
    rng = random.Random(881310)
    pairs = {(0, 0), (0, 1), (n - 1, n - 1), (n - 2, n - 1), (0, n - 1)}
    pairs.update(tuple(sorted((rng.randrange(n), rng.randrange(n)))) for _ in range(samples))
    with (small / 'pairs.bin').open('rb') as sf, (big / 'pairs.bin').open('rb') as bf:
        for u, v in sorted(pairs):
            sf.seek(36 * large.pairIndex(u, v))
            bf.seek(36 * large.pairIndex(remap(u), remap(v)))
            a, b = sf.read(36), bf.read(36)
            if len(a) != 36 or a != b:
                raise AssertionError('remapped pair differs at %d,%d' % (u, v))
    return {'schema': 'ecc2k-pair-extension-audit-v1', 'passed': True,
            'smallerBranches': sh, 'largerBranches': bh,
            'directionsChecked': n, 'remappedPairsChecked': len(pairs),
            'smallerPayloadSha256': sm['payloadSha256'], 'largerPayloadSha256': bm['payloadSha256'],
            'smallerManifestSha256': hashlib.sha256((small / 'manifest.json').read_bytes()).hexdigest(),
            'largerManifestSha256': hashlib.sha256((big / 'manifest.json').read_bytes()).hexdigest(),
            'comparisonSourceSha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
            'note': 'pair samples read from disk; full payload hashes are the recorded generation hashes'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('small', type=pathlib.Path)
    parser.add_argument('big', type=pathlib.Path)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    args = parser.parse_args()
    result = compare(args.small, args.big)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
