"""Independent root/identity, malformed-input and bounded-output controls."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import ctypes as ct
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import random
import sys

from native import HERE, Native, Packed, Stats, U32, U64

from reference import checker as python_checker, direct_roots, truth_transform


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())


def polynomials(y, equations, terms):
    rows = [0] * equations
    for monomial, coefficient in terms:
        for e in range(equations):
            if coefficient & (1 << e):
                rows[e] ^= 1 << monomial
    return tuple(rows)


def cases(plan):
    rng = random.Random(plan['seed'])
    for y in (1, 2, 3):
        monomials = tuple(m for m in range(1 << y) if m.bit_count() <= 2)
        polynomials = [sum(((v >> i) & 1) << m for i, m in enumerate(monomials))
                       for v in range(1 << len(monomials))]
        for left, right in itertools.product(polynomials, repeat=2):
            terms = [(m, ((left >> m) & 1) | (((right >> m) & 1) << 1)) for m in monomials]
            yield f'exhaustive-{y}-{left}-{right}', y, 2, terms, 'exhaustive'
    for y in range(1, 11):
        for equations in plan['random_widths']:
            for trial in range(plan['random_systems_per_width_and_dimension']):
                terms = [(m, rng.getrandbits(equations)) for m in range(1 << y)
                         if m.bit_count() <= 2 and rng.randrange(2)]
                terms += terms[:2] * 2 + [(0, 0)]
                yield f'random-y{y}-e{equations}-{trial}', y, equations, terms, 'random-width'
    for trial in range(plan['structural_controls']):
        y, equations, solution = 10, 31, rng.randrange(1024)
        columns = {1 << i: rng.getrandbits(equations) for i in range(y)}
        for i in range(y):
            for j in range(i + 1, y):
                columns[(1 << i) | (1 << j)] = (1 << (2 * i + j)) ^ (1 << (i + 2 * j))
        constant = 0
        for monomial, coefficient in columns.items():
            if monomial & solution == monomial:
                constant ^= coefficient
        columns[0] = constant
        yield f'structured-n31-ell10-{trial}-root{solution}', y, equations, list(columns.items()), 'structured'
    reference = read(HERE / 'fixtures/frozen-controls.json')
    fixture_path = HERE / reference['original_anf_fixture']
    assert sha(fixture_path) == reference['original_anf_sha256']
    fixtures = {i['name']: i for i in read(fixture_path)}
    for row in reference['actual_residual_controls']:
        name, branch_text = row['name'].rsplit('-branch', 1)
        item, branch = fixtures[name], int(branch_text)
        x, y = 2 * item['ell'], item['ell']
        columns = {}
        for monomial, coefficient in item['reference_anf']:
            left, right = monomial & ((1 << x) - 1), monomial >> x
            if left & branch == left:
                columns[right] = columns.get(right, 0) ^ coefficient
        yield row['name'], y, item['n'], list(columns.items()), 'actual-residual'
    for y in (3, 7, 10):
        for equations in (3, 31, 32, 63, 64, 65, 127, 128):
            a, b, high = 1 << (y - 2), 1 << (y - 1), 1 << (equations - 1)
            yield f'high-y{y}-e{equations}', y, equations, [(a, 1), (b, 2), (a | b, high), (0, high)], 'high-word'


def controls(sanitizer):
    records = []
    with Native(3, 65, kind='producer', sanitizer=sanitizer) as p, Native(3, 65, kind='checker', sanitizer=sanitizer) as c:
        terms = [(2, 1), (4, 2), (6, 1 << 64), (0, 1 << 64)]
        packed = Packed(3, 65, terms)
        produced = p.produce(packed)
        assert produced['code'] == 0
        witnesses = produced['witnesses']
        checked = c.check(packed, witnesses)
        assert checked['code'] == 0 and checked['roots'] == ()
        for name, native, baseline in (('producer', p, produced), ('checker', c, checked)):
            for budget in (0, 1, 8, baseline['stats']['work'] - 1):
                result = native.produce(packed, work_budget=budget) if name == 'producer' else native.check(packed, witnesses, work_budget=budget)
                assert result['code'] == 3 and result['stats']['work'] <= budget
                records.append({'kind': name + '-work-budget', 'budget': budget, 'code': result['code']})
            exact = native.produce(packed, work_budget=baseline['stats']['work']) if name == 'producer' else native.check(packed, witnesses, work_budget=baseline['stats']['work'])
            assert exact == baseline
        assert p.produce(packed, capacity=len(witnesses) - 1)['code'] == 4
        assert c.check(packed, witnesses, assignment_budget=checked['stats']['assignments'] - 1)['code'] == 3
        empty = Packed(3, 65, [])
        assert c.check(empty, (), capacity=7)['code'] == 4
        assert c.check(empty, ())['roots'] == tuple(range(8))
        assert c.check(packed, (1 << 64,))['code'] == 2
        changed = Packed(3, 65, terms[:-1])
        expected = truth_transform(3, polynomials(3, 65, terms[:-1]))
        assert c.check(changed, witnesses)['roots'] == expected and expected
        assert c.check(packed, witnesses)['roots'] == ()
        records += [{'kind': kind, 'status': 'PASS'} for kind in
                    ('producer-capacity', 'assignment-limit', 'root-capacity', 'rank-zero', 'nonlinear-witness', 'changed-originals', 'fresh-reuse')]
        # Corrupt buffers after construction to exercise native guards too.
        bad = Packed(3, 65, terms)
        bad.coefficients[1] |= 2
        assert p.produce(bad)['code'] == c.check(bad, witnesses)['code'] == 1
        bad = Packed(3, 65, terms)
        bad.masks[0] = 8
        assert p.produce(bad)['code'] == c.check(bad, witnesses)['code'] == 1
        cubic = Packed(3, 65, [(7, 1)])
        assert p.produce(cubic)['code'] == c.check(cubic, ())['code'] == 2
        assert p.produce(Packed(3, 65, [(7, 0)]))['code'] == 0
        assert c.check(Packed(3, 65, [(7, 0)]), ())['roots'] == tuple(range(8))
        records += [{'kind': kind, 'status': 'PASS'} for kind in ('native-coefficient-high-bits', 'native-mask-extent', 'nonquadratic-input', 'zero-placeholder')]
        for y, e in ((0, 3), (11, 3), (3, 0), (3, 129)):
            assert not p.lib.partial_create(y, e) and not c.lib.partial_create(y, e)
        records.append({'kind': 'native-invalid-dimensions', 'cases': 8, 'status': 'PASS'})
        count, stats = U32(123), Stats()
        out = (U64 * 258)(*([0xA5A5A5A5A5A5A5A5] * 258))
        code = p.lib.partial_produce(p._handle, None, None, 1000001, 1 << 24,
                                    out, 128, ct.byref(count), ct.byref(stats))
        assert code == 1 and count.value == 0 and stats.work == 0
        assert all(v == 0xA5A5A5A5A5A5A5A5 for v in out)
        for context, stats_pointer in ((None, ct.byref(stats)), (p._handle, None)):
            count.value = 123
            code = p.lib.partial_produce(context, packed.masks, packed.coefficients,
                                        len(packed.masks), 1 << 24, out, 128,
                                        ct.byref(count), stats_pointer)
            assert code == 1 and count.value == 0
        roots = (U32 * 1026)(*([0xA5A5A5A5] * 1026))
        bad_witness = (U64 * 2)(0, 2)
        count.value = 123
        code = c.lib.partial_check(c._handle, packed.masks, packed.coefficients,
                                  len(packed.masks), bad_witness, 1, 1 << 24, 1024,
                                  roots, 1024, ct.byref(count), ct.byref(stats))
        assert code == 1 and count.value == 0 and all(v == 0xA5A5A5A5 for v in roots)
        for context, witnesses_pointer, rows in ((None, None, 0), (c._handle, None, 129), (c._handle, None, 1)):
            count.value = 123
            code = c.lib.partial_check(context, packed.masks, packed.coefficients,
                                      len(packed.masks), witnesses_pointer, rows, 1 << 24, 1024,
                                      roots, 1024, ct.byref(count), ct.byref(stats))
            assert code == 1 and count.value == 0 and all(v == 0xA5A5A5A5 for v in roots)
        records += [{'kind': kind, 'status': 'PASS'} for kind in
                    ('native-term-limit', 'native-null-context', 'native-null-metadata',
                     'native-witness-high-bits', 'native-witness-count', 'native-null-witnesses')]
        with ThreadPoolExecutor(max_workers=4) as pool:
            answers = list(pool.map(lambda _: (p.produce(packed), c.check(packed, witnesses)), range(12)))
        assert all(a == produced and b == checked for a, b in answers)
        records.append({'kind': 'concurrent-reuse', 'calls': 24, 'status': 'PASS'})
    for native, call in ((p, lambda: p.produce(packed)), (c, lambda: c.check(packed, witnesses))):
        native.close()
        try:
            call()
        except RuntimeError:
            records.append({'kind': 'closed-' + native.kind, 'status': 'PASS'})
        else:
            raise AssertionError('closed native context accepted')
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'build/correctness.json.gz')
    output = parser.parse_args().output
    if output.exists():
        raise FileExistsError(output)
    receipt = read(HERE / 'build/receipt.json')
    for name, expected in receipt['sources'].items():
        assert sha(HERE / name) == expected
    for name, expected in receipt['binaries'].items():
        assert sha(HERE / 'build' / name) == expected
    plan = read(HERE / 'plan.json')
    corpus = list(cases(plan))
    truths = {name: truth_transform(y, polynomials(y, e, terms)) for name, y, e, terms, kind in corpus}
    for name, y, e, terms, kind in corpus:
        if y <= 3:
            assert truths[name] == direct_roots(y, polynomials(y, e, terms))
    report = {'status': 'RUNNING', 'scope': plan['scope'], 'build_receipt_sha256': sha(HERE / 'build/receipt.json'),
              'plan_sha256': sha(HERE / 'plan.json'),
              'corpus_sha256': hashlib.sha256(json.dumps(corpus, separators=(',', ':')).encode()).hexdigest(),
              'controls': [], 'guards': [], 'candidate_id': None,
              'online_speedup': None, 'timing_eligible': False}
    optimized = {}
    for sanitizer in (False, True):
        with ExitStack() as stack:
            workspaces = {}
            for index, (name, y, e, terms, kind) in enumerate(corpus):
                if (y, e) not in workspaces:
                    workspaces[y, e] = (stack.enter_context(Native(y, e, kind='producer', sanitizer=sanitizer)),
                                        stack.enter_context(Native(y, e, kind='checker', sanitizer=sanitizer)))
                p, c = workspaces[y, e]
                packed = Packed(y, e, terms)
                produced = p.produce(packed)
                assert produced['code'] == 0, (name, produced)
                witnesses = produced['witnesses']
                checked = c.check(packed, witnesses)
                assert checked['code'] == 0 and checked['roots'] == truths[name], (name, checked)
                independent = python_checker(y, polynomials(y, e, terms), witnesses)
                assert independent.roots == truths[name]
                assert checked['stats']['rank'] == independent.rank
                assert bool(checked['stats']['inconsistent']) == independent.inconsistent
                assert checked['stats']['assignments'] == independent.candidates
                assert c.check(packed, ())['roots'] == truths[name]
                assert c.check(packed, tuple(reversed(witnesses)))['roots'] == truths[name]
                assert c.check(packed, witnesses + witnesses)['roots'] == truths[name]
                record = {'name': name, 'shape': [y, e], 'kind': kind, 'producer': produced, 'checker': checked}
                if sanitizer:
                    assert record == optimized[name], name
                else:
                    optimized[name] = record
                report['controls'].append({**record, 'sanitizer': sanitizer})
                if (index + 1) % 1000 == 0:
                    print('CONTROLS_PASS', sanitizer, index + 1, flush=True)
        report['guards'].append({'sanitizer': sanitizer, 'records': controls(sanitizer)})
    report.update(status='PASS', systems=len(corpus), runs=len(report['controls']),
                  source_sha256={str(p.relative_to(HERE)): sha(p) for p in [HERE / 'plan.json',
                      HERE / 'fixtures/frozen-controls.json', *HERE.glob('*.py')]})
    for name, expected in receipt['sources'].items():
        assert sha(HERE / name) == expected
    for name, expected in receipt['binaries'].items():
        assert sha(HERE / 'build' / name) == expected
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), mtime=0))
    print('NATIVE_PARTIAL_PASS', report['systems'], 'systems', report['runs'], 'runs', flush=True)


if __name__ == '__main__':
    main()
