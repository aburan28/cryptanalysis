"""Independent ANF inversion and Shannon-BDD replay of the W18 screen."""

import hashlib
import json
import random
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def shannon_nodes(codes, order):
    unique = {}

    def visit(subset, depth):
        if not subset:
            return 0
        if len(subset) == 1 << (run.N-depth):
            return 1
        if depth == run.N:
            return 1
        bit = order[depth]
        low = [mask for mask in subset if not (mask >> bit & 1)]
        high = [mask for mask in subset if mask >> bit & 1]
        left, right = visit(low, depth+1), visit(high, depth+1)
        if left == right:
            return left
        key = depth, left, right
        if key not in unique:
            unique[key] = len(unique)+2
        return unique[key]

    visit(list(codes), 0)
    return len(unique)


def transform_descending(table):
    coefficients = bytearray(table)
    for bit in range(run.N-1, -1, -1):
        mask_bit = 1 << bit
        for mask in range(run.SIZE):
            if mask & mask_bit:
                coefficients[mask] ^= coefficients[mask^mask_bit]
    return coefficients


def main():
    protocol = json.loads((HERE/'protocol.json').read_text())
    result = json.loads((HERE/'result.json').read_text())
    assert protocol['source_sha256'] == {name: sha(path)
                                         for name, path in run.source_paths().items()}
    assert result['source_sha256']['protocol.json'] == sha(HERE/'protocol.json')
    assert result['status'] == 'COMPLETE_EXACT_SOURCE_LOGIC_SCREEN'
    assert result['wall_seconds_exploratory'] < protocol['wall_cap_seconds']
    assert result['peak_process_rss_bytes'] < protocol['rss_cap_bytes']
    columns = run.read_support()
    valid = tuple(columns)
    invalid = bytearray([1])*run.SIZE
    for mask in valid:
        invalid[mask] = 0
    coefficients = transform_descending(invalid)
    assert transform_descending(coefficients) == invalid
    by_degree = [0]*(run.N+1)
    for mask, value in enumerate(coefficients):
        if value:
            by_degree[mask.bit_count()] += 1
    assert by_degree == result['invalidity_anf_terms_by_degree']
    assert sum(by_degree) == result['invalidity_anf_terms']
    assert sha_bytes(coefficients) == result['invalidity_anf_sha256']
    baseline = tuple(range(run.N-1, -1, -1))
    assert shannon_nodes(valid, baseline) == result['baseline_bdd_nodes']
    rng = random.Random(protocol['permutation_seed'])
    for row in result['alternative_orders']:
        order = list(range(run.N))
        rng.shuffle(order)
        assert row['root_to_leaf_bits'] == order
    best = min(result['alternative_orders'], key=lambda row: (row['bdd_nodes'], row['index']))
    assert best == result['best_alternative']
    assert shannon_nodes(valid, best['root_to_leaf_bits']) == best['bdd_nodes']
    worst = max(result['alternative_orders'], key=lambda row: row['bdd_nodes'])
    assert shannon_nodes(valid, worst['root_to_leaf_bits']) == worst['bdd_nodes']
    audit = {'status': 'PASS_INDEPENDENT_W18_SOURCE_LOGIC_AUDIT',
             'truth_table_rows': run.SIZE,
             'anf_coefficients_reversed_to_truth_table': True,
             'anf_terms': sum(by_degree),
             'baseline_bdd_nodes': result['baseline_bdd_nodes'],
             'best_bdd_nodes': best['bdd_nodes'],
             'worst_bdd_nodes': worst['bdd_nodes'],
             'source_sha256': {'audit.py': sha(Path(__file__)),
                               'protocol.json': sha(HERE/'protocol.json'),
                               'result.json': sha(HERE/'result.json')}}
    (HERE/'audit.json').write_text(json.dumps(audit, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': audit['status'],
                      'anf_terms': audit['anf_terms'],
                      'best_bdd_nodes': audit['best_bdd_nodes']}))


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


if __name__ == '__main__':
    main()
