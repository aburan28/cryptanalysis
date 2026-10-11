"""Frozen one-target CryptoMiniSat run for the one-hot W18 source circuit."""

import argparse
import gzip
import hashlib
import json
import resource
import subprocess
import tempfile
import time
from pathlib import Path

import psutil
import measure
from onehot import emit, rows_from_codes

HERE = Path(__file__).resolve().parent
SOLVER = Path('/opt/homebrew/bin/cryptominisat5')
FLAGS = ['--threads=1', '--xor=0', '--printsol=1', '--random=20261011', '--maxtime=600']
RSS_CAP = 4 * 1024 ** 3
PARENT_CAP = 615


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True)+'\n')


def paths():
    return {'solve.py': HERE/'solve.py', 'measure.py': HERE/'measure.py',
            'onehot.py': HERE/'onehot.py', 'protocol.json': HERE/'protocol.json',
            'result.json': HERE/'result.json', 'audit.json': HERE/'audit.json',
            'trace_circuit.py': measure.BASE/'circuit.py',
            'source_table': measure.SOURCE, 'cryptominisat5': SOLVER}


def freeze():
    assertion = json.loads((HERE/'audit.json').read_text())
    assert assertion['status'] == 'PASS_EXHAUSTIVE_TABLE_AND_FULL_CONSTRUCTED_ASSIGNMENT'
    profile = json.loads((HERE/'result.json').read_text())['formula']
    protocol = {'status': 'FROZEN_BEFORE_PUBLIC_SOLVER', 'curve_id': 'EC1N131Ckb1heb5f1998f20b',
                'candidate_id': None, 'workload_id': 'cc09e7eb202a',
                'public_target': json.loads((measure.BASE/'protocol.json').read_text())['public_target'],
                'expected_formula_sha256': profile['sha256'],
                'solver_flags': FLAGS, 'workers': 1,
                'solver_cap_seconds': 600, 'parent_cap_seconds': PARENT_CAP,
                'combined_rss_cap_bytes': RSS_CAP,
                'source_sha256': {key: sha(value) for key, value in paths().items()}}
    save(HERE/'solver_protocol.json', protocol)
    print(json.dumps({'status': protocol['status'], 'expected_formula_sha256': profile['sha256']}))


def run():
    protocol = json.loads((HERE/'solver_protocol.json').read_text())
    assert protocol['source_sha256'] == {key: sha(value) for key, value in paths().items()}
    columns = measure.load_columns()
    rows = rows_from_codes(columns)
    target = json.loads((measure.BASE/'protocol.json').read_text())['raw_target_preimage_z']
    original_bdd, original_emit = measure.base.build_bdd, measure.base.emit_bdd
    measure.base.build_bdd = lambda codes: (0, {})
    measure.base.emit_bdd = lambda c, root, nodes, mask: emit(c, mask, rows)
    start = time.monotonic()
    try:
        circuit = measure.KaratsubaCircuit(131, [0, 1, 2, 13])
        meta = measure.base.build(circuit, measure.base.Field(), columns, target)
    finally:
        measure.base.build_bdd, measure.base.emit_bdd = original_bdd, original_emit
    construction = time.monotonic() - start
    assert construction < 120
    assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss < RSS_CAP
    with tempfile.NamedTemporaryFile(prefix='w18_onehot_', suffix='.xcnf',
                                     dir='/private/tmp', delete=False) as stream:
        formula = Path(stream.name)
    try:
        circuit.write(formula)
        formula_hash = sha(formula)
        assert formula_hash == protocol['expected_formula_sha256']
        formula_bytes = formula.stat().st_size
        del circuit
        solver_start = time.monotonic()
        peak_rss = 0
        killed_for_wall = killed_for_rss = False
        with tempfile.NamedTemporaryFile(prefix='w18_onehot_stdout_', dir='/private/tmp') as out, \
             tempfile.NamedTemporaryFile(prefix='w18_onehot_stderr_', dir='/private/tmp') as err:
            proc = subprocess.Popen([str(SOLVER), *FLAGS, str(formula)], stdout=out, stderr=err)
            child, parent = psutil.Process(proc.pid), psutil.Process()
            while proc.poll() is None:
                try:
                    rss = child.memory_info().rss + parent.memory_info().rss
                except psutil.NoSuchProcess:
                    rss = parent.memory_info().rss
                peak_rss = max(peak_rss, rss)
                if peak_rss > RSS_CAP:
                    killed_for_rss = True
                    proc.kill()
                    break
                if time.monotonic() - solver_start > PARENT_CAP:
                    killed_for_wall = True
                    proc.kill()
                    break
                time.sleep(0.2)
            returncode = proc.wait()
            out.flush(); err.flush()
            stdout, stderr = Path(out.name).read_bytes(), Path(err.name).read_bytes()
        solver_seconds = time.monotonic() - solver_start
        with gzip.open(HERE/'solver.stdout.gz', 'wb', compresslevel=6) as stream:
            stream.write(stdout)
        with gzip.open(HERE/'solver.stderr.gz', 'wb', compresslevel=6) as stream:
            stream.write(stderr)
        status = ('RESOURCE_GATE_EXCEEDED' if killed_for_rss else
                  'SAT_PENDING_GROUP_REPLAY' if b's SATISFIABLE' in stdout else
                  'UNSAT' if b's UNSATISFIABLE' in stdout else
                  'BOUNDED_UNKNOWN')
        positive, negative = set(), set()
        if status == 'SAT_PENDING_GROUP_REPLAY':
            for line in stdout.splitlines():
                if line.startswith(b'v '):
                    for token in line.split()[1:]:
                        literal = int(token)
                        (positive if literal > 0 else negative).add(abs(literal))
            primaries = set(meta['primary_variables'])
            if positive & negative or not primaries <= positive | negative:
                status = 'INCOMPLETE_SAT_MODEL'
            else:
                decode = lambda wires: sum((wire in positive) << i for i, wire in enumerate(wires))
                save(HERE/'model_decoded.json',
                     {'public_target': protocol['public_target'],
                      'masks': [decode(x) for x in meta['masks']],
                      'pair_z': [decode(x) for x in meta['pair_z']],
                      'middle_z': [decode(x) for x in meta['middle_z']],
                      'branch': [int(x in positive) for x in meta['branch']],
                      'target_flag': decode(meta['target_flags']),
                      'formula_sha256': formula_hash})
        phase = {'construction': construction,
                 'write_and_hash': solver_start-start-construction,
                 'solver': solver_seconds}
        phase['post_solver'] = time.monotonic()-start-sum(phase.values())
        phase['total'] = sum(phase.values())
        result = {'status': status, 'curve_id': protocol['curve_id'],
                  'candidate_id': None, 'workload_id': protocol['workload_id'],
                  'public_target': protocol['public_target'],
                  'formula_sha256': formula_hash, 'formula_bytes': formula_bytes,
                  'solver_flags': FLAGS, 'solver_returncode': returncode,
                  'solver_wall_killed': killed_for_wall, 'solver_rss_killed': killed_for_rss,
                  'peak_combined_rss_bytes': peak_rss,
                  'phase_seconds_exploratory': phase,
                  'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
                  'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
                  'stdout_gzip_sha256': sha(HERE/'solver.stdout.gz'),
                  'stderr_gzip_sha256': sha(HERE/'solver.stderr.gz'),
                  'source_sha256': {'solver_protocol.json': sha(HERE/'solver_protocol.json')}}
        save(HERE/'solver_result.json', result)
        print(json.dumps(result))
    finally:
        formula.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('freeze', 'run'))
    {'freeze': freeze, 'run': run}[parser.parse_args().mode]()
