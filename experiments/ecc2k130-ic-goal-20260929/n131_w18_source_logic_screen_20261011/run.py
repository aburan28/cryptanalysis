"""Exact W18 rational-mask ANF and reduced-BDD variable-order census."""

import hashlib
import importlib.util
import json
import random
import resource
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SUPPORT = ROOT/'n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv'
CIRCUIT = ROOT/'n131_w18_cubic_correct_target_20261011/circuit.py'
N = 18
SIZE = 1 << N


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_paths():
    return {'run.py': Path(__file__), 'freeze.py': HERE/'freeze.py',
            'support_w18.tsv': SUPPORT,
            'n131_cubic_circuit.py': CIRCUIT}


def read_support():
    columns = {}
    for line in SUPPORT.read_text().splitlines():
        mask_text, column_text = line.split()
        mask, column = int(mask_text), int(column_text)
        assert 0 <= mask < SIZE and mask not in columns
        columns[mask] = column
    assert len(columns) == 131307 and len(set(columns.values())) == 131068
    return columns


def anf(invalid):
    coefficients = bytearray(invalid)
    for bit in range(N):
        step = 1 << bit
        for base in range(0, SIZE, step << 1):
            for offset in range(step):
                coefficients[base+step+offset] ^= coefficients[base+offset]
    by_degree = [0]*(N+1)
    for mask, value in enumerate(coefficients):
        if value:
            by_degree[mask.bit_count()] += 1
    return coefficients, by_degree


def ordered_table(valid_masks, order):
    weight = [0]*N
    for depth, bit in enumerate(order):
        weight[bit] = 1 << (N-1-depth)
    remap = [0]*SIZE
    for mask in range(1, SIZE):
        low = mask & -mask
        remap[mask] = remap[mask^low] ^ weight[low.bit_length()-1]
    table = bytearray(SIZE)
    for mask in valid_masks:
        table[remap[mask]] = 1
    return table


def reduced_bdd_nodes(table):
    ids = list(table)
    count = 0
    levels = []
    for _ in range(N):
        memo = {}
        next_ids = []
        for index in range(0, len(ids), 2):
            left, right = ids[index], ids[index+1]
            if left == right:
                next_ids.append(left)
            else:
                key = (left, right)
                node = memo.get(key)
                if node is None:
                    node = count+2
                    count += 1
                    memo[key] = node
                next_ids.append(node)
        ids = next_ids
        levels.append(len(memo))
    assert len(ids) == 1
    return count, levels


def main():
    protocol = json.loads((HERE/'protocol.json').read_text())
    assert protocol['status'] == 'FROZEN_BEFORE_SOURCE_LOGIC_SCREEN'
    assert protocol['source_sha256'] == {name: sha(path)
                                         for name, path in source_paths().items()}
    if (HERE/'result.json').exists():
        raise FileExistsError('result.json')
    began = time.monotonic()
    columns = read_support()
    valid_masks = tuple(columns)
    invalid = bytearray([1])*SIZE
    for mask in valid_masks:
        invalid[mask] = 0
    coefficients, by_degree = anf(invalid)
    baseline_order = tuple(range(N-1, -1, -1))
    baseline_count, baseline_levels = reduced_bdd_nodes(
        ordered_table(valid_masks, baseline_order))
    spec = importlib.util.spec_from_file_location('frozen_n131_circuit', CIRCUIT)
    circuit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(circuit)
    _, frozen_nodes = circuit.build_bdd(columns)
    assert baseline_count == len(frozen_nodes) == 31118
    rng = random.Random(protocol['permutation_seed'])
    alternatives = []
    for index in range(protocol['random_orders']):
        order = list(range(N))
        rng.shuffle(order)
        node_count, _ = reduced_bdd_nodes(ordered_table(valid_masks, order))
        alternatives.append({'index': index, 'root_to_leaf_bits': order,
                             'bdd_nodes': node_count})
        if time.monotonic()-began > protocol['wall_cap_seconds']:
            raise TimeoutError('source logic screen exceeded wall cap')
    best = min(alternatives, key=lambda row: (row['bdd_nodes'], row['index']))
    result = {'status': 'COMPLETE_EXACT_SOURCE_LOGIC_SCREEN',
              'curve_id': 'EC1N131Ckb1heb5f1998f20b',
              'source_dimension': N, 'valid_masks': len(valid_masks),
              'invalid_masks': SIZE-len(valid_masks),
              'folded_columns': len(set(columns.values())),
              'invalidity_anf_terms_by_degree': by_degree,
              'invalidity_anf_terms': sum(by_degree),
              'invalidity_anf_degree': max(i for i, count in enumerate(by_degree) if count),
              'invalidity_anf_sha256': hashlib.sha256(coefficients).hexdigest(),
              'baseline_bdd_nodes': baseline_count,
              'baseline_bdd_nodes_by_bottom_level': baseline_levels,
              'alternative_orders': alternatives,
              'best_alternative': best,
              'median_alternative_nodes': sorted(row['bdd_nodes'] for row in alternatives)[len(alternatives)//2],
              'wall_seconds_exploratory': time.monotonic()-began,
              'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'source_sha256': {'protocol.json': sha(HERE/'protocol.json')}}
    assert result['peak_process_rss_bytes'] < protocol['rss_cap_bytes']
    (HERE/'result.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': result['status'],
                      'anf_terms': result['invalidity_anf_terms'],
                      'baseline_bdd_nodes': baseline_count,
                      'best_alternative_nodes': best['bdd_nodes']}))


if __name__ == '__main__':
    main()
