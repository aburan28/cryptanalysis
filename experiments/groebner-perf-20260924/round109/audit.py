"""Native-free proof, Boolean-basis, curve and continuation-accounting audit."""
import argparse
from dataclasses import replace
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from compose import compose

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REFERENCE = HERE.parent/'round108'
_path = sys.path[:]
try:
    sys.path[:0] = [str(REFERENCE), str(HERE.parent.parent/'pdp-scaling')]
    from matrix_model import model
    from boolean_basis import certify_boolean_basis
    from descend import make_instance, verify_solution
finally:
    sys.path[:] = _path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def integer(value, upper):
    assert type(value) is int and 0 <= value < upper
    return value


@lru_cache(maxsize=32)
def matrix(encoded):
    c = json.loads(encoded)
    return model(c['nvars'], c['equations'], min(c['nvars'], 6 if c['boundary'] == 'pdp' else 2),
                 2, minimal=True, parity=True, block=True, max_work=20000000,
                 max_nodes=2000000, max_rows=4096)


@lru_cache(maxsize=32)
def mathematics(encoded):
    n, equations, basis, proof = json.loads(encoded)
    assert 1 <= n <= 12
    assert (proof['version'], proof['nvars'], proof['order']) == (1, n, 'grevlex-x0-first')
    nodes, outputs = proof['nodes'], proof['outputs']
    assert len(nodes) <= 2000000 and len(outputs) == len(basis)

    def polynomial(terms):
        value = 0
        for term in terms:
            value ^= 1 << integer(term, 1 << n)
        return value

    # Python integers encode polynomial coefficients. This verifier shares no
    # native arithmetic and keeps only values with remaining graph/output uses.
    uses = [0]*len(nodes)
    for i, node in enumerate(nodes):
        assert isinstance(node, list) and node
        if node[0] == 'input':
            assert len(node) == 2
            integer(node[1], len(equations))
        else:
            assert node[0] in ('mul', 'xor') and len(node) == 3
            uses[integer(node[1], i)] += 1
            if node[0] == 'xor':
                uses[integer(node[2], i)] += 1
            else:
                integer(node[2], 1 << n)
    for output in outputs:
        uses[integer(output, len(nodes))] += 1
    originals = [polynomial(row) for row in equations]
    values = {}
    live = peak = total = released = freed = 0

    def release(i):
        nonlocal live, released, freed
        size = values.pop(i).bit_count()
        live -= size
        released += size
        freed += 1

    def consume(i):
        uses[i] -= 1
        if not uses[i]:
            release(i)

    for i, node in enumerate(nodes):
        if node[0] == 'input':
            value = originals[node[1]]
        elif node[0] == 'xor':
            value = values[node[1]] ^ values[node[2]]
        else:
            bits, value = values[node[1]], 0
            while bits:
                bit = bits & -bits
                bits ^= bit
                value ^= 1 << ((bit.bit_length()-1) | node[2])
        values[i] = value
        size = value.bit_count()
        live += size
        total += size
        peak = max(peak, live)
        assert peak <= 2000000
        if node[0] != 'input':
            consume(node[1])
        if node[0] == 'xor':
            consume(node[2])
        if not uses[i]:
            release(i)
    assert [values[i] for i in outputs] == [polynomial(row) for row in basis]
    for output in outputs:
        consume(output)
    assert not values and live == 0
    certificate = certify_boolean_basis(n, equations, basis, monomial_cache=True)
    assert certificate['verified'], certificate
    return dict(planning_work=len(nodes)+len(outputs), metadata_bytes=4*len(nodes),
                live_terms=live, peak_terms=peak, released_terms=released, released_nodes=freed), total


@lru_cache(maxsize=32)
def curve(encoded, assignment):
    c = json.loads(encoded)
    original = make_instance(c['n'], c['m'], c['ell'], seed=c['seed'], build_anf=False)
    assert (original.mod, original.b, original.xR) == (c['mod'], c['b'], c['target_x'])
    anf = {}
    for i, row in enumerate(c['equations']):
        for mask in row:
            anf[mask] = anf.get(mask, 0) ^ (1 << i)
    original = replace(original, anf=anf)
    assert original.evaluate(assignment) == 0 and verify_solution(original, assignment)


def audit(report, folder):
    folder = Path(folder)
    assert report['status'] == 'RECORDED_PENDING_AUDIT' and report['unit_exit_code'] == 0
    assert report['timing_eligible'] is False and report['qualified_speedup'] is None
    commit = report['source_commit']
    assert len(commit) == 40 and set(commit) <= set('0123456789abcdef')
    prefix = str(HERE.relative_to(ROOT))+'/'
    files = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit, '--', prefix], cwd=ROOT, text=True).splitlines()
    expected_scripts = {Path(p).name for p in files if p.endswith('.py') and Path(p).parent == Path(prefix)}
    assert set(report['scripts']) == expected_scripts
    for name, digest in report['scripts'].items():
        data = subprocess.check_output(['git', 'show', commit+':'+prefix+name], cwd=ROOT)
        assert sha(data) == digest
    build = report['reference_build']
    assert build['schema'] == 'block-witness-build/1'
    assert len(build['sources']) == 104 and len(build['binaries']) == len(build['commands']) == 26
    assert len(build['generated']) == 12 and len(build['resources']) == 2
    for name, digest in build['sources'].items():
        path = (ROOT/'experiments'/name).resolve()
        assert path.is_relative_to(ROOT) and sha(path.read_bytes()) == digest
    plan = json.loads((REFERENCE/'panel.json').read_text())
    assert report['reference_plan'] == plan
    fixture = HERE.parent/'round13/results/confirmation.json.gz'
    assert sha(fixture.read_bytes()) == plan['fixture_sha256']
    cases = {c['name']: c for c in json.loads(gzip.decompress(fixture.read_bytes()))['inputs']}
    entries = iter(report['rows'])
    seen = {}
    counts = dict(rows=0, algebra_verified=0, curve_replays=0, inconclusive=0,
                  seeded_successes=0, process_failures=0, composed_graphs=0)
    for sanitized in (False, True):
        for name in plan['cases']:
            row = next(entries)
            counts['rows'] += 1
            assert row['name'] == name and row['sanitized'] is sanitized
            if row['execution'] != 'completed':
                assert row['execution'] in ('timeout', 'process-failure')
                counts['process_failures'] += 1
                continue
            assert row['exit_code'] == 0
            path = folder/row['result']
            assert Path(row['result']).name == row['result'] and not path.is_symlink()
            data = path.read_bytes()
            assert sha(data) == row['sha256']
            r = json.loads(data)
            c = cases[name]
            assert r['name'] == name and r['fixture'] == c and r['sanitized'] is sanitized
            assert r['timing_eligible'] is False and r['qualified_speedup'] is None and r['native_integration'] is False
            encoded = json.dumps(c, sort_keys=True)
            expected = matrix(encoded)
            first = r['attempts'][0]
            assert first['kind'] == 'macaulay'
            assert first['stats'] == expected['stats'] and first['parity'] == expected['parity'] and first['block'] == expected['block']
            if expected['reason']:
                assert first['reason'] == expected['reason']
            assert r['work'] == sum(a['stats']['work'] for a in r['attempts'])+r['bridge_work']+r.get('composition', {}).get('stats', {}).get('work', 0)
            assert r['check_work'] == sum(a.get('certificate', {}).get('stats', {}).get('work', 0) for a in r['attempts'])
            integer(r['work'], 80000001)
            integer(r['check_work'], 200000001)
            if len(r['attempts']) == 2 and r['attempts'][1]['kind'] == 'seeded-f4':
                second = r['attempts'][1]
                assert expected['stats']['status'] == 0 and not first['certificate']['verified']
                assert second['reserved_seed_nodes'] == len(expected['proof']['nodes'])+len(c['equations'])
                if second['stats']['status'] == 0:
                    continuation = r['continuation']
                    basis = continuation['basis']
                    nodes = len(continuation['proof']['nodes'])
                    assert nodes == second['stats']['nodes']
                    assert nodes+second['reserved_seed_nodes'] <= 2000000
                    bridge = len(expected['proof']['nodes'])+len(expected['basis'])+sum(map(len, expected['basis']))
                    bridge += len(expected['basis'])+len(c['equations'])+sum(map(len, expected['basis']))+sum(map(len, c['equations']))
                    bridge += nodes+len(basis)+sum(map(len, basis))
                    result = compose(expected['proof'], continuation['proof'], len(c['equations']),
                        max_work=80000000-first['stats']['work']-second['stats']['work']-bridge, max_nodes=2000000)
                    assert r['composition'] == {k: v for k, v in result.items() if k != 'proof'}
                    if result['proof'] is not None:
                        bridge += sum(map(len, basis))+len(basis)+len(result['proof']['nodes'])
                        assert r['proof'] == result['proof'] and r['basis'] == basis
                    assert r['bridge_work'] == bridge
                    counts['composed_graphs'] += 1
            elif len(r['attempts']) == 2:
                assert expected['stats']['status'] != 0 and r['attempts'][1]['kind'] == 'fresh-f4'
                assert r['bridge_work'] == 0
            else:
                assert len(r['attempts']) == 1 and first['certificate']['verified'] and r['bridge_work'] == 0
                assert r['basis'] == expected['basis'] and r['proof'] == expected['proof']
            if r['algebra_verified']:
                certificate = r['attempts'][-1]['certificate']
                assert certificate == r['certificate'] and certificate['verified'] is True
                assert certificate['ideal_equality'] is True and certificate['reduced_groebner_basis'] is True
                life, total = mathematics(json.dumps([c['nvars'], c['equations'], r['basis'], r['proof']]))
                assert life == certificate['liveness'] and total == certificate['stats']['retained_terms']
                assert certificate['stats']['proof_nodes'] == len(r['proof']['nodes'])
                counts['algebra_verified'] += 1
                counts['seeded_successes'] += int(r['attempts'][-1]['kind'] == 'seeded-f4')
                assert r['verified'] is True
                if c['boundary'] == 'pdp':
                    assert r['status'] == 'solved' and r['reference_equations_and_curve_replay'] is True
                    curve(encoded, integer(r['assignment'], 1 << c['nvars']))
                    counts['curve_replays'] += 1
                else:
                    assert r['status'] == 'gb'
            else:
                assert r['verified'] is False and r['status'] == 'inconclusive'
                assert not any(k in r for k in ('basis', 'proof', 'assignment'))
                counts['inconclusive'] += 1
            deterministic = {k: v for k, v in r.items() if k != 'sanitized'}
            if name in seen:
                assert seen[name] == deterministic
            else:
                seen[name] = deterministic
    assert next(entries, None) is None
    return dict(status='PASS', native_binaries_loaded=False, timing_eligible=False,
                qualified_speedup=None, unique_records=len(seen), **counts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.report.read_text()), args.report.parent)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)
