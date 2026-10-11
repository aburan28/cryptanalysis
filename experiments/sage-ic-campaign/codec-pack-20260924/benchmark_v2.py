"""Paired complete-plan benchmark for the Sage NTL output codec."""
import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import random
import resource
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path

from sage.all import EllipticCurve, GF, set_random_seed
from sage.schemes.elliptic_curves import binary_hardware, binary_hardware_codec

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def incumbent_hardware():
    old_so = next((HERE / 'baseline').glob('binary_hardware_codec*.so'))
    package_name = '_codec_output_incumbent'
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package
    name = package_name + '.binary_hardware_codec'
    spec = importlib.util.spec_from_file_location(name, old_so)
    old_codec = importlib.util.module_from_spec(spec)
    sys.modules[name] = old_codec
    spec.loader.exec_module(old_codec)
    assert old_codec is not binary_hardware_codec
    spec = importlib.util.spec_from_file_location('old_binary_hardware',
                                                   binary_hardware.__file__)
    old_hardware = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old_hardware)
    old_hardware._codec = old_codec
    return old_hardware


def worker(case, backend, out):
    set_random_seed(case['seed'])
    field = GF(2**case['degree'], 'z', impl='ntl')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    base, attempts = generate(curve, min(case['points'], 128), case['seed'])
    points = [base[i % len(base)] for i in range(case['points'])]
    if len(points) > 2:
        points[0], points[1] = curve(0), curve(0, 1)
    phi = curve.frobenius_isogeny(case['power'] % case['degree'])
    expected = [phi(P) for P in points]
    old_hardware = incumbent_hardware()
    assert old_hardware._codec.__file__ != binary_hardware_codec.__file__
    plans = {}
    setup = {}
    for arm, module in (('incumbent', old_hardware), ('candidate', binary_hardware)):
        start = time.perf_counter_ns()
        plans[arm] = module.FrobeniusPlan(curve, case['power'], backend=backend,
                                         cpu_threads=1)
        setup[arm] = (time.perf_counter_ns() - start) / 1e9
        assert plans[arm].codec == 'native-ntl'

    def checked(arm, calls):
        start = time.perf_counter_ns()
        for _ in range(calls):
            actual = plans[arm].apply(points)
            if actual != expected:
                raise AssertionError(f'{arm}: wrong point map')
            del actual
        return (time.perf_counter_ns() - start) / 1e9 / calls

    for arm in plans:
        checked(arm, 1)
    calls = max(4, math.ceil(131072 / case['points']))
    orders = list(itertools.permutations(plans)) * 6
    random.Random(case['seed'] + case['degree'] + case['points']).shuffle(orders)
    samples = []
    for order in orders:
        samples.append({'order': order, 'seconds': {arm: checked(arm, calls)
                                                    for arm in order}})
    for plan in plans.values():
        plan.close()
    logs = [math.log(s['seconds']['incumbent'] / s['seconds']['candidate'])
            for s in samples]
    row = {'case': case, 'backend': backend, 'rounds': samples, 'setup_seconds': setup,
           'calls_per_sample': calls, 'verified_outputs': case['points'] * calls * 24,
           'all_outputs_exact': True, 'fixture_attempts': attempts,
           'speedup': math.exp(statistics.median(logs)),
           'incumbent_ms': 1000 * statistics.median(
               s['seconds']['incumbent'] for s in samples),
           'candidate_ms': 1000 * statistics.median(
               s['seconds']['candidate'] for s in samples),
           'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'incumbent_binary_sha256': sha(old_hardware._codec.__file__),
           'candidate_binary_sha256': sha(binary_hardware_codec.__file__)}
    out.write_text(json.dumps(row, indent=2) + '\n')
    print(case, backend, f'{row["speedup"]:.3f}x', flush=True)


def parent(out):
    intent = json.loads((HERE / 'intent-candidate-v2.json').read_text())
    install = json.loads((HERE / 'install-002/install.json').read_text())
    old_so = next((HERE / 'baseline').glob('binary_hardware_codec*.so'))
    assert sha(old_so) == intent['incumbent']['binary_sha256']
    assert sha(HERE / 'baseline/binary_hardware_codec.pyx') == intent['incumbent']['source_sha256']
    assert sha(binary_hardware_codec.__file__) == install['files'][1]['sha256']
    assert sha(ROOT / 'third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_hardware_codec.pyx') == install['files'][0]['sha256']
    out.mkdir(parents=True, exist_ok=False)
    (out / 'execution.json').write_text(json.dumps({
        'intent_sha256': sha(HERE / 'intent-candidate-v2.json'),
        'benchmark_sha256': sha(__file__),
        'incumbent_binary_sha256': sha(old_so),
        'candidate_binary_sha256': sha(binary_hardware_codec.__file__),
        'candidate_source_sha256': sha(ROOT / 'third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_hardware_codec.pyx'),
    }, indent=2) + '\n')
    rows = []
    for phase in ('primary', 'confirmation'):
        for index, item in enumerate(intent[phase + '_cases']):
            for backend in intent['backends']:
                case = dict(item, phase=phase,
                            seed=(intent['seed_base_primary'] if phase == 'primary' else intent['seed_base_confirmation']) + index)
                path = out / f'cell-{len(rows):02d}.json'
                command = [sys.executable, str(Path(__file__).resolve()), '--case',
                           json.dumps(case), '--backend', backend, '--worker-out', str(path)]
                start = time.perf_counter()
                with (out / f'cell-{len(rows):02d}.log').open('w') as log:
                    try:
                        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                                timeout=300)
                        status = result.returncode
                    except subprocess.TimeoutExpired:
                        status = 'timeout'
                (out / f'cell-{len(rows):02d}-parent.json').write_text(json.dumps({
                    'case': case, 'backend': backend, 'status': status,
                    'parent_seconds': time.perf_counter() - start,
                }, indent=2) + '\n')
                if status != 0:
                    print('FAILED', case, backend, status, flush=True)
                    raise SystemExit(1)
                row = json.loads(path.read_text())
                rows.append(row)
                print(phase, case['degree'], case['points'], case['power'], backend,
                      f'{row["speedup"]:.3f}x', flush=True)
                (out / 'summary.json').write_text(json.dumps({
                    'cells': [{k: r[k] for k in ('case', 'backend', 'speedup',
                                                'incumbent_ms', 'candidate_ms')}
                              for r in rows],
                    'all_outputs_exact': all(r['all_outputs_exact'] for r in rows),
                    'total_verified_outputs': sum(r['verified_outputs'] for r in rows),
                }, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    parser.add_argument('--case')
    parser.add_argument('--backend', choices=('cpu', 'metal'))
    parser.add_argument('--worker-out', type=Path)
    args = parser.parse_args()
    if args.case:
        worker(json.loads(args.case), args.backend, args.worker_out)
    else:
        parent(args.out)
