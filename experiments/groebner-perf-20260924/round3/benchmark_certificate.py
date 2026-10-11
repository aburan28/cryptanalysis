"""Serial paired verifier-only measurements on content-addressed frozen inputs."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'pdp-scaling'))
from boolean_certificate_native import certify_boolean_basis_native, load_library, DEFAULT_LIBRARY
spec = importlib.util.spec_from_file_location('frozen_python_certificate', HERE / 'baseline/boolean_basis.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--output', type=Path, default=HERE / 'results/certificate-benchmark.json')
    args = parser.parse_args()
    if args.repeats < 2: raise ValueError('need at least two measured pairs')
    source_paths = [HERE / 'inputs.json', HERE / 'baseline/boolean_basis.py',
                    HERE.parent.parent / 'pdp-scaling/boolean_certificate.cpp',
                    HERE.parent.parent / 'pdp-scaling/boolean_certificate_native.py',
                    DEFAULT_LIBRARY, Path(__file__)]
    start = time.perf_counter_ns()
    load_library()
    initialization_ns = time.perf_counter_ns()-start
    report = {'schema': 'boolean-certificate-component-measurement-v1',
              'scope': 'Verifier-only algebra component diagnostic, not an IC candidate comparison or complete DLP cost',
              'complete_dlp_cost': None, 'natural_relation_yield': None,
              'inputs': 'Frozen exact equations and candidate bases; planted systems are correctness controls',
              'timing': 'Input Python lists resident; includes per-call packing, native allocations/evaluation, complete certificate and output unpacking; no numerical caches. Python and native arms alternate. Compilation, file loading and one library initialization separate.',
              'library_initialization_ns': initialization_ns, 'repeats': args.repeats,
              'warmups': 'One pair retained per case; charged totals include warmups',
              'host': platform.platform(), 'load_start': os.getloadavg(),
              'python': sys.version, 'sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
              'cells': [], 'status': 'running'}
    for case in json.loads((HERE / 'inputs.json').read_text())['cases']:
        data = case['input']
        functions = {'python': lambda: old.certify_boolean_basis(data['nvars'], data['equations'], data['basis'], monomial_cache=data['nvars'] <= 12),
                     'native': lambda: certify_boolean_basis_native(data['nvars'], data['equations'], data['basis'])}
        cell = {'name': case['name'], 'workload_sha256': case['workload_sha256'], 'nvars': data['nvars'],
                'equations': len(data['equations']), 'terms': sum(map(len, data['equations'])), 'samples': []}
        report['cells'].append(cell)
        for repetition in range(args.repeats+1):
            sample = {'repetition': repetition, 'warmup': repetition == 0, 'load': os.getloadavg(), 'arms': {}}
            cell['samples'].append(sample)
            for name in (('python', 'native') if repetition % 2 == 0 else ('native', 'python')):
                start = time.perf_counter_ns()
                try:
                    answer = functions[name]()
                    elapsed = time.perf_counter_ns()-start
                    assert answer['verified'], answer
                    sample['arms'][name] = {'wall_ns': elapsed, 'status': 'verified', 'certificate': answer}
                except Exception as error:
                    sample['arms'][name] = {'wall_ns': time.perf_counter_ns()-start, 'status': 'error', 'detail': str(error)}
                    report['status'] = 'failed'
                    args.output.write_text(json.dumps(report, indent=2)+'\n')
                    raise
            assert sample['arms']['python']['certificate']['solutions'] == sample['arms']['native']['certificate']['solutions']
            args.output.write_text(json.dumps(report, indent=2)+'\n')
        measured = cell['samples'][1:]
        cell['median_ns'] = {name: statistics.median(s['arms'][name]['wall_ns'] for s in measured) for name in functions}
        logs = [math.log(s['arms']['python']['wall_ns']/s['arms']['native']['wall_ns']) for s in measured]
        cell['paired_geomean_speedup'] = math.exp(statistics.mean(logs))
        rng = random.Random(2026092405)
        bootstrap = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs)))) for _ in range(10000))
        cell['paired_bootstrap_95pct'] = [bootstrap[250], bootstrap[9749]]
        cell['charged_ns_including_warmup'] = {name: sum(s['arms'][name]['wall_ns'] for s in cell['samples']) for name in functions}
        print(case['name'], cell['median_ns'], cell['paired_geomean_speedup'], flush=True)
    report['status'] = 'PASS'
    report['load_end'] = os.getloadavg()
    report['uncertainty'] = 'Within-case paired bootstrap over five timed repeats by default; shared-host descriptive intervals, no population or unseen-workload inference'
    args.output.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__': main()
