"""Exact compactness diagnostics for the N41 target-conditioned support."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    data = json.loads((HERE/'receipt.json').read_text())
    replay = json.loads((HERE/'sage_replay.json').read_text())
    assert data['status'] == 'COMPLETE_EXACT_FIBER'
    assert replay['status'] == 'PASS_ALL_12_TRANSPORTED_N41_ROWS_SAGE'
    support = set(data['prefix_support'][0])
    assert len(support) == 11 and support <= set(range(1, 64))
    anchor = min(support)
    span = {0}
    for value in support:
        difference = value ^ anchor
        span |= {x ^ difference for x in tuple(span)}
    affine_rank = (len(span)-1).bit_length()
    linear_equalities = []
    for mask in range(1, 64):
        values = {bin(x & mask).count('1') & 1 for x in support}
        if len(values) == 1:
            linear_equalities.append({'mask': mask, 'value': values.pop()})
    anf = [int(i in support) for i in range(64)]
    for bit in range(6):
        for index in range(64):
            if index & (1 << bit):
                anf[index] ^= anf[index ^ (1 << bit)]
    terms_by_degree = [sum(anf[i] for i in range(64)
                           if bin(i).count('1') == degree) for degree in range(7)]
    assert sum(terms_by_degree) == sum(anf)
    result = {'status': 'PASS_EXACT_N41_TARGET_SUPPORT_ANALYSIS',
              'source_domain_size': data['pair_sum_domain_sizes'][0],
              'target_supported_first_pair_sums': sorted(support),
              'target_supported_count': len(support),
              'excluded_domain_count': 63-len(support),
              'excluded_domain_fraction': '52/63',
              'affine_hull_rank': affine_rank,
              'nontrivial_linear_equalities': linear_equalities,
              'indicator_anf_terms_by_degree': terms_by_degree,
              'indicator_algebraic_degree': max(i for i, n in enumerate(terms_by_degree) if n),
              'prefix_support_sizes': data['prefix_support_sizes'],
              'target_dependent_construction_ns': data['online_ns'],
              'reusable_index_build_ns': data['setup_ns'],
              'source_sha256': {'receipt.json': sha(HERE/'receipt.json'),
                                'sage_replay.json': sha(HERE/'sage_replay.json'),
                                'analyze.py': sha(HERE/'analyze.py')}}
    assert affine_rank == 6 and not linear_equalities
    (HERE/'analysis.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': result['status'],
                      'excluded_domain_fraction': result['excluded_domain_fraction'],
                      'affine_hull_rank': affine_rank,
                      'indicator_algebraic_degree': result['indicator_algebraic_degree']}))


if __name__ == '__main__':
    main()
