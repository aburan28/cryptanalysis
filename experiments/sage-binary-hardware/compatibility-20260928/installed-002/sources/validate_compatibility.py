"""Validate installed arithmetic on this host; never load archived binaries.

Run with the checked local Sage launcher. On other hardware use its rebuilt
fork. Every requested backend must execute successfully; missing hardware
is a failed request, not a silently skipped test or a compatibility claim.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time
import traceback
import unittest


def file_record(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def run_suite(suite, path):
    started = time.perf_counter()
    with path.open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return {'status': 'pass' if result.wasSuccessful() and not result.skipped else 'fail',
            'tests': result.testsRun, 'failures': len(result.failures),
            'errors': len(result.errors), 'skipped': len(result.skipped),
            'elapsed_seconds': time.perf_counter()-started, 'log': path.name}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backends', default='cpu', help='comma-separated cpu,metal,cuda,opencl')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    backends = args.backends.split(',')
    if len(set(backends)) != len(backends) or any(b not in ('cpu', 'metal', 'cuda', 'opencl') for b in backends):
        parser.error('select unique backends from cpu,metal,cuda,opencl')
    args.out.mkdir(parents=True, exist_ok=False)
    snapshot = args.out/'sources'
    snapshot.mkdir()
    for name in ('validate_compatibility.py', 'test_portability.py', 'test_hardware.py', 'load_hardware.py'):
        shutil.copyfile(Path(__file__).with_name(name), snapshot/name)
    report = {'schema': 1, 'status': 'fail', 'platform': platform.platform(),
              'architecture': platform.machine(), 'byteorder': sys.byteorder,
              'python': sys.executable, 'python_version': sys.version,
              'requested_backends': backends, 'backends': {},
              'scope': 'installed full-API correctness; no timing or cross-device speed claim',
              'validator': file_record(__file__),
              'tests': [file_record(Path(__file__).with_name(name))
                        for name in ('test_portability.py', 'test_hardware.py')]}
    try:
        for name in ('SAGE_BINARY_CANDIDATE', 'SAGE_BINARY_NATIVE', 'SAGE_BINARY_CODEC'):
            if os.environ.get(name):
                raise RuntimeError(f'installed validation forbids {name}')
        os.environ['SAGE_BINARY_USE_INSTALLED'] = '1'
        import sage.all
        from sage.all import EllipticCurve, GF
        from sage.env import SAGE_VERSION
        from load_hardware import FrobeniusPlan, artifacts
        report['sage_version'] = SAGE_VERSION
        report['hardware_artifacts'] = artifacts()
        report['modules'] = {}
        for name in ('ell_point', 'binary_batch', 'binary_batch_ntl', 'binary_hardware', 'binary_hardware_codec'):
            module = importlib.import_module('sage.schemes.elliptic_curves.' + name)
            report['modules'][name] = file_record(module.__file__)
        manifest = os.environ.get('SAGE_LOCAL_RUNTIME_MANIFEST')
        if manifest:
            report['runtime_manifest'] = file_record(manifest)
        import test_portability
        report['scalar_and_batch'] = run_suite(
            unittest.defaultTestLoader.loadTestsFromModule(test_portability), args.out/'scalar-and-batch.txt')
        print('scalar_and_batch:', report['scalar_and_batch']['status'], flush=True)
        import test_hardware
        for backend in backends:
            try:
                E = EllipticCurve(GF(2**19, 'z'), [1, 1, 0, 0, 1])
                with FrobeniusPlan(E, 1, backend) as plan:
                    if plan.apply([E(0, 1)]) != [E(0, 1)]:
                        raise AssertionError('backend probe returned an incorrect point')
                    device = {'name': plan.device_name, 'codec': plan.codec,
                              'backend': plan.backend, 'gpu_seconds': plan.last_gpu_seconds}
                test_hardware.BACKENDS = [backend]
                result = run_suite(unittest.defaultTestLoader.loadTestsFromModule(test_hardware),
                                   args.out/f'{backend}.txt')
                report['backends'][backend] = {**result, 'device': device}
            except Exception:
                report['backends'][backend] = {'status': 'fail', 'error': traceback.format_exc()}
            print(backend + ':', report['backends'][backend]['status'], flush=True)
        if (report['scalar_and_batch']['status'] == 'pass'
                and all(result['status'] == 'pass' for result in report['backends'].values())):
            report['status'] = 'pass'
    except Exception:
        report['error'] = traceback.format_exc()
    (args.out/'receipt.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
