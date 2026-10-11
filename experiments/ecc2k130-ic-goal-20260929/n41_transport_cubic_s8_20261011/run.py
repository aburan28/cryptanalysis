"""Frozen N41 transported-source control and unpinned public query."""

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
sys.path.insert(0, str(ROOT/'experiments/koblitz-polynomial-w-pair-20260925'))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402

SOLVER = Path('/opt/homebrew/bin/cryptominisat5')
RSS_CAP = 4*1024**3
CONSTRUCTION_CAP = 120
SOLVER_CAP = 600
PARENT_CAP = 615


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, record):
    Path(path).write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')


def fixture():
    data = json.loads((HERE/'fixture.json').read_text())
    assert data['status'] == 'PASS_TRANSPORTED_N41_PUBLIC_EIGHT_SLOT_WITNESS'
    assert len(data['mask_columns']) == 32
    assert len(data['raw_target_reciprocals']) == 4
    return data


def source_files():
    return {'run.py': HERE/'run.py', 'circuit.py': HERE/'circuit.py',
            'prepare_sage.py': HERE/'prepare_sage.py',
            'fixture.json': HERE/'fixture.json',
            'sage_runtime_info.json': HERE/'sage_runtime_info.json',
            'native_receipt.json': HERE.parent/'n131_w18_four_pairs/native_join/receipt.json',
            'screen.json': HERE.parent/'n131_w18_four_pairs/screen.json',
            'n131_circuit.py': circuit.N131,
            'n41_cubic_circuit.py': circuit.shared.N41/'circuit.py',
            'basis_circuit.py': circuit.shared.SPARSE/'circuit.py',
            'basis_sparse.py': circuit.shared.SPARSE/'sparse.py',
            'n41_horner_circuit.py': circuit.shared.ROOT/'n41_single_branch_horner_20261011/circuit.py',
            'karatsuba_circuit.py': ROOT/'experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py',
            'circuit_sat.py': ROOT/'experiments/koblitz-s5-invariant-20260924/circuit_sat.py',
            'cryptominisat5': SOLVER}


def freeze():
    f = fixture()
    assert SOLVER.is_file()
    record = {'status': 'FROZEN_BEFORE_N41_CONTROL_AND_PUBLIC_QUERY',
              'candidate_id': None, 'curve_id': f['curve_id'],
              'field': 'GF(2)[t]/(t^41+t^3+1)',
              'subgroup_order': 549756390943,
              'public_target_original': f['public_target_original'],
              'public_target_transported': f['public_target_transported'],
              'target_transport': '1+Frobenius',
              'raw_target_preimage_z': f['raw_target_reciprocals'],
              'control_masks': f['known_masks'],
              'control_raw_preimage_index': f['known_raw_preimage_index'],
              'source_dimension': 6, 'rotations': circuit.ROTATIONS,
              'source_rational_masks_per_window': 32,
              'factor_base_B': 128, 'folded_columns_K': 26,
              'workers': 1, 'construction_cap_seconds': CONSTRUCTION_CAP,
              'solver_cap_seconds': SOLVER_CAP,
              'parent_solver_cap_seconds': PARENT_CAP,
              'rss_cap_bytes': RSS_CAP,
              'solver_flags': ['--threads=1', '--xor=0', '--printsol=1',
                               '--random=20261011', '--maxtime=600'],
              'source_sha256': {name: sha(path) for name, path in source_files().items()}}
    save(HERE/'protocol.json', record)
    print(json.dumps({'status': record['status'], 'target': record['public_target_original']}))


def protocol():
    data = json.loads((HERE/'protocol.json').read_text())
    assert data['status'] == 'FROZEN_BEFORE_N41_CONTROL_AND_PUBLIC_QUERY'
    assert data['source_sha256'] == {name: sha(path) for name, path in source_files().items()}
    return data


def build(target_zs):
    f = fixture()
    c = KaratsubaCircuit(41, [0, 3])
    began = time.monotonic()
    m = circuit.build(c, circuit.Field(),
                      {int(k): int(v) for k, v in f['mask_columns'].items()}, target_zs)
    return c, m, time.monotonic()-began


def profile(c, m, elapsed):
    return {'variables': c.next_var-1, 'and_gates': c.and_count,
            'clauses': len(c.clauses), 'native_xor_rows': len(c.xors),
            'construction_seconds_exploratory': elapsed,
            'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            **{key: m[key] for key in ('bdd_nodes', 'source_and_gates',
                                       'source_product_and_gates', 'pair_link_and_gates',
                                       'joint_link_and_gates',
                                       'nontrivial_column_collision_pairs',
                                       'target_selector_cross_term')}}


def complete_assignment(c, initial):
    definitions = {int(out): ('and', int(a), int(b))
                   for (a, b), out in c.and_cache.items()}
    for line in c.xors:
        literals = [int(x) for x in line.split()[1:-1]]
        definitions[abs(literals[0])] = ('xor', literals)
    values = [None]*c.next_var
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
    p, f = protocol(), fixture()
    c, m, elapsed = build([f['raw_target_reciprocals'][f['known_raw_preimage_index']]])
    initial = {}

    def bind(wires, number):
        initial.update({wire: number >> bit & 1 for bit, wire in enumerate(wires)})

    for wires, number in zip(m['masks'], f['known_masks']):
        bind(wires, number)
    for wires, number in zip(m['pair_z'], f['pair_reciprocals']):
        bind(wires, number)
    for wires, number in zip(m['middle_z'], f['middle_reciprocals']):
        bind(wires, number)
    for wire, bit in zip(m['branch'], f['branch_bits']):
        initial[wire] = bit
    assert len(initial) == len(m['primary_variables'])
    check = check_assignment(c, complete_assignment(c, initial))
    result = {'status': 'PASS_FULL_N41_TRANSPORTED_EIGHT_SLOT_ASSIGNMENT',
              'target_original': f['public_target_original'],
              'target_transported': f['public_target_transported'],
              'source_masks': f['known_masks'], 'formula': profile(c, m, elapsed),
              'assignment_check': check,
              'protocol_sha256': sha(HERE/'protocol.json')}
    save(HERE/'control_result.json', result)
    print(json.dumps({'status': result['status'], 'formula': result['formula']}))


def query():
    p, f = protocol(), fixture()
    assert json.loads((HERE/'control_result.json').read_text())['status'] == \
        'PASS_FULL_N41_TRANSPORTED_EIGHT_SLOT_ASSIGNMENT'
    begun = time.monotonic()
    c, m, elapsed = build(p['raw_target_preimage_z'])
    if elapsed > CONSTRUCTION_CAP or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > RSS_CAP:
        result = {'status': 'RESOURCE_GATE_EXCEEDED', 'solver_started': False,
                  'target_original': f['public_target_original'],
                  'target_transported': f['public_target_transported'],
                  'formula': profile(c, m, elapsed)}
        save(HERE/'query_result.json', result)
        print(json.dumps(result))
        return
    with tempfile.NamedTemporaryFile(prefix='n41_transport_cubic_', suffix='.xcnf',
                                     dir='/private/tmp', delete=False) as stream:
        formula = Path(stream.name)
    try:
        c.write(formula)
        formula_bytes, formula_hash = formula.stat().st_size, sha(formula)
        formula_profile = profile(c, m, elapsed)
        del c
        solver_start = time.monotonic()
        with tempfile.NamedTemporaryFile(prefix='n41_cubic_stdout_', dir='/private/tmp') as out, \
             tempfile.NamedTemporaryFile(prefix='n41_cubic_stderr_', dir='/private/tmp') as err:
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
                if time.monotonic()-solver_start > PARENT_CAP:
                    timed_out = True
                    process.kill()
                    break
                time.sleep(0.2)
            returncode = process.wait()
            out.flush(); err.flush()
            stdout, stderr = Path(out.name).read_bytes(), Path(err.name).read_bytes()
        solver_seconds = time.monotonic()-solver_start
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
                    if lit:
                        (positive if lit > 0 else negative).add(abs(lit))
            primary = set(m['primary_variables'])
            if positive & negative or len(primary & (positive | negative)) != len(primary):
                status = 'INCOMPLETE_SAT_MODEL'
            else:
                def decode(wires):
                    return sum(int(wire in positive) << bit for bit, wire in enumerate(wires))
                save(HERE/'model_decoded.json',
                     {'target_original': f['public_target_original'],
                      'target_transported': f['public_target_transported'],
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
                  'target_original': f['public_target_original'],
                  'target_transported': f['public_target_transported'],
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
                  'protocol_sha256': sha(HERE/'protocol.json')}
        save(HERE/'query_result.json', result)
        print(json.dumps({'status': status, 'phases': phases,
                          'formula_bytes': formula_bytes, 'peak_rss': peak_rss}))
    finally:
        formula.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('freeze', 'control', 'query'))
    {'freeze': freeze, 'control': control, 'query': query}[parser.parse_args().mode]()
