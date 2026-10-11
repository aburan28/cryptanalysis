"""Independent truth-table and constructed eight-point assignment replay."""

import hashlib
import json
import random
from pathlib import Path

import measure
from onehot import emit, rows_from_codes

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE/'protocol.json').read_text())
    assert protocol['source_sha256'] == {key: sha(value) for key, value in measure.source_paths().items()}
    columns = measure.load_columns()
    rows = rows_from_codes(columns)
    valid = set(columns)
    # This loops over the complete domain, independently of the circuit builder.
    for code in range(1 << 18):
        assert ((code & 511) in rows[code >> 9]) == (code in valid)

    circuit = measure.KaratsubaCircuit(131, [0, 1, 2, 13])
    bits = [circuit.variable() for _ in range(18)]
    output = emit(circuit, bits, rows)
    assert output > 0 and circuit.clauses[-1] == f'-{circuit.xor((output, -1))} 0'
    rng = random.Random(20261011)
    good = rng.sample(sorted(valid), 32)
    bad = rng.sample(sorted(set(range(1 << 18)) - valid), 32)
    for code in good + bad:
        inputs = {wire: (code >> i) & 1 for i, wire in enumerate(bits)}
        values = measure.base_run.complete_assignment(circuit, inputs)
        assert values[output] == (code in valid)
        for clause in circuit.clauses[:-1]:
            assert any(values[abs(lit)] == (lit > 0)
                       for lit in map(int, clause.split()[:-1]))
        assert all(sum(values[abs(lit)] ^ (lit < 0)
                       for lit in map(int, row.split()[1:-1])) & 1
                   for row in circuit.xors)
        final = int(circuit.clauses[-1].split()[0])
        assert (values[abs(final)] == (final > 0)) == (code in valid)

    original_bdd, original_emit = measure.base.build_bdd, measure.base.emit_bdd
    measure.base.build_bdd = lambda codes: (0, {})
    measure.base.emit_bdd = lambda c, root, nodes, mask: emit(c, mask, rows)
    try:
        fixture = json.loads((measure.BASE/'fixture.json').read_text())
        full = measure.KaratsubaCircuit(131, [0, 1, 2, 13])
        meta = measure.base.build(full, measure.base.Field(), columns,
                                  [fixture['raw_target_reciprocal']])
    finally:
        measure.base.build_bdd, measure.base.emit_bdd = original_bdd, original_emit
    primary = {}
    def bind(wires, number):
        primary.update({wire: (number >> bit) & 1 for bit, wire in enumerate(wires)})
    for wires, number in zip(meta['masks'], fixture['masks']):
        bind(wires, number)
    for wires, number in zip(meta['pair_z'], fixture['pair_reciprocals']):
        bind(wires, number)
    for wires, number in zip(meta['middle_z'], fixture['middle_reciprocals']):
        bind(wires, number)
    for wire, bit in zip(meta['branch'], fixture['branch_bits']):
        primary[wire] = bit
    assert len(primary) == len(meta['primary_variables'])
    assignment = measure.base_run.complete_assignment(full, primary)
    checked = measure.base_run.check_assignment(full, assignment)
    result = {'status': 'PASS_EXHAUSTIVE_TABLE_AND_FULL_CONSTRUCTED_ASSIGNMENT',
              'curve_id': protocol['curve_id'], 'workload_id': protocol['workload_id'],
              'truth_table_entries': 1 << 18, 'source_valid_masks': len(valid),
              'source_circuit_positive_cases': len(good),
              'source_circuit_negative_cases': len(bad),
              'full_control_source_masks': fixture['masks'],
              'full_control_target': fixture['projected_target'],
              'full_control_clauses': checked['clauses'],
              'full_control_native_xor_rows': checked['native_xor_rows'],
              'source_sha256': {'protocol.json': sha(HERE/'protocol.json'),
                                'result.json': sha(HERE/'result.json'),
                                'audit.py': sha(HERE/'audit.py')}}
    (HERE/'audit.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
