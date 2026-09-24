"""Bound the absolute dispatch overhead on unchanged Sage paths."""
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_hardware

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


intent = json.loads((HERE / 'intent-control-v3.json').read_text())
assert digest(binary_hardware.__file__) == intent['candidate_source_sha256']
out = HERE / 'control-001'
out.mkdir(exist_ok=False)
(out / 'execution.json').write_text(json.dumps({
    'intent_sha256': digest(HERE / 'intent-control-v3.json'),
    'script_sha256': digest(__file__),
}, indent=2) + '\n')
rows = []
for index, case in enumerate(intent['cases']):
    field = GF(2**case['degree'], 'z', impl='ntl')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    base, attempts = generate(curve, 128, intent['seed_base'] + index)
    points = [base[i % len(base)] for i in range(case['points'])]
    phi = curve.frobenius_isogeny(case['power'] % case['degree'])
    expected = [phi(point) for point in points]
    plan = binary_hardware.FrobeniusPlan(curve, case['power'], backend='auto')
    assert plan._auto_requested
    original = binary_hardware.frobenius_points
    calls = []

    def tracked(*args):
        calls.append(1)
        return original(*args)

    binary_hardware.frobenius_points = tracked
    try:
        actual = plan.apply(points)
        assert actual == expected and calls == [1]
        assert plan.last_backend == 'sage' and plan._auto_plan is None
    finally:
        binary_hardware.frobenius_points = original
    full = []
    for _ in range(8):
        start = time.perf_counter_ns()
        actual = plan.apply(points)
        assert actual == expected
        del actual
        full.append((time.perf_counter_ns() - start) / 1e9)
    samples = []
    repetitions = intent['predicate_repetitions']
    for batch in range(intent['batches']):
        order = (False, True) if batch % 2 else (True, False)
        result = {}
        for enabled in order:
            plan._auto_requested = enabled
            matched = 0
            start = time.perf_counter_ns()
            for _ in range(repetitions):
                if (plan._auto_requested and type(points) in (list, tuple)
                        and len(points) >= 4096 and plan.degree in (67, 131)
                        and plan.power == 65 and plan.codec == 'native-ntl'):
                    matched += 1
            elapsed = (time.perf_counter_ns() - start) / 1e9
            assert matched == 0
            result[str(enabled)] = elapsed / repetitions
        samples.append(result)
    plan.close()
    delta = statistics.median(s['True'] - s['False'] for s in samples)
    row = {'case': case, 'samples': samples, 'branch_delta_seconds': delta,
           'representative_full_seconds': statistics.median(full),
           'branch_fraction': delta / statistics.median(full),
           'direct_sage_function_calls': len(calls),
           'all_outputs_exact': True, 'fixture_attempts': attempts,
           'candidate_source_sha256': digest(binary_hardware.__file__)}
    (out / f'cell-{index:02d}.json').write_text(json.dumps(row, indent=2) + '\n')
    rows.append(row)
    print(case['degree'], case['points'], case['power'],
          f'branch delta {delta*1e6:.3f} us',
          f'fraction {100*row["branch_fraction"]:.5f}%', flush=True)
(out / 'summary.json').write_text(json.dumps({
    'cells': [{'case': row['case'], 'branch_delta_seconds': row['branch_delta_seconds'],
               'branch_fraction': row['branch_fraction']} for row in rows],
    'all_outputs_exact': all(row['all_outputs_exact'] for row in rows),
}, indent=2) + '\n')
