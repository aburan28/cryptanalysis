"""Frozen N131 W18 cubic query with exact standard-reciprocal trace pruning."""

import argparse
import gzip
import hashlib
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil
import circuit

ROOT = Path('/Volumes/SSD990/cryptanalysis')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'experiments/koblitz-polynomial-w-pair-20260925'))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402

SUPPORT = circuit.ROOT / 'n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv'
PUBLIC = circuit.ROOT / 'n131_fixed_seed_eight_pair_circuit_20261010/target_preimages.json'
SOLVER = Path('/opt/homebrew/bin/cryptominisat5')
RSS_CAP = 4 * 1024**3
CONSTRUCTION_CAP = 120
SOLVER_CAP = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, record):
    Path(path).write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')


def sources():
    return {'run.py': Path(__file__), 'circuit.py': HERE/'circuit.py',
            'fixture.py': HERE/'fixture.py', 'fixture.json': HERE/'fixture.json',
            'support_w18.tsv': SUPPORT, 'target_preimages.json': PUBLIC,
            'n41_cubic_circuit.py': circuit.N41/'circuit.py',
            'basis_circuit.py': circuit.SPARSE/'circuit.py',
            'basis_sparse.py': circuit.SPARSE/'sparse.py',
            'n41_horner_circuit.py': circuit.ROOT/'n41_single_branch_horner_20261011/circuit.py',
            'karatsuba_circuit.py': ROOT/'experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py',
            'circuit_sat.py': ROOT/'experiments/koblitz-s5-invariant-20260924/circuit_sat.py',
            'corrected_full_protocol.json': HERE.parent/'n131_w18_cubic_correct_target_20261011/protocol.json',
            'cryptominisat5': SOLVER}


def source_columns():
    return {int(a): int(b) for a, b in
            (line.split() for line in SUPPORT.read_text().splitlines())}


def public():
    record = json.loads(PUBLIC.read_text())
    assert record['curve_id'] == 'EC1N131Ckb1heb5f1998f20b'
    assert record['workload_id'] == 'cc09e7eb202a'
    assert len(record['preimages']) == 4
    field = circuit.Field()
    assert all(circuit.old.trace(field, 1 << bit) == 0 for bit in range(1, 19))
    standard = []
    for index, row in enumerate(record['preimages']):
        assert row['index'] == index
        x = int(row['point'][0])
        shifted = int(row['reciprocal_x_z'])
        assert x not in (0, 1)
        assert field.mul(x ^ 1, shifted) == 1
        assert field.mul(x, shifted) == shifted ^ 1
        z = field.inv(x)
        assert field.mul(x, z) == 1 and z != shifted
        standard.append(z)
    record['standard_reciprocal_x_z'] = standard
    record['standard_reciprocal_trace'] = [circuit.old.trace(field, z) for z in standard]
    assert record['standard_reciprocal_trace'] == [0, 0, 1, 1]
    return record


def freeze():
    p = public()
    fixture = json.loads((HERE/'fixture.json').read_text())
    assert fixture['status'] == 'PASS_CONSTRUCTED_EIGHT_SLOT_GROUP_WITNESS'
    assert SOLVER.is_file()
    record = {'status': 'FROZEN_BEFORE_N131_CONTROL_AND_PUBLIC_QUERY',
              'candidate_id': None, 'curve_id': 'EC1N131Ckb1heb5f1998f20b',
              'field': 'GF(2)[t]/(t^131+t^13+t^2+t+1)',
              'subgroup_order': '680564733841876926932320129493409985129',
              'public_target': p['public_target'], 'public_workload_id': p['workload_id'],
              'raw_target_preimage_z': p['standard_reciprocal_x_z'][:2],
              'raw_target_preimage_indices': [0, 1],
              'excluded_preimage_indices': [2, 3],
              'all_standard_reciprocal_traces': p['standard_reciprocal_trace'],
              'trace_rule': 'all W18 source reciprocal coordinates have trace zero; every S3 output preserves trace sum',
              'input_binding': {
                  'circuit_coordinate': 'z=1/x',
                  'source_file_coordinate': 'reciprocal_x_z=1/(x+1)',
                  'preimage_x': [row['point'][0] for row in p['preimages']],
                  'source_shifted_z': [row['reciprocal_x_z'] for row in p['preimages']],
                  'standard_z': p['standard_reciprocal_x_z'],
                  'checks': 'x*z=1 and (x+1)*source_shifted_z=1 for all four preimages'},
              'control_target': fixture['projected_target'],
              'control_raw_z': fixture['raw_target_reciprocal'],
              'source_dimension': 18, 'rotations': circuit.ROTATIONS,
              'source_rational_masks': 131307, 'factor_base_B': 1050456,
              'folded_columns_K': 131068, 'workers': 1,
              'construction_cap_seconds': CONSTRUCTION_CAP,
              'solver_cap_seconds': SOLVER_CAP, 'parent_solver_cap_seconds': 615,
              'rss_cap_bytes': RSS_CAP,
              'solver_flags': ['--threads=1', '--xor=0', '--printsol=1',
                               '--random=20261011', '--maxtime=600'],
              'source_sha256': {name: sha(path) for name, path in sources().items()}}
    save(HERE/'protocol.json', record)
    print(json.dumps({'status': record['status'], 'public_workload_id': p['workload_id']}))


def checked_protocol():
    record = json.loads((HERE/'protocol.json').read_text())
    assert record['status'] == 'FROZEN_BEFORE_N131_CONTROL_AND_PUBLIC_QUERY'
    assert record['source_sha256'] == {name: sha(path) for name, path in sources().items()}
    return record


def build(target_zs):
    circuit_obj = KaratsubaCircuit(circuit.N, [0, 1, 2, 13])
    began = time.monotonic()
    meta = circuit.build(circuit_obj, circuit.Field(), source_columns(), target_zs)
    elapsed = time.monotonic() - began
    return circuit_obj, meta, elapsed


def profile(c, m, elapsed):
    return {'variables': c.next_var-1, 'and_gates': c.and_count,
            'clauses': len(c.clauses), 'native_xor_rows': len(c.xors),
            'construction_seconds_exploratory': elapsed,
            'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            **{key: m[key] for key in ('bdd_nodes', 'source_and_gates',
                                        'source_product_and_gates', 'pair_link_and_gates',
                                        'joint_link_and_gates',
                                        'nontrivial_column_collision_pairs')}}


def complete_assignment(c, initial):
    definitions = {int(out): ('and', int(a), int(b))
                   for (a, b), out in c.and_cache.items()}
    for line in c.xors:
        literals = [int(x) for x in line.split()[1:-1]]
        definitions[abs(literals[0])] = ('xor', literals)
    values = [None] * c.next_var
    for wire, bit in initial.items():
        values[wire] = int(bit)

    def value(wire):
        return 1 if wire == -1 else 0 if wire == 0 else values[wire]

    for wire in range(1, c.next_var):
        if values[wire] is not None:
            continue
        definition = definitions.get(wire)
        if definition is None:
            raise RuntimeError(f'unassigned primary wire {wire}')
        if definition[0] == 'and':
            values[wire] = value(definition[1]) & value(definition[2])
        else:
            literals = definition[1]
            bit = int(literals[0] > 0)
            for literal in literals[1:]:
                bit ^= values[abs(literal)] ^ int(literal < 0)
            values[wire] = bit
    return values


def check_assignment(c, values):
    for row in c.clauses:
        literals = map(int, row.split()[:-1])
        assert any(values[abs(wire)] == int(wire > 0) for wire in literals)
    for row in c.xors:
        literals = map(int, row.split()[1:-1])
        assert sum(values[abs(wire)] ^ int(wire < 0) for wire in literals) & 1
    return {'clauses': len(c.clauses), 'native_xor_rows': len(c.xors)}


def control():
    p = checked_protocol()
    fixture = json.loads((HERE/'fixture.json').read_text())
    c, m, elapsed = build([fixture['raw_target_reciprocal']])
    initial = {}

    def bind(wires, number):
        initial.update({wire: number >> bit & 1 for bit, wire in enumerate(wires)})

    for wires, number in zip(m['masks'], fixture['masks']):
        bind(wires, number)
    for wires, number in zip(m['pair_z'], fixture['pair_reciprocals']):
        bind(wires, number)
    for wires, number in zip(m['middle_z'], fixture['middle_reciprocals']):
        bind(wires, number)
    for wire, bit in zip(m['branch'], fixture['branch_bits']):
        initial[wire] = bit
    assert len(initial) == len(m['primary_variables'])
    values = complete_assignment(c, initial)
    check = check_assignment(c, values)
    result = {'status': 'PASS_FULL_N131_EIGHT_SLOT_ASSIGNMENT',
              'target': fixture['projected_target'], 'source_masks': fixture['masks'],
              'formula': profile(c, m, elapsed), 'assignment_check': check,
              'source_sha256': {'protocol.json': sha(HERE/'protocol.json')}}
    save(HERE/'control_result.json', result)
    print(json.dumps({'status': result['status'], 'formula': result['formula']}))


def query():
    p = checked_protocol()
    control_record = json.loads((HERE/'control_result.json').read_text())
    assert control_record['status'] == 'PASS_FULL_N131_EIGHT_SLOT_ASSIGNMENT'
    begun = time.monotonic()
    c, m, elapsed = build(p['raw_target_preimage_z'])
    if elapsed > CONSTRUCTION_CAP or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > RSS_CAP:
        result = {'status': 'RESOURCE_GATE_EXCEEDED', 'solver_started': False,
                  'target': p['public_target'], 'formula': profile(c, m, elapsed)}
        save(HERE/'query_result.json', result)
        print(json.dumps(result))
        return
    with tempfile.NamedTemporaryFile(prefix='n131_w18_cubic_', suffix='.xcnf',
                                     dir='/private/tmp', delete=False) as stream:
        formula = Path(stream.name)
    try:
        c.write(formula)
        formula_bytes, formula_hash = formula.stat().st_size, sha(formula)
        formula_profile = profile(c, m, elapsed)
        del c
        solver_start = time.monotonic()
        with tempfile.NamedTemporaryFile(prefix='n131_w18_stdout_', dir='/private/tmp') as out, \
             tempfile.NamedTemporaryFile(prefix='n131_w18_stderr_', dir='/private/tmp') as err:
            process = subprocess.Popen([str(SOLVER), *p['solver_flags'], str(formula)],
                                       stdout=out, stderr=err)
            child, parent = psutil.Process(process.pid), psutil.Process()
            timed_out, rss_exceeded, peak_rss = False, False, 0
            while process.poll() is None:
                try:
                    combined = child.memory_info().rss + parent.memory_info().rss
                except psutil.NoSuchProcess:
                    combined = parent.memory_info().rss
                peak_rss = max(peak_rss, combined)
                if combined > RSS_CAP:
                    rss_exceeded = True
                    process.kill()
                    break
                if time.monotonic() - solver_start > 615:
                    timed_out = True
                    process.kill()
                    break
                time.sleep(0.2)
            returncode = process.wait()
            out.flush(); err.flush()
            stdout, stderr = Path(out.name).read_bytes(), Path(err.name).read_bytes()
        solver_seconds = time.monotonic() - solver_start
        status = ('RESOURCE_GATE_EXCEEDED' if rss_exceeded else
                  'SAT_PENDING_GROUP_REPLAY' if b's SATISFIABLE' in stdout else
                  'BOUNDED_UNKNOWN' if timed_out or b's INDETERMINATE' in stdout else
                  'UNSAT' if b's UNSATISFIABLE' in stdout else 'BOUNDED_UNKNOWN')
        if status == 'SAT_PENDING_GROUP_REPLAY':
            positive, negative = set(), set()
            for row in stdout.splitlines():
                if not row.startswith(b'v '):
                    continue
                for token in row.split()[1:]:
                    lit = int(token)
                    (positive if lit > 0 else negative).add(abs(lit))
            primary = set(m['primary_variables'])
            if positive & negative or len(primary & (positive | negative)) != len(primary):
                status = 'INCOMPLETE_SAT_MODEL'
            else:
                def decode(wires):
                    return sum(int(wire in positive) << bit for bit, wire in enumerate(wires))
                save(HERE/'model_decoded.json',
                     {'target': p['public_target'],
                      'masks': [decode(row) for row in m['masks']],
                      'pair_reciprocals': [decode(row) for row in m['pair_z']],
                      'middle_reciprocals': [decode(row) for row in m['middle_z']],
                      'branch_bits': [int(wire in positive) for wire in m['branch']],
                      'raw_preimage_index': decode(m['target_flags']),
                      'formula_sha256': formula_hash})
        with gzip.open(HERE/'solver.stdout.gz', 'wb', compresslevel=6) as stream:
            stream.write(stdout)
        with gzip.open(HERE/'solver.stderr.gz', 'wb', compresslevel=6) as stream:
            stream.write(stderr)
        phases = {'construction': elapsed,
                  'write_and_hash': solver_start-begun-elapsed,
                  'solver': solver_seconds, 'total': time.monotonic()-begun}
        result = {'status': status, 'candidate_id': None,
                  'target': p['public_target'], 'public_workload_id': p['public_workload_id'],
                  'formula': {**formula_profile, 'bytes': formula_bytes,
                              'sha256': formula_hash},
                  'phase_seconds': phases, 'solver_started': True,
                  'solver_returncode': returncode, 'solver_timed_out': timed_out,
                  'solver_rss_exceeded': rss_exceeded,
                  'peak_combined_rss_bytes': peak_rss,
                  'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
                  'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
                  'stdout_gzip_sha256': sha(HERE/'solver.stdout.gz'),
                  'stderr_gzip_sha256': sha(HERE/'solver.stderr.gz'),
                  'source_sha256': {'protocol.json': sha(HERE/'protocol.json')}}
        save(HERE/'query_result.json', result)
        print(json.dumps({'status': status, 'phases': phases,
                          'formula_bytes': formula_bytes, 'peak_rss': peak_rss}))
    finally:
        formula.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('freeze', 'control', 'query'))
    mode = parser.parse_args().mode
    {'freeze': freeze, 'control': control, 'query': query}[mode]()
