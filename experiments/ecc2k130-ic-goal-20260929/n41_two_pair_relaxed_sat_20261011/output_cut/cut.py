"""Freeze and test one supplied pair-output coordinate in the N41 completion core."""

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

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
import run as base  # noqa: E402

FLAGS = ['--threads=1', '--xor=0', '--printsol=1',
         '--random=20261011', '--maxtime=30']
RSS_CAP = 4 * 1024**3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, sort_keys=True, indent=2)+'\n')


def sources():
    return {'cut.py': HERE/'cut.py', 'parent_protocol.json': PARENT/'protocol.json',
            'parent_run.py': PARENT/'run.py', 'parent_circuit.py': PARENT/'circuit.py',
            'parent_control.json': PARENT/'control.json',
            'panel': base.PANEL, 'solver': base.SOLVER}


def freeze():
    parent = base.checked_protocol()
    control = json.loads((PARENT/'control.json').read_text())
    assert control['status'] == 'PASS_EXACT_POSITIVE_BOOLEAN_ASSIGNMENT'
    z0 = control['rotated_pair_reciprocals'][0]
    positive = base.panel()['queries'][0]
    assert z0 == base.circuit.old.Field().inv(positive['left_point'][0])
    protocol = {'status': 'FROZEN_BEFORE_OUTPUT_CUT_CONTROL_AND_QUERIES',
                'candidate_id': None, 'first_pair_reciprocal_z': z0,
                'pinned_coordinate_bits': 41,
                'pin_source': 'known positive relaxed pair witness; validation-only',
                'targets': {label: parent['targets'][label]
                            for label in ('positive', 'control_0')},
                'solver_flags': FLAGS, 'workers': 1, 'solver_cap_seconds': 30,
                'parent_cap_seconds': 35, 'combined_rss_cap_bytes': RSS_CAP,
                'source_sha256': {name: sha(path) for name, path in sources().items()}}
    save(HERE/'protocol.json', protocol)
    print(json.dumps({'status': protocol['status'], 'first_pair_reciprocal_z': z0}))


def checked():
    protocol = json.loads((HERE/'protocol.json').read_text())
    assert protocol['source_sha256'] == {name: sha(path) for name, path in sources().items()}
    return protocol


def build(target, z0):
    c, meta, field, elapsed = base.build(target)
    for bit, wire in enumerate(meta['z'][0]):
        c.clauses.append(f'{wire if z0 >> bit & 1 else -wire} 0')
    return c, meta, field, elapsed


def control():
    protocol = checked()
    row = base.panel()['queries'][0]
    c, meta, field, elapsed = build(row['target'], protocol['first_pair_reciprocal_z'])
    primary = {}
    def bind(wires, integer):
        primary.update({wire: (integer >> bit) & 1 for bit, wire in enumerate(wires)})
    zs = []
    for i, witness in enumerate((row['left_witness'], row['right_witness'])):
        z = field.frob(witness['reciprocal_z'], base.circuit.ROTATIONS[i])
        zs.append(z)
        bind(meta['seed'][i], witness['seed_sum'])
        bind(meta['product'][i], witness['product_mask'])
        bind(meta['z'][i], z)
        bind(meta['x'][i], field.inv(z))
        primary[meta['branch'][i]] = witness['branch']
    root = field.mul(field.mul(zs[0], zs[1]), meta['target_z'])
    root ^= base.circuit.old.halftrace(field, field.square(zs[0]^zs[1]^meta['target_z']))
    assert root in (0, 1)
    primary[meta['branch'][2]] = root
    assert len(primary) == len(meta['primary'])
    verified = base.check_assignment(c, base.complete_assignment(c, primary))
    record = {'status': 'PASS_FULL_PINNED_ASSIGNMENT', 'target': row['target'],
              'first_pair_reciprocal_z': protocol['first_pair_reciprocal_z'],
              'pinned_units': 41, 'formula': base.profile(c, meta, elapsed),
              'checked': verified,
              'source_sha256': {'protocol.json': sha(HERE/'protocol.json')}}
    save(HERE/'control.json', record)
    print(json.dumps(record))


def query(label):
    protocol = checked()
    assert json.loads((HERE/'control.json').read_text())['status'] == 'PASS_FULL_PINNED_ASSIGNMENT'
    target = protocol['targets'][label]
    began = time.monotonic()
    c, meta, _, construct = build(target, protocol['first_pair_reciprocal_z'])
    with tempfile.NamedTemporaryFile(prefix='n41_output_cut_', suffix='.xcnf',
                                     dir='/private/tmp', delete=False) as stream:
        formula = Path(stream.name)
    try:
        c.write(formula)
        digest, size = sha(formula), formula.stat().st_size
        profile = base.profile(c, meta, construct)
        del c
        solver_start = time.monotonic()
        peak, wall_killed, rss_killed = 0, False, False
        with tempfile.NamedTemporaryFile(prefix='n41_output_cut_out_', dir='/private/tmp') as out, \
             tempfile.NamedTemporaryFile(prefix='n41_output_cut_err_', dir='/private/tmp') as err:
            proc = subprocess.Popen([str(base.SOLVER), *FLAGS, str(formula)],
                                    stdout=out, stderr=err)
            child, parent = psutil.Process(proc.pid), psutil.Process()
            while proc.poll() is None:
                try:
                    rss = child.memory_info().rss + parent.memory_info().rss
                except psutil.NoSuchProcess:
                    rss = parent.memory_info().rss
                peak = max(peak, rss)
                if peak > RSS_CAP:
                    rss_killed = True; proc.kill(); break
                if time.monotonic()-solver_start > 35:
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
                      'formula_sha256': digest})
        phase = {'construction': construct, 'write_and_hash': solver_start-began-construct,
                 'solver': solver_seconds}
        phase['post_solver'] = time.monotonic()-began-sum(phase.values())
        phase['total'] = sum(phase.values())
        record = {'status': status, 'label': label, 'target': target,
                  'candidate_id': None, 'first_pair_reciprocal_z': protocol['first_pair_reciprocal_z'],
                  'formula': {**profile, 'bytes': size, 'sha256': digest},
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
