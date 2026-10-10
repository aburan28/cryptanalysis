"""Emit one complete-query measurement for the isolated benchmark service."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--early-mode', type=int, choices=(0, 1), required=True)
    parser.add_argument('--expected-proof-sha', required=True)
    parser.add_argument('--expected-assignment', type=int, required=True)
    args = parser.parse_args()
    root = args.reference_root.resolve()
    earlier = root/'experiments/groebner-perf-20260924'
    sys.path.insert(0, str(earlier/'round112'))
    spec = importlib.util.spec_from_file_location('isolated_panel112', earlier/'round112/panel.py')
    panel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(panel)
    from early_query import Query
    from common import digest
    panel.previous.Query = lambda **kwargs: Query(early_mode=args.early_mode, **kwargs)
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
                and proof_sha == args.expected_proof_sha)
    # Context.run starts at target-dependent coefficient borrowing and stops
    # after original-equation and curve replay. Setup and this digest are outside.
    fields = dict(online_ms=f"{row['wall_ns']/1_000_000:.9f}",
                  verified=int(verified), case=args.case,
                  fixture_sha=digest(case),
                  target_x=case['target_x'], mod=case['mod'], b=case['b'],
                  m=case['m'], nvars=case['nvars'],
                  status=result['status'], proof_sha=proof_sha)
    print(' '.join(f'{key}={value}' for key, value in fields.items()), flush=True)


if __name__ == '__main__':
    main()
