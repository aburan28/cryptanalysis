"""Conductor-stratum inventory; does not construct curves or run DLP solvers.

Inputs are supplied ordinary-class invariants and a complete factorization.
Prime factors below 2^64 are checked deterministically. Larger factors require
an upstream certificate adapter (not implemented), rather than probable-prime
promotion. Restricted-walk components here are components of the ORDER graph,
not assertions about connectivity among individual curves in an order.
"""

import argparse
import itertools
import json
from math import isqrt, prod
from pathlib import Path


def prime64(n):
    if not 2 <= n < 2**64:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
        if a % n == 0:
            continue
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def checked_factors(value, factors):
    out = {int(p): int(e) for p, e in factors.items()}
    if len(out) != len(factors) or any(e < 1 or not prime64(p) for p, e in out.items()):
        raise ValueError('need distinct proven prime factors < 2^64 and positive exponents')
    if value < 1 or prod(p**e for p, e in out.items()) != value:
        raise ValueError('incomplete or inconsistent conductor factorization')
    return dict(sorted(out.items()))


def fundamental_discriminant(d):
    if d >= 0 or d % 4 not in (0, 1):
        return False
    rad = d if d % 4 == 1 else d // 4
    if d % 4 == 0 and rad % 4 not in (2, 3):
        return False
    # Bounded exact check; never spend unbounded time factoring a field discriminant.
    if abs(rad) > 10**8:
        raise ValueError('field discriminant exceeds exact squarefree-check scope')
    return all(rad % (p * p) for p in range(2, isqrt(abs(rad)) + 1))


def inventory(*, characteristic, q, trace, field_discriminant,
              frobenius_conductor, factors, allowed_primes,
              source_conductor=None, source_evidence=None, max_strata=4096):
    characteristic, q, trace = int(characteristic), int(q), int(trace)
    dk, fp = int(field_discriminant), int(frobenius_conductor)
    if not prime64(characteristic):
        raise ValueError('characteristic must be a proven prime < 2^64')
    q_part = q
    while q_part > 1 and q_part % characteristic == 0:
        q_part //= characteristic
    if q <= 1 or q_part != 1:
        raise ValueError('q must be a positive power of the characteristic')
    if trace % characteristic == 0:
        raise ValueError('ordinary volcano model does not apply')
    if not fundamental_discriminant(dk) or trace * trace - 4 * q != dk * fp * fp:
        raise ValueError('invalid fundamental discriminant or Frobenius identity')
    fs = checked_factors(fp, factors)
    allowed = sorted(set(int(p) for p in allowed_primes))
    if any(not prime64(p) or p == characteristic for p in allowed):
        raise ValueError('allowed walk degrees must be primes different from characteristic')
    if prod(e + 1 for e in fs.values()) > max_strata:
        raise ValueError('stratum count exceeds explicit inventory limit; no partial enumeration')
    source = None if source_conductor is None else int(source_conductor)
    if source is not None and (source < 1 or fp % source or not source_evidence):
        raise ValueError('source conductor needs divisibility and a nonempty evidence reference')
    blocked_primes = [p for p in fs if p not in allowed]
    def valuations(c):
        result = {}
        for p in fs:
            e, part = 0, c
            while part % p == 0:
                part //= p
                e += 1
            result[str(p)] = e
        return result
    source_levels = None if source is None else valuations(source)
    strata = []
    for exps in itertools.product(*(range(e + 1) for e in fs.values())):
        c = prod(p**e for p, e in zip(fs, exps))
        levels = dict(zip((str(p) for p in fs), exps))
        barriers = None if source is None else [
            {'prime': str(p), 'source_level': source_levels[str(p)],
             'destination_level': levels[str(p)],
             'vertical_steps_required': abs(source_levels[str(p)] - levels[str(p)]),
             'degree_bits': p.bit_length(), 'reason': 'degree_not_in_allowed_walk_set'}
            for p in blocked_primes if source_levels[str(p)] != levels[str(p)]]
        strata.append({
            'order_conductor': str(c), 'order_discriminant': str(dk * c * c),
            'local_levels': levels,
            'restricted_order_component': {str(p): levels[str(p)] for p in blocked_primes},
            'source_separation': 'unknown' if source is None else (
                'separated_by_excluded_prime' if barriers else 'no_conductor_obstruction'),
            'barriers': barriers, 'curve_id': None, 'construction_status': 'not_constructed',
            'map_status': 'unknown', 'measured_advantage': None,
        })
    strata.sort(key=lambda row: int(row['order_conductor']))
    return {
        'schema': 'conductor-navigation-v1',
        'scope': 'order-stratum metadata; no curve-connectivity or computational-hardness proof',
        'characteristic': str(characteristic), 'q': str(q), 'trace': str(trace),
        'field_discriminant': str(dk), 'frobenius_order_conductor': str(fp),
        'frobenius_conductor_factors': {str(p): e for p, e in fs.items()},
        'allowed_walk_primes': [str(p) for p in allowed],
        'source_endomorphism_conductor': None if source is None else str(source),
        'source_conductor_evidence': source_evidence if source is not None else None,
        'strata': strata,
    }


def annotate_summary(summary, allowed_primes):
    """Add metadata to a copy of an existing sweep; retain its raw measurements."""
    summary = json.loads(json.dumps(summary))
    shared = summary['shared_invariants']
    q = int(shared['card']) + int(shared['trace']) - 1
    # This adapter is explicitly for the existing -7 Koblitz sweep.
    fp = int(shared['conductor_Z_pi'])
    nav = inventory(characteristic=2, q=q, trace=shared['trace'], field_discriminant=-7,
                    frobenius_conductor=fp, factors={263: 1, 146505763881528721: 1},
                    allowed_primes=allowed_primes, source_conductor=1,
                    source_evidence='sweep.sage:E0 has the degree-2 endomorphism of discriminant -7')
    by_c = {row['order_conductor']: row for row in nav['strata']}
    for row in summary['levels']:
        row['navigation'] = by_c[str(row['conductor'])]
    summary['conductor_navigation'] = nav
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True,
                    help='invariant manifest or existing sweep with --sweep-summary')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--allowed-primes', type=int, nargs='*', default=[263])
    ap.add_argument('--sweep-summary', action='store_true')
    args = ap.parse_args()
    data = json.loads(args.input.read_text())
    result = (annotate_summary(data, args.allowed_primes) if args.sweep_summary else
              inventory(**data, allowed_primes=args.allowed_primes))
    if args.input.resolve() == args.output.resolve() or args.output.exists():
        ap.error('output must be a new file; historical inputs are never overwritten')
    with args.output.open('x') as fh:
        json.dump(result, fh, indent=2)
        fh.write('\n')


if __name__ == '__main__':
    main()
