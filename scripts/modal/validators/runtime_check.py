"""Check the pinned local installation before launch; optionally probe imports.

The normal preflight uses only the standard library, outside operation timers.
--probe also loads Sage, checks actual module origins, and exercises dispatch.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = Path(__file__).with_name('runtime-current.json')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(manifest_path):
    manifest = json.loads(manifest_path.read_text())
    if manifest['schema'] != 1:
        raise RuntimeError('unsupported runtime manifest schema')
    expected_prefix = (ROOT/manifest['python_prefix']).resolve()
    if Path(sys.prefix).resolve() != expected_prefix:
        raise RuntimeError(f'wrong Python prefix: {sys.prefix}; expected {expected_prefix}')
    for entry in manifest['files']:
        path = ROOT/entry['path']
        if digest(path) != entry['sha256']:
            raise RuntimeError(f'local Sage file differs from the verified build: {path}')
    return manifest


def probe(manifest, manifest_path):
    import importlib
    from sage.all import EllipticCurve, GF, ZZ
    from sage.schemes.elliptic_curves import binary_batch
    from sage.version import version

    modules = {}
    for name, relative in manifest['modules'].items():
        module = importlib.import_module(name)
        actual = Path(module.__file__).resolve()
        expected = (ROOT/relative).resolve()
        if actual != expected:
            raise RuntimeError(f'{name} loaded from {actual}; expected {expected}')
        modules[name] = str(actual)
    F = GF(2**131, 'runtime_z', impl='ntl')
    E = EllipticCurve(F, [1, 1, 0, 0, 1])
    for i in range(2, 100):
        points = E.lift_x(F.from_integer(i), all=True)
        if points:
            P = points[0]
            break
    else:
        raise RuntimeError('could not construct the runtime probe point')
    expected = E(0)
    for unused in range(17):
        expected += P
    calls = {}
    originals = {}
    for name in manifest['native_dispatch']:
        original = getattr(binary_batch._native, name)
        originals[name] = original
        calls[name] = 0
        def counted(*args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)
        setattr(binary_batch._native, name, counted)
    try:
        assert ZZ(17)*P == expected
        assert binary_batch.add_pairs(E, [(P, P)]) == [2*P]
        image = E.frobenius_isogeny(7)(P)
        assert binary_batch.frobenius_add_pairs(E, [(P, P)], 7) == [image+P]
        if not all(calls.values()):
            raise RuntimeError(f'expected native dispatch was bypassed: {calls}')
    finally:
        for name, original in originals.items():
            setattr(binary_batch._native, name, original)
    return {'status': 'verified', 'sage_version': version, 'python': sys.executable,
            'python_prefix': sys.prefix, 'manifest': str(manifest_path.resolve()),
            'manifest_sha256': digest(manifest_path), 'modules': modules,
            'native_calls': calls, 'features': manifest['features'],
            'receipt': manifest['receipt']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    try:
        manifest = check(args.manifest)
        if args.probe:
            print(json.dumps(probe(manifest, args.manifest), indent=2))
    except (OSError, ValueError, KeyError, RuntimeError, AssertionError) as error:
        print(f'Local Sage runtime check failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
