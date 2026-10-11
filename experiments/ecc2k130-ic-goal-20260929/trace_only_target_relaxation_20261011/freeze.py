"""Freeze the public N41 trace-only fourth-pair relaxation."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    sources = {'input': ROOT/'n131_w18_four_pairs/native_join/native_input.txt',
               'fixture': ROOT/'n41_transport_cubic_s8_20261011/fixture.json',
               'producer': HERE/'relaxation_sage.py',
               'runtime': HERE/'sage_runtime_info.json',
               'freezer': HERE/'freeze.py'}
    f = json.loads(sources['fixture'].read_text())
    assert f['status'] == 'PASS_TRANSPORTED_N41_PUBLIC_EIGHT_SLOT_WITNESS'
    assert json.loads(sources['runtime'].read_text())['status'] == 'verified'
    record = {'status': 'FROZEN_N41_THREE_EXACT_PAIRS_FOURTH_TRACE_RELAXATION',
              'candidate_id': None, 'curve_id': f['curve_id'],
              'field': 'GF(2)[t]/(t^41+t^3+1)',
              'subgroup_order': 549756390943,
              'target_original': f['public_target_original'],
              'target_transported': f['public_target_transported'],
              'source_rotations': f['rotations'],
              'actual_union_points_B': 256, 'folded_columns_K': 26,
              'exact_pair_groups': [0, 1, 2],
              'fourth_pair_policy': 'any nonexceptional odd-subgroup point with trace(1/x)=0',
              'source_sha256': {name: sha(path) for name, path in sources.items()}}
    (HERE/'protocol.json').write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': record['status'], 'target': record['target_transported']}))


if __name__ == '__main__':
    main()
