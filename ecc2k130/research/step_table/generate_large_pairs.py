"""Materialize a synthetic two-step table within an explicit coordinate budget.

Default: H=128, 33,536 signed directions, 562,348,416 unordered pairs,
20,244,542,976 coordinate bytes within 24 GB. H=256 produces 80,976,964,608
bytes and fits --budget-gb 88. No challenge target, walk, or solver is run.
"""

import argparse
import hashlib
import json
import math
import pathlib
import platform
import random
import shutil
import struct
import subprocess
import time

import pack
import table
from curves import CurvePb
from field import Pb

HERE = pathlib.Path(__file__).resolve().parent
POLY = (1 << 131) | (1 << 13) | 7


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while data := source.read(8 << 20):
            digest.update(data)
    return digest.hexdigest()


def writeField(out, value):
    if not 0 <= value < 1 << 192:
        raise ValueError('field/scalar encoding overflow')
    out.write(value.to_bytes(24, 'little'))


def decode(data):
    if len(data) != 36:
        raise ValueError('short point')
    words = struct.unpack('<9I', data)
    if words[8] == 0x80000000 and not any(words[:8]):
        return None
    if words[8] & ~63:
        raise ValueError('invalid packed flags/top bits')
    x = sum(words[i] << (32 * i) for i in range(4)) | ((words[8] & 7) << 128)
    y = sum(words[4 + i] << (32 * i) for i in range(4)) | ((words[8] >> 3) << 128)
    return x, y


def pairIndex(u, v):
    if u > v:
        u, v = v, u
    return v * (v + 1) // 2 + u


def pairIndices(index):
    v = (math.isqrt(8 * index + 1) - 1) // 2
    return index - v * (v + 1) // 2, v


def prepare(outDir, branches, seed):
    original = json.loads((HERE / 'table32-20260921.json').read_text())
    # Verify the existing source identity and basis conversion before reuse.
    pack.pack(original, 8)
    headerPath = table.ROOT / 'generated/eccF131.h'
    toPb = pack.columns(headerPath.read_text(), 'GAMMA_TO_PB')
    base = [pack.linear(int(v, 16), toPb) for v in original['generator']]
    target = [pack.linear(int(v, 16), toPb) for v in original['target']]
    ell, eigen = int(original['ell']), int(original['eigenvalue'])
    powers = [pow(eigen, k, ell) for k in range(131)]
    seen, rows = set(), []
    for h in range(branches):
        for attempt in range(1024):
            a = table.coefficient(seed, h, 0, attempt, ell)
            b = table.coefficient(seed, h, 1, attempt, ell)
            effective = (a + table.KNOWN * b) % ell
            orbitKey = min(min(effective * s % ell, -effective * s % ell) for s in powers)
            if effective and orbitKey not in seen:
                break
        else:
            raise RuntimeError('cannot find a new signed Frobenius orbit')
        seen.add(orbitKey)
        rows.append({'branch': h, 'attempt': attempt, 'a': str(a), 'b': str(b),
                     'effectiveSyntheticScalar': str(effective)})
    coeffs = {'schema': 'ecc2k-pair-coefficients-v1', 'scope': 'synthetic', 'seed': seed,
              'branches': branches, 'ell': str(ell), 'frobeniusEigenvalue': str(eigen),
              'knownScalar': table.KNOWN, 'generatorPolynomial': [hex(v) for v in base],
              'targetPolynomial': [hex(v) for v in target], 'rows': rows,
              'directionIndex': 'd = 2*(k*H+h)+eps; delta_d=(-1)^eps * sigma^k(T_h)',
              'pairCoefficients': 'sum the two signed sigma-scaled (a,b) labels modulo ell'}
    (outDir / 'coefficients.json').write_text(json.dumps(coeffs, indent=2) + '\n')
    with (outDir / 'input.bin').open('xb') as out:
        out.write(struct.pack('<Q', branches))
        for value in base + target + [ell]:
            writeField(out, value)
        for row in rows:
            for key in ('a', 'b', 'effectiveSyntheticScalar'):
                writeField(out, int(row[key]))
    field = Pb(131, POLY)
    rng = random.Random(87211)
    vectors = [(0, 0), (1, 1), ((1 << 131) - 1, (1 << 131) - 1)]
    vectors += [(1 << i, 1 << j) for i in (0, 1, 63, 64, 127, 128, 129, 130) for j in range(131)]
    vectors += [(rng.getrandbits(131), rng.getrandbits(131)) for _ in range(256)]
    with (outDir / 'vectors.bin').open('xb') as out:
        out.write(struct.pack('<Q', len(vectors)))
        for a, b in vectors:
            for value in (a, b, field.mul(a, b), field.inv(a) if a else 0):
                writeField(out, value)
    return coeffs, len(vectors)


def audit(outDir, branches, count, seed, samples):
    curve = CurvePb(Pb(131, POLY))
    directions = (outDir / 'directions.bin').read_bytes()
    if len(directions) != 2 * 131 * branches * 36:
        raise AssertionError('wrong source direction size')
    points = [decode(directions[i:i + 36]) for i in range(0, len(directions), 36)]
    source = json.loads((outDir / 'coefficients.json').read_text())
    # Compare every conjugate of the original 32-entry prefix to the earlier,
    # independently generated normal-basis artifact when coefficients match.
    prefixChecks = 0
    if seed == 20260921:
        reference = (HERE / 'packed-20260921/table32.bin').read_bytes()
        for k in range(131):
            for h in range(min(branches, 32)):
                expected = decode(reference[(k * 32 + h) * 36:(k * 32 + h + 1) * 36])
                actual = points[2 * (k * branches + h)]
                if actual != expected or points[2 * (k * branches + h) + 1] != curve.neg(expected):
                    raise AssertionError('existing normal-basis reference mismatch')
                prefixChecks += 1
    # Independent Python scalar multiplication checks for the new base rows.
    generator = tuple(int(v, 16) for v in source['generatorPolynomial'])
    scalarChecks = 0
    for h in range(0, branches, max(1, branches // 16)):
        expected = curve.mul(generator, int(source['rows'][h]['effectiveSyntheticScalar']))
        if points[2 * h] != expected:
            raise AssertionError('independent scalar check failed')
        scalarChecks += 1
    rng = random.Random(902117)
    indices = {0, count - 1}
    indices.update(rng.randrange(count) for _ in range(samples))
    for direction in list(range(min(32, len(points)))) + [len(points) - 2, len(points) - 1]:
        for index in (pairIndex(direction, direction), pairIndex(direction & ~1, direction | 1)):
            if index < count:
                indices.add(index)
    with (outDir / 'pairs.partial.bin').open('rb') as raw:
        for index in sorted(indices):
            u, v = pairIndices(index)
            if pairIndex(u, v) != index:
                raise AssertionError('pair index round trip failed')
            raw.seek(index * 36)
            actual = decode(raw.read(36))
            expected = curve.add(points[u], points[v])
            if actual != expected or not curve.onCurve(actual):
                raise AssertionError('independent pair audit failed at %d' % index)
    return {'independentPairChecks': len(indices), 'normalBasisPrefixChecks': prefixChecks,
            'independentScalarChecks': scalarChecks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    parser.add_argument('--branches', type=int, default=128)
    parser.add_argument('--budget-gb', type=int, default=24, help='coordinate payload budget in decimal GB')
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--seed', type=int, default=20260921)
    parser.add_argument('--limit', type=int, default=0, help='bounded prefix for testing; zero materializes all pairs')
    parser.add_argument('--audit-samples', type=int, default=256)
    parser.add_argument('--cxx', default='clang++')
    args = parser.parse_args()
    if (args.branches not in (8, 16, 32, 64, 128, 256) or args.budget_gb < 1 or
            not 1 <= args.threads <= 32 or args.limit < 0 or args.audit_samples < 1):
        parser.error('invalid bounds')
    directions = 2 * 131 * args.branches
    total = directions * (directions + 1) // 2
    count = min(args.limit, total) if args.limit else total
    budgetBytes = args.budget_gb * 1_000_000_000
    if count * 36 > budgetBytes:
        parser.error('coordinate payload exceeds the %d GB budget' % args.budget_gb)
    args.out.mkdir(parents=True, exist_ok=False)
    if shutil.disk_usage(args.out).free < count * 36 + (2 << 30):
        raise RuntimeError('insufficient free space with 2 GiB headroom')
    paths = [HERE / p for p in ('large_pairs.cpp', 'generate_large_pairs.py', 'table.py', 'pack.py',
                                'table32-20260921.json', 'packed-20260921/table32.bin')]
    paths += [table.ROOT / p for p in ('codegen/field.py', 'codegen/curves.py', 'generated/eccF131.h')]
    sources = {str(p.relative_to(table.ROOT)): sha(p) for p in paths}
    for source in paths:
        destination = args.out / 'sources' / source.relative_to(table.ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        if sha(destination) != sources[str(source.relative_to(table.ROOT))]:
            raise RuntimeError('source changed while taking snapshot')
    compiler = subprocess.run([args.cxx, '--version'], text=True, capture_output=True, check=True).stdout
    binary = args.out / 'generator'
    compileCommand = [args.cxx, '-O3', '-std=c++17', '-pthread', '-Wall', '-Wextra']
    if platform.machine() == 'arm64':
        compileCommand.append('-march=armv8-a+crypto')
    compileCommand += [str(HERE / 'large_pairs.cpp'), '-o', str(binary)]
    built = subprocess.run(compileCommand, text=True, capture_output=True, timeout=120)
    (args.out / 'build.log').write_text(built.stdout + built.stderr)
    built.check_returncode()
    begun = time.perf_counter()
    print('preparing coefficients and independent field vectors', flush=True)
    coeffs, vectorCount = prepare(args.out, args.branches, args.seed)
    command = [str(binary.resolve()), str((args.out / 'input.bin').resolve()),
               str((args.out / 'vectors.bin').resolve()), str((args.out / 'pairs.partial.bin').resolve()),
               str((args.out / 'directions.bin').resolve()), str(args.threads), str(args.limit)]
    receipt = None
    with (args.out / 'generation.log').open('x') as log:
        process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in process.stdout:
            print(line, end='', flush=True); log.write(line); log.flush()
            if line.startswith('{'):
                receipt = json.loads(line)
        code = process.wait()
    if code or receipt is None:
        raise RuntimeError('native generation failed; partial output and log preserved')
    partial = args.out / 'pairs.partial.bin'
    if (receipt['entries'] != count or receipt['onCurveChecked'] != count or
            receipt['bytes'] != count * 36 or partial.stat().st_size != count * 36 or
            receipt['complete'] != (count == total)):
        raise RuntimeError('incomplete output or invalid receipt')
    print('auditing disk samples against independent Python curve arithmetic', flush=True)
    checks = audit(args.out, args.branches, count, args.seed, args.audit_samples)
    print('hashing the complete materialized payload', flush=True)
    payloadHash = sha(partial)
    if sources != {str(p.relative_to(table.ROOT)): sha(p) for p in paths}:
        raise RuntimeError('source changed during generation')
    partial.rename(args.out / 'pairs.bin')
    manifest = {'schema': 'ecc2k-large-pair-table-v1', 'scope': 'synthetic-precomputation-only',
                'complete': count == total, 'branches': args.branches, 'signedDirections': directions,
                'entries': count, 'fullTableEntries': total, 'bytes': count * 36,
                'budgetBytes': budgetBytes, 'coordinateBasis': 'polynomial',
                'polynomial': 'z^131+z^13+z^2+z+1', 'knownScalar': table.KNOWN,
                'layout': 'unordered pair u<=v; index=v*(v+1)/2+u; 36 bytes per entry',
                'directionLayout': coeffs['directionIndex'],
                'encoding': 'little-endian uint32[9]: x_lo[4], y_lo[4], x_top|y_top<<3; infinity=(0,...,0,0x80000000)',
                'payloadSha256': payloadHash, 'sourceSha256': sources,
                'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)}
                          for p in [args.out / n for n in ('coefficients.json', 'directions.bin', 'input.bin', 'vectors.bin', 'generator')]},
                'validation': receipt | checks | {'independentFieldVectors': vectorCount},
                'compiler': compiler, 'compileCommand': compileCommand, 'command': command,
                'threads': args.threads, 'platform': platform.platform(),
                'elapsedSeconds': time.perf_counter() - begun,
                'allocatedBytes': (args.out / 'pairs.bin').stat().st_blocks * 512,
                'limitations': ['pair sums only; no intermediate-tag predictor is implemented',
                                'no measured rho group-operation reduction or GPU speedup',
                                'synthetic target and new index/exception ABI; incompatible with production checkpoints']}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: manifest[k] for k in ('complete', 'entries', 'bytes', 'payloadSha256', 'elapsedSeconds')}, indent=2))


if __name__ == '__main__':
    main()
