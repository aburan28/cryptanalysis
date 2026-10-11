"""Frozen N41 implicit relaxed-pair SAT panel against exact join controls."""

import argparse
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

HERE = Path(__file__).resolve().parent
ROOT = Path('/Volumes/SSD990/cryptanalysis')
PANEL = circuit.ROOT/'n41_direct_relaxed_pair_join_20261011/receipt.json'
SOLVER = Path('/opt/homebrew/bin/cryptominisat5')
sys.path.insert(0, str(ROOT/'experiments/koblitz-polynomial-w-pair-20260925'))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402

FLAGS = ['--threads=1', '--xor=0', '--printsol=1',
         '--random=20261011', '--maxtime=45']
RSS_CAP = 4 * 1024**3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True)+'\n')


def sources():
    return {'circuit.py': HERE/'circuit.py', 'run.py': HERE/'run.py',
            'panel': PANEL, 'old_cubic': circuit.BASE/'circuit.py',
            'sparse': circuit.SPARSE/'sparse.py',
            'horner': circuit.ROOT/'n41_single_branch_horner_20261011/circuit.py',
            'karatsuba': ROOT/'experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py',
            'solver': SOLVER}


def panel():
    record = json.loads(PANEL.read_text())
    assert record['status'] == 'COMPLETE_N41_RELAXED_TWO_PAIR_PANEL'
    assert record['queries'][0]['status'] == 'RELAXED_SUM_HIT'
    assert all(x['status'] == 'COMPLETE_RELAXED_NO_SUM' for x in record['queries'][1:])
    return record


def freeze():
    entries = panel()['queries']
    assert SOLVER.is_file()
    protocol = {'status': 'FROZEN_BEFORE_CONTROL_AND_PUBLIC_QUERIES',
                'candidate_id': None, 'field': 'GF(2)[t]/(t^41+t^3+1)',
                'curve': 'y^2+xy=x^3+1', 'rotations': list(circuit.ROTATIONS),
                'source_seed_sum_masks': 63, 'source_product_masks': 2048,
                'target_labels': ['positive', 'control_0'],
                'targets': {row['label']: row['target'] for row in entries
                            if row['label'] in ('positive', 'control_0')},
                'solver_flags': FLAGS, 'workers': 1,
                'solver_cap_seconds': 45, 'parent_cap_seconds': 50,
                'combined_rss_cap_bytes': RSS_CAP,
                'source_sha256': {name: sha(path) for name, path in sources().items()}}
    save(HERE/'protocol.json', protocol)
    print(json.dumps({'status': protocol['status'], 'labels': protocol['target_labels']}))


def checked_protocol():
    protocol = json.loads((HERE/'protocol.json').read_text())
    assert protocol['source_sha256'] == {name: sha(path) for name, path in sources().items()}
    return protocol


def build(target):
    field = circuit.old.Field()
    c = KaratsubaCircuit(41, [0, 3])
    start = time.monotonic()
    meta = circuit.build(c, field, target)
    return c, meta, field, time.monotonic()-start


def complete_assignment(c, initial):
    definitions = {int(out): ('and', int(a), int(b))
                   for (a, b), out in c.and_cache.items()}
    for line in c.xors:
        literals = [int(v) for v in line.split()[1:-1]]
        definitions[abs(literals[0])] = ('xor', literals)
    values = [None]*c.next_var
    for wire, bit in initial.items():
        values[wire] = bit
    def value(wire):
        return 1 if wire == -1 else 0 if wire == 0 else values[wire]
    for wire in range(1, c.next_var):
        if values[wire] is not None:
            continue
        definition = definitions[wire]
        if definition[0] == 'and':
            values[wire] = value(definition[1]) & value(definition[2])
        else:
            literals = definition[1]
            bit = int(literals[0] > 0)
            for lit in literals[1:]:
                bit ^= values[abs(lit)] ^ int(lit < 0)
            values[wire] = bit
    return values


def check_assignment(c, values):
    for row in c.clauses:
        assert any(values[abs(lit)] == int(lit > 0)
                   for lit in map(int, row.split()[:-1]))
    for row in c.xors:
        assert sum(values[abs(lit)] ^ int(lit < 0)
                   for lit in map(int, row.split()[1:-1])) & 1
    return {'clauses': len(c.clauses), 'xor_rows': len(c.xors)}


def profile(c, meta, elapsed):
    return {'variables': c.next_var-1, 'and_gates': c.and_count,
            'cnf_clauses': len(c.clauses), 'xor_rows': len(c.xors),
            'construction_seconds_exploratory': elapsed,
            'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'primary_variables': len(meta['primary'])}


def control():
    protocol = checked_protocol()
    row = panel()['queries'][0]
    c, meta, field, elapsed = build(row['target'])
    assert row['label'] == 'positive'
    witnesses = [row['left_witness'], row['right_witness']]
    primary = {}
    def bind(wires, integer):
        primary.update({wire: (integer >> bit) & 1 for bit, wire in enumerate(wires)})
    zs = []
    for i, witness in enumerate(witnesses):
        z = field.frob(witness['reciprocal_z'], circuit.ROTATIONS[i])
        x = field.inv(z)
        point = row['left_point'] if i == 0 else row['right_point']
        assert x == point[0]
        zs.append(z)
        bind(meta['seed'][i], witness['seed_sum'])
        bind(meta['product'][i], witness['product_mask'])
        bind(meta['z'][i], z)
        bind(meta['x'][i], x)
        primary[meta['branch'][i]] = witness['branch']
    root_branch = field.mul(field.mul(zs[0], zs[1]), meta['target_z'])
    root_branch ^= circuit.old.halftrace(field, field.square(zs[0]^zs[1]^meta['target_z']))
    assert root_branch in (0, 1)
    primary[meta['branch'][2]] = root_branch
    assert len(primary) == len(meta['primary'])
    checked = check_assignment(c, complete_assignment(c, primary))
    record = {'status': 'PASS_EXACT_POSITIVE_BOOLEAN_ASSIGNMENT',
              'target': row['target'], 'rotated_pair_reciprocals': zs,
              'root_branch': root_branch, 'formula': profile(c, meta, elapsed),
              'assignment_check': checked,
              'source_sha256': {'protocol.json': sha(HERE/'protocol.json')}}
    save(HERE/'control.json', record)
    print(json.dumps(record))


def query(label):
    protocol = checked_protocol()
    assert json.loads((HERE/'control.json').read_text())['status'] == 'PASS_EXACT_POSITIVE_BOOLEAN_ASSIGNMENT'
    target = protocol['targets'][label]
    started = time.monotonic()
    c, meta, _, construct = build(target)
    with tempfile.NamedTemporaryFile(prefix='n41_relaxed_', suffix='.xcnf',
                                     dir='/private/tmp', delete=False) as stream:
        formula = Path(stream.name)
    try:
        c.write(formula)
        formula_hash, formula_bytes = sha(formula), formula.stat().st_size
        formula_profile = profile(c, meta, construct)
        del c
        solver_start = time.monotonic()
        peak, wall_killed, rss_killed = 0, False, False
        with tempfile.NamedTemporaryFile(prefix='n41_relaxed_out_', dir='/private/tmp') as out, \
             tempfile.NamedTemporaryFile(prefix='n41_relaxed_err_', dir='/private/tmp') as err:
            proc = subprocess.Popen([str(SOLVER), *FLAGS, str(formula)], stdout=out, stderr=err)
            child, parent = psutil.Process(proc.pid), psutil.Process()
            while proc.poll() is None:
                try:
                    rss = child.memory_info().rss + parent.memory_info().rss
                except psutil.NoSuchProcess:
                    rss = parent.memory_info().rss
                peak = max(peak, rss)
                if peak > RSS_CAP:
                    rss_killed = True; proc.kill(); break
                if time.monotonic()-solver_start > 50:
                    wall_killed = True; proc.kill(); break
                time.sleep(0.1)
            returncode = proc.wait()
            out.flush(); err.flush()
            stdout, stderr = Path(out.name).read_bytes(), Path(err.name).read_bytes()
        solver_seconds = time.monotonic()-solver_start
        status = ('RESOURCE_GATE_EXCEEDED' if rss_killed else
                  'SAT_PENDING_GROUP_REPLAY' if b's SATISFIABLE' in stdout else
                  'UNSAT' if b's UNSATISFIABLE' in stdout else
                  'BOUNDED_UNKNOWN' if wall_killed or b's INDETERMINATE' in stdout else
                  'PRODUCER_FAILURE')
        (HERE/f'{label}.stdout').write_bytes(stdout)
        (HERE/f'{label}.stderr').write_bytes(stderr)
        if status == 'SAT_PENDING_GROUP_REPLAY':
            positive, negative = set(), set()
            for line in stdout.splitlines():
                if line.startswith(b'v '):
                    for token in line.split()[1:]:
                        value = int(token)
                        (positive if value > 0 else negative).add(abs(value))
            if positive & negative or not set(meta['primary']) <= positive | negative:
                status = 'INCOMPLETE_SAT_MODEL'
            else:
                decode = lambda wires: sum((wire in positive) << bit
                                           for bit, wire in enumerate(wires))
                save(HERE/f'{label}.model.json',
                     {'target': target, 'seed': [decode(x) for x in meta['seed']],
                      'product': [decode(x) for x in meta['product']],
                      'z': [decode(x) for x in meta['z']],
                      'x': [decode(x) for x in meta['x']],
                      'branch': [int(x in positive) for x in meta['branch']],
                      'formula_sha256': formula_hash})
        phase = {'construction': construct,
                 'write_and_hash': solver_start-started-construct,
                 'solver': solver_seconds}
        phase['post_solver'] = time.monotonic()-started-sum(phase.values())
        phase['total'] = sum(phase.values())
        record = {'status': status, 'label': label, 'target': target,
                  'candidate_id': None, 'formula': {**formula_profile,
                  'bytes': formula_bytes, 'sha256': formula_hash},
                  'solver_flags': FLAGS, 'solver_returncode': returncode,
                  'solver_wall_killed': wall_killed, 'solver_rss_killed': rss_killed,
                  'peak_combined_rss_bytes': peak, 'phase_seconds_exploratory': phase,
                  'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
                  'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
                  'source_sha256': {'protocol.json': sha(HERE/'protocol.json')}}
        save(HERE/f'{label}.result.json', record)
        print(json.dumps(record))
    finally:
        formula.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('freeze', 'control', 'query'))
    parser.add_argument('--label', choices=('positive', 'control_0'))
    args = parser.parse_args()
    {'freeze': freeze, 'control': control,
     'query': lambda: query(args.label)}[args.mode]()
