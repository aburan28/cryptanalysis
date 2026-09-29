"""Measure whether faster RREF alone can make the bounded hybrid competitive."""
import argparse
from contextlib import ExitStack
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / 'round27'))
from full_query import BaselineQuery
from conditional import Native
from sparse_checker import Curve, GF2n
from descend import make_instance
sys.path.insert(0, str(HERE.parent / 'round10'))
from hybrid_query import HybridQuery, QueryStats


class PackedHybrid(HybridQuery):
    """Feed the current descent's existing uint32/uint64 views to the hybrid."""
    def compute(self, anf):
        with self._lock:
            if not self._handle:
                raise RuntimeError('hybrid workspace is closed')
            started = time.perf_counter()
            masks, width, coefficients = Native.views(self, anf)
            if width != 32:
                raise ValueError('hybrid requires uint32 monomial views')
            stats = QueryStats()
            handle = self._solver.hybrid_compute(self._handle, masks, coefficients,
                                                 len(masks), ctypes.byref(stats))
            if not handle:
                raise RuntimeError(self._solver.hybrid_error().decode())
            try:
                basis = [list(self._solver.hybrid_row_data(handle, i)[
                    :self._solver.hybrid_row_size(handle, i)]) for i in range(stats.basis_rows)]
            finally:
                self._solver.hybrid_destroy(handle)
            produced = time.perf_counter()
            certificate = self._certify(masks, coefficients, basis)
            finished = time.perf_counter()
            return {'status': 'gb' if certificate['verified'] else 'verification-failed',
                    'complete': certificate['verified'], 'basis_terms': basis,
                    'basis_sha256': hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest(),
                    'basis_seconds': stats.total, 'wall_seconds': produced-started,
                    'verification_seconds': finished-produced, 'basis_certificate': certificate,
                    'groebner_verified': certificate['verified'],
                    'generators_reduce_to_zero': certificate['verified'],
                    'transport': 'direct-packed-native-descent-views', 'coefficient_copy': False,
                    'metrics': {name: getattr(stats, name) for name, _ in stats._fields_},
                    'binary_sha256': self._binary_sha256,
                    'verifier_binary_sha256': self._verifier_sha256}


class HybridPublicQuery(BaselineQuery):
    def __init__(self, *shape):
        super().__init__(*shape, arm='sparse')
        try:
            self.basis.close()
            self.basis = PackedHybrid(shape[3]*shape[4], shape[0], backend='cpu')
            self.basis._certify = self.checker.certify_views
            self.basis.verifier_path = self.checker.path
            self.basis._verifier_sha256 = self.checker.binary_sha256
        except Exception:
            self.close()
            raise


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=7)
    args = parser.parse_args()
    if args.output.exists() or not 2 <= args.repetitions <= 31:
        parser.error('fresh output and 2..31 repetitions required')
    if sys.platform == 'darwin':
        lib = ctypes.CDLL(None)
        if lib.pthread_set_qos_class_self_np(0x19, 0):
            raise RuntimeError('USER_INITIATED QoS failed')
    report = {'schema': 'hybrid-query-diagnostic/1', 'status': 'RUNNING',
              'scope': 'Single public-point PDP query; planted controls; no IC result',
              'candidate_id': None, 'IC_online_ms': None, 'rho_online_ms': None,
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'platform': platform.platform(), 'logical_cpus': os.cpu_count(),
              'load_initial': os.getloadavg(), 'repetitions': args.repetitions,
              'arms': ['hybrid-cpu', 'evaluation'], 'rows': [], 'inputs': [], 'setup': [],
              'boundary': 'Public point validation, fresh native packed descent, complete basis, identical independent sparse certification, original-equation and full signed curve replay; setup and fixture construction excluded.',
              'projection': 'query wall minus measured hybrid elimination is a zero-RREF-cost counterfactual, not an observed GPU result; all other work is held fixed.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')

    def admitted():
        if os.getloadavg()[0] > report['logical_cpus']:
            raise RuntimeError('load admission rejected')

    rng = random.Random(2026092931)
    save()
    try:
        admitted()
        with ExitStack() as stack:
            field = GF2n(31)
            shape = (31, field.mod, 1, 3, 4)
            queries = {}
            for arm in report['arms']:
                start = time.perf_counter_ns()
                queries[arm] = stack.enter_context(HybridPublicQuery(*shape) if arm == 'hybrid-cpu'
                                                  else BaselineQuery(*shape, arm='sparse'))
                q = queries[arm]
                report['setup'].append({'arm': arm, 'wall_ns': time.perf_counter_ns()-start,
                    'solver_sha256': digest(q.basis.solver_path), 'checker_sha256': q.checker.binary_sha256,
                    'descent_sha256': q.descent.binary_sha256, 'replay_sha256': q.replay.binary_sha256})
            # Includes the two matrix captures and three separate controls.
            for seed in (1, 2, 3, 4, 5):
                fixture = make_instance(31, 3, 4, seed=seed)
                oracle = Curve(GF2n(31, fixture.mod), fixture.b)
                target = oracle.sum(fixture.points)
                report['inputs'].append({'seed': seed, 'target': vars(target), 'shape': shape,
                                         'anf': sorted(fixture.anf.items())})
                for rep in range(args.repetitions+1):
                    admitted()
                    order = report['arms'][:]
                    rng.shuffle(order)
                    row = {'seed': seed, 'repetition': rep, 'warmup': rep == 0,
                           'order': order, 'load': os.getloadavg()}
                    for arm in order:
                        start = time.perf_counter_ns()
                        answer = queries[arm].solve(target)
                        row[arm] = {'wall_ns': time.perf_counter_ns()-start, 'result': answer}
                        if not answer.get('verified') or fixture.evaluate(answer['assignment']):
                            raise RuntimeError('query or untouched equations failed')
                    a, b = [row[arm]['result'] for arm in report['arms']]
                    if sorted(map(tuple, a['basis_terms'])) != sorted(map(tuple, b['basis_terms'])):
                        raise RuntimeError('canonical basis mismatch')
                    row['load_end'] = os.getloadavg()
                    report['rows'].append(row)
                    save()
                    admitted()
                print('seed', seed, 'passed', flush=True)
        report['status'] = 'PASS'
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = repr(error)
        raise
    finally:
        paths = {Path(m.__file__).resolve() for m in list(sys.modules.values())
                 if getattr(m, '__file__', None) and Path(m.__file__).resolve().is_relative_to(ROOT)}
        for receipt in (HERE.parent/'round20/build/receipt.json', HERE.parent/'round23/build/receipt.json'):
            value = json.loads(receipt.read_text())
            paths.update(ROOT/name for name in value['source_sha256'])
        paths.update(HERE.parent/'round10'/name for name in ('build.py', 'hybrid_query.mm', 'hybrid_query.py'))
        paths.update(ROOT/'experiments/pdp-scaling'/name for name in ('boolean_f5b_native.cpp', 'boolean_f5b_m4ri.cpp'))
        report['source_sha256'] = {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths) if p.is_file()}
        report['load_final'] = os.getloadavg()
        save()
    for seed in (1, 2, 3, 4, 5):
        samples = [r for r in report['rows'] if r['seed'] == seed and not r['warmup']]
        timings = {a: statistics.median(r[a]['wall_ns']/1e6 for r in samples) for a in report['arms']}
        timings['zero_elimination_counterfactual_ms'] = statistics.median(
            r['hybrid-cpu']['wall_ns']/1e6 - 1000*r['hybrid-cpu']['result']['metrics']['elimination']
            for r in samples)
        print(seed, timings)


if __name__ == '__main__':
    main()
