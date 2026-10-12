"""Emit a verified complete-query timing for the isolated benchmark service."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--arm', choices=('scratch', 'bitset'), required=True)
    parser.add_argument('--expected-proof-sha', required=True)
    parser.add_argument('--expected-assignment', type=int, required=True)
    parser.add_argument('--expected-work', type=int, required=True)
    parser.add_argument('--expected-check-work', type=int, required=True)
    args = parser.parse_args()
    root = args.reference_root.resolve()
    base = root / 'experiments/groebner-perf-20260924'
    os.environ['GROEBNER_PHASE_REFERENCE_ROOT'] = str(root)
    os.environ['GROEBNER_F4_REFERENCE_ROOT'] = str(root)
    sys.path.insert(0, str(base / 'round112'))
    spec = importlib.util.spec_from_file_location('isolated_panel112', base / 'round112/panel.py')
    panel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(panel)
    sys.path.insert(0, str(base / ('round118' if args.arm == 'scratch' else 'round119')))
    if args.arm == 'scratch':
        from scratch_query import Query
    else:
        from bitset_query import Query
    from common import digest
    panel.previous.Query = lambda **kwargs: Query(early_mode=1, **kwargs)
    context = panel.previous.Context(args.case)
    try:
        row = context.run(args.case, 'matrix-block4')
    finally:
        for layout in context.layouts.values():
            layout.close()
    case, result = context.cases[args.case], row['result']
    proof = result.get('proof')
    proof_sha = hashlib.sha256(proof.serialized()).hexdigest() if proof else 'none'
    verified = (result.get('status') == 'solved' and result.get('verified') is True
                and result.get('complete') is True
                and result.get('reference_equations_and_curve_replay') is True
                and result.get('assignment') == args.expected_assignment
                and result.get('work') == args.expected_work
                and result.get('check_work') == args.expected_check_work
                and proof_sha == args.expected_proof_sha)
    phases = result['phases']
    seeded = [attempt for attempt in result['attempts'] if attempt['kind'] == 'seeded-f4']
    f4_ns = sum(attempt['native_phases']['f4_ns'] for attempt in seeded)
    fields = dict(online_ms=f"{row['wall_ns']/1_000_000:.9f}",
                  verified=int(verified), case=args.case, fixture_sha=digest(case),
                  target_x=case['target_x'], mod=case['mod'], b=case['b'],
                  m=case['m'], nvars=case['nvars'], status=result['status'],
                  proof_sha=proof_sha, work=result['work'], check_work=result['check_work'],
                  matrix_ms=f"{phases['matrix_ns']/1_000_000:.9f}",
                  f4_ms=f"{f4_ns/1_000_000:.9f}",
                  checker_ms=f"{phases['checker_ns']/1_000_000:.9f}")
    # Context.run owns the target-dependent interval and ends after original
    # equation and curve replay. The proof digest and this output are outside.
    print(' '.join(f'{key}={value}' for key, value in fields.items()), flush=True)
    if not verified:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
