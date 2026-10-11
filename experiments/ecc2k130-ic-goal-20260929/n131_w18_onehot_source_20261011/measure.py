"""Freeze, measure, and independently replay one-hot membership in the N131 tree."""

import argparse
import hashlib
import importlib.util
import json
import resource
import sys
import time
from pathlib import Path

from onehot import emit, rows_from_codes

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORKSPACE = Path('/Volumes/SSD990/cryptanalysis')
SOURCE = ROOT/'n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv'
BASE = ROOT/'n131_w18_cubic_correct_trace_20261011'
BASE_RUN = ROOT/'n131_w18_cubic_correct_target_20261011/run.py'
sys.path.insert(0, str(WORKSPACE/'experiments/koblitz-polynomial-w-pair-20260925'))
from karatsuba_circuit import KaratsubaCircuit

spec = importlib.util.spec_from_file_location('trace_circuit_onehot', BASE/'circuit.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
run_spec = importlib.util.spec_from_file_location('cubic_run_onehot', BASE_RUN)
base_run = importlib.util.module_from_spec(run_spec)
sys.path.insert(0, str(BASE_RUN.parent))
run_spec.loader.exec_module(base_run)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_columns():
    return {int(a): int(b) for a, b in (line.split() for line in SOURCE.read_text().splitlines())}


def source_paths():
    return {'onehot.py': HERE/'onehot.py', 'measure.py': HERE/'measure.py',
            'source_table': SOURCE, 'trace_circuit.py': BASE/'circuit.py',
            'base_run.py': BASE_RUN,
            'karatsuba_circuit.py': WORKSPACE/'experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py'}


def freeze():
    columns = load_columns()
    assert len(columns) == 131307 and len(set(columns.values())) == 131068
    protocol = {'status': 'FROZEN_BEFORE_FORMULA_MEASUREMENT', 'curve_id': 'EC1N131Ckb1heb5f1998f20b',
                'candidate_id': None, 'workload_id': 'cc09e7eb202a',
                'source_dimension': 18, 'split_bits': [9, 9], 'row_parity_group_width': 6,
                'source_valid_masks': len(columns), 'source_rows': 512,
                'public_target': json.loads((BASE/'protocol.json').read_text())['public_target'],
                'source_sha256': {key: sha(value) for key, value in source_paths().items()},
                'scope': 'exact source predicate and one full public formula; no solver timing claim'}
    (HERE/'protocol.json').write_text(json.dumps(protocol, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': protocol['status'], 'valid_masks': len(columns)}))


def measure():
    protocol = json.loads((HERE/'protocol.json').read_text())
    assert protocol['source_sha256'] == {key: sha(value) for key, value in source_paths().items()}
    columns = load_columns()
    rows = rows_from_codes(columns)
    assert sum(map(len, rows)) == len(columns)
    original_bdd, original_emit = base.build_bdd, base.emit_bdd
    base.build_bdd = lambda codes: (0, {})
    base.emit_bdd = lambda c, root, nodes, mask: emit(c, mask, rows)
    try:
        target = json.loads((BASE/'protocol.json').read_text())['raw_target_preimage_z']
        began = time.monotonic()
        circuit = KaratsubaCircuit(131, [0, 1, 2, 13])
        meta = base.build(circuit, base.Field(), columns, target)
        construct = time.monotonic() - began
    finally:
        base.build_bdd, base.emit_bdd = original_bdd, original_emit
    begin_write = time.monotonic()
    formula_path = HERE/'public_formula.xcnf'
    circuit.write(formula_path)
    write = time.monotonic() - begin_write
    formula = {'variables': circuit.next_var-1, 'and_gates': circuit.and_count,
               'clauses': len(circuit.clauses), 'native_xor_rows': len(circuit.xors),
               'bytes': formula_path.stat().st_size, 'sha256': sha(formula_path),
               'source_and_gates': meta['source_and_gates'],
               'source_product_and_gates': meta['source_product_and_gates'],
               'pair_link_and_gates': meta['pair_link_and_gates'],
               'joint_link_and_gates': meta['joint_link_and_gates']}
    formula_path.unlink()
    result = {'status': 'EXACT_FORMULA_CONSTRUCTED', 'candidate_id': None,
              'public_target': protocol['public_target'], 'workload_id': protocol['workload_id'],
              'formula': formula,
              'phase_seconds_exploratory': {'construction': construct, 'write_and_hash': write},
              'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'source_sha256': {'protocol.json': sha(HERE/'protocol.json')}}
    (HERE/'result.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('freeze', 'measure'))
    args = parser.parse_args()
    {'freeze': freeze, 'measure': measure}[args.mode]()
