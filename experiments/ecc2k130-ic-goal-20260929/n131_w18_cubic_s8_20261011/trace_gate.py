"""Exact trace propagation through the W18 reciprocal sum tree."""

import json
from pathlib import Path

import circuit

HERE = Path(__file__).resolve().parent


def main():
    field = circuit.Field()
    support = {int(a) for a, _ in
               (line.split() for line in
                (circuit.ROOT/'n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv')
                .read_text().splitlines())}
    basis_trace = [circuit.old.trace(field, 1 << (i+1)) for i in range(18)]
    assert basis_trace == [0]*18
    assert all(circuit.old.trace(field, mask << 1) == 0
               for mask in (min(support), max(support), 3, 4, 17, 18, 19, 22, 24, 25))
    target = json.loads((circuit.ROOT/'n131_fixed_seed_eight_pair_circuit_20261010/target_preimages.json').read_text())
    rows = [{'index': row['index'], 'reciprocal_x_z': row['reciprocal_x_z'],
             'trace': circuit.old.trace(field, row['reciprocal_x_z'])}
            for row in target['preimages']]
    assert [row['trace'] for row in rows] == [0, 1, 0, 1]
    fixture = json.loads((HERE/'fixture.json').read_text())
    assert all(circuit.old.trace(field, value) == 0 for value in
               fixture['pair_reciprocals'] + fixture['middle_reciprocals'] +
               [fixture['raw_target_reciprocal']])
    record = {'status': 'PASS_TRACE_ZERO_TARGET_PREIMAGE_GATE',
              'field_degree': 131, 'source_trace_zero_basis_count': 18,
              'public_workload_id': target['workload_id'],
              'preimages': rows, 'admissible_raw_preimage_indices': [0, 2],
              'proof': 'Tr(a+b+c)=0 is necessary for each S3 link; Tr(a)=Tr(b)=0 at every W18 leaf, so every internal reciprocal and the target reciprocal has trace zero.'}
    (HERE/'trace_gate_result.json').write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': record['status'],
                      'admissible_raw_preimage_indices': record['admissible_raw_preimage_indices']}))


if __name__ == '__main__':
    main()
