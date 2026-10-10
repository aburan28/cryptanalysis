"""Bounded conductor search in E: y^2+xy=x^3+1 over F_(2^m).

The curve is defined over F_2 and its geometric endomorphism order contains
tau with tau^2+tau+2=0, a maximal order (discriminant -7). Base extension
preserves this maximal geometric order, hence f_End(E)=1. Candidate destination
orders are arithmetic strata; no target curve or isogeny is constructed here.
"""

import argparse
import json
import math
import platform
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path

from conductor_navigation import checked_factors, inventory


def koblitz_invariants(m):
    if m < 1:
        raise ValueError('extension degree must be positive')
    # tau^m = a+b*tau, Norm(tau)=2, Trace(tau)=-1.
    a, b = 1, 0
    for _ in range(m):
        a, b = -2 * b, a - b
    q = 1 << m
    trace = 2 * a - b
    conductor = abs(b)
    assert a*a - a*b + 2*b*b == q
    assert trace*trace - 4*q == -7*conductor*conductor
    return {'m': m, 'q': q, 'trace': trace, 'curve_order': q+1-trace,
            'frobenius_conductor': conductor,
            'source_endomorphism_conductor': 1,
            'source_model': 'y^2 + xy = x^3 + 1 over F_(2^m)'}


def factor_with_certificate(n, timeout):
    """GNU factor is a proposer. Recompose and prove each <2^64 prime."""
    if n == 1:
        return {}, 'complete', '1'
    try:
        proc = subprocess.run(['factor', str(n)], capture_output=True, text=True,
                              timeout=timeout, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return None, 'unresolved_' + ('timeout' if isinstance(exc, subprocess.TimeoutExpired)
                                      else 'factor_unavailable'), type(exc).__name__
    raw = proc.stdout.strip()
    try:
        prefix, values = raw.split(':', 1)
        primes = [int(word) for word in values.split()]
        factors = dict(Counter(primes))
        if proc.returncode or int(prefix) != n:
            raise ValueError('factor process failed')
        checked_factors(n, factors)
    except (ValueError, IndexError):
        return None, 'unresolved_factor_or_primality', raw
    return factors, 'complete', raw


def kronecker_minus7(p):
    if p == 7:
        return 0
    if p == 2:
        return 1  # -7 = 1 mod 8
    r = pow((-7) % p, (p - 1) // 2, p)
    return -1 if r == p - 1 else 1


def search(min_degree=13, max_degree=131, min_gap_bits=20, factor_timeout=2.0):
    if min_degree < 1 or max_degree < min_degree or max_degree > 131:
        raise ValueError('supported sweep: 1 <= min_degree <= max_degree <= 131')
    if min_gap_bits < 1 or factor_timeout <= 0:
        raise ValueError('positive threshold and timeout required')
    rows = []
    for m in range(min_degree, max_degree + 1):
        inv = koblitz_invariants(m)
        start = time.monotonic()
        factors, status, raw = factor_with_certificate(inv['frobenius_conductor'], factor_timeout)
        row = {**{k: str(v) if isinstance(v, int) and k != 'm' else v
                  for k, v in inv.items()},
               'factorization_status': status, 'factor_command_output': raw,
               'factor_elapsed_ms': round((time.monotonic()-start)*1000, 3),
               'factors': None if factors is None else {str(p): e for p, e in factors.items()},
               'gap_candidates': [],
               'source_curve_id': ('EC1N131Ckb1h136f03e58c98' if m == 131 else None),
               'source_curve_id_evidence': (
                   'experiments/ic-candidate-catalog/curves.yaml:ecc2k130_pb' if m == 131 else None),
               'destination_curve_id': None,
               'destination_map_status': 'unknown', 'measured_dlp_advantage': None}
        if factors is not None:
            nav = inventory(characteristic=2, q=inv['q'], trace=inv['trace'],
                            field_discriminant=-7,
                            frobenius_conductor=inv['frobenius_conductor'],
                            factors=factors, allowed_primes=[], source_conductor=1,
                            source_evidence='tau^2+tau+2=0; fundamental discriminant -7')
            for p in factors:
                if p.bit_length() < min_gap_bits:
                    continue
                stratum = next(s for s in nav['strata'] if s['order_conductor'] == str(p))
                row['gap_candidates'].append({
                    'prime': str(p), 'prime_bits': p.bit_length(),
                    'log2_prime_approx': round(math.log2(p), 6),
                    'order_discriminant': stratum['order_discriminant'],
                    'kronecker_minus7': kronecker_minus7(p),
                    'class_number_ratio_to_maximal': str(p - kronecker_minus7(p)),
                    'source_to_stratum_vertical_steps': 1,
                    'destination_order_only': True,
                })
        rows.append(row)
    hits = sorted(({'m': row['m'], **hit} for row in rows for hit in row['gap_candidates']),
                  key=lambda hit: (-int(hit['prime']), hit['m']))
    return {'schema': 'koblitz-conductor-gap-search-v1',
            'scope': 'E:y^2+xy=x^3+1 over F_(2^m); order strata, no target curves constructed',
            'method': 'exact tau recurrence; GNU factor candidate; deterministic prime checks <2^64',
            'parameters': {'min_degree': min_degree, 'max_degree': max_degree,
                           'min_gap_bits': min_gap_bits, 'factor_timeout_seconds': factor_timeout},
            'environment': {'python': platform.python_version(), 'factor_path': shutil.which('factor')},
            'counts': {'degrees': len(rows), 'complete_factorizations': sum(
                r['factorization_status']=='complete' for r in rows),
                       'unresolved_factorizations': sum(
                           r['factorization_status']!='complete' for r in rows),
                       'hits': len(hits)},
            'ranked_hits': hits, 'rows': rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--min-degree', type=int, default=13)
    ap.add_argument('--max-degree', type=int, default=131)
    ap.add_argument('--min-gap-bits', type=int, default=20)
    ap.add_argument('--factor-timeout', type=float, default=2.0)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    result = search(args.min_degree, args.max_degree, args.min_gap_bits, args.factor_timeout)
    with args.output.open('x') as fh:
        json.dump(result, fh, indent=2)
        fh.write('\n')
    print(json.dumps(result['counts']))


if __name__ == '__main__':
    main()
