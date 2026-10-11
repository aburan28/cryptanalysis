"""Independent exhaustive review of the restricted three-point RR chart.

Reproduce from the repository root (no SAT package required):

    python ecc2k130/codegen/testnagaoreview.py --out review.json

The immutable JSON output uses schema ``nagao-independent-review-v1``. Its
``counts`` record all signed triples examined, eligible triples, successfully
interpolated certificates, checks against each IR frontend, and rejected
wrong-target-sign mutations. It records source hashes and runtime provenance.
Elapsed time is diagnostic only; this is not an attack-cost measurement.

Independent derivation: L(4O) has basis 1,x,y,x^2. A divisor consisting of
P1,P2,P3,-R with four distinct abscissas and group sum O determines a function
in L(4O). Its x^2 coefficient is nonzero, since otherwise its pole order is at
most three. Its y coefficient is nonzero, since a quadratic in x cannot have
four distinct x roots. Thus the restricted monic chart covers every tested
triple. Direct group additions supply the target before interpolation; neither
IR system is used to decide which triples are valid.

No type hints, camelCase identifiers, no itertools (project convention).
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import curves
import field
import indexcalc
import nagaodecomp


def runReview():
    onb = field.Onb(5)
    curve = curves.Curve(onb)
    base, _ = indexcalc.factorBase(onb, curve, 5)
    xs = sorted(base)
    programs = {variant: nagaodecomp.buildSystem(5, onb.n, 5, variant)
                for variant in nagaodecomp.FORMULATIONS}
    counts = {'all_signed_triples': 0, 'supported_triples': 0,
              'certificates': 0, 'checked_ir_formulations': 0,
              'bad_sign_mutations_rejected': 0}
    started = time.monotonic()
    for first in range(len(xs)):
        for second in range(first + 1, len(xs)):
            for third in range(second + 1, len(xs)):
                for mask in range(8):
                    counts['all_signed_triples'] += 1
                    coords = [xs[first], xs[second], xs[third]]
                    points = [curve.neg(base[x]) if mask >> index & 1 else base[x]
                              for index, x in enumerate(coords)]
                    target = None
                    for point in points:
                        target = curve.add(target, point)
                    if target is None or onb.toCoords(target[0]) in coords:
                        continue
                    counts['supported_triples'] += 1
                    decoded = nagaodecomp.certificateForPoints(
                        onb, curve, points, target)
                    if decoded is None:
                        raise ArithmeticError('eligible triple has no RR certificate: %r'
                                              % (coords,))
                    counts['certificates'] += 1
                    values = nagaodecomp.inputValues(5, decoded,
                        onb.toCoords(target[0]), onb.toCoords(target[1]))
                    for variant, (prog, roots) in programs.items():
                        if any(prog.evaluate(values, roots)):
                            raise ArithmeticError('%s rejects a valid certificate: %r'
                                                  % (variant, coords))
                        counts['checked_ir_formulations'] += 1
                    negative = curve.neg(target)
                    if negative != target:
                        if nagaodecomp.reconstructWitness(onb, curve, decoded,
                                                         negative) is not None:
                            raise ArithmeticError('certificate accepted the wrong target sign')
                        counts['bad_sign_mutations_rejected'] += 1
    code = Path(__file__).resolve().parent
    sources = ['testnagaoreview.py', 'nagaodecomp.py', 'decomp.py',
               'field.py', 'curves.py', 'indexcalc.py', 'ir.py', 'build.py']
    return {
        'schema': 'nagao-independent-review-v1',
        'review': 'independent exhaustive full-factor-base signed-triple interpolation at GF(2^5)',
        'command': [sys.executable] + sys.argv,
        'python': platform.python_version(),
        'field_degree': 5,
        'weight': 5,
        'factor_base_abscissas': len(xs),
        'source_sha256': {name: hashlib.sha256((code / name).read_bytes()).hexdigest()
                          for name in sources},
        'counts': counts,
        'elapsed_seconds': time.monotonic() - started,
        'limits': 'exhaustive restricted toy correctness only; no solver-work or attack-cost measurement',
        'valid': True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.out.exists():
        parser.error('output already exists; choose a new immutable evidence path')
    result = runReview()
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    with arguments.out.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'valid': result['valid'], 'counts': result['counts'],
                      'out': str(arguments.out)}))


if __name__ == '__main__':
    main()
