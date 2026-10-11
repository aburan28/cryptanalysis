"""Freeze the exact N41 target-conditioned support census before its run."""

import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INPUT = ROOT/'n131_w18_four_pairs/native_join/native_input.txt'
FIXTURE = ROOT/'n41_transport_cubic_s8_20261011/fixture.json'
HELPER = ROOT.parent/'koblitz-s5-invariant-20260924/three_pair_s7_native.cpp'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    fixture = json.loads(FIXTURE.read_text())
    assert fixture['status'] == 'PASS_TRANSPORTED_N41_PUBLIC_EIGHT_SLOT_WITNESS'
    assert fixture['public_target_original'] == [1458168294740, 1672312028033]
    assert fixture['public_target_transported'] == [920359962848, 755404565011]
    runtime = json.loads((HERE/'sage_runtime_info.json').read_text())
    assert runtime['status'] == 'verified'
    sources = {'projection.cpp': HERE/'projection.cpp',
               'projection_native': HERE/'projection_native',
               'input.txt': INPUT, 'fixture.json': FIXTURE,
               'three_pair_s7_native.cpp': HELPER,
               'sage_runtime_info.json': HERE/'sage_runtime_info.json',
               'freeze.py': HERE/'freeze.py'}
    record = {'status': 'FROZEN_BEFORE_COMPLETE_N41_TARGET_FIBER',
              'candidate_id': None, 'curve_id': fixture['curve_id'],
              'field': 'GF(2)[t]/(t^41+t^3+1)',
              'subgroup_order': 549756390943,
              'target_original': fixture['public_target_original'],
              'target_transported': fixture['public_target_transported'],
              'source_transport': '1+Frobenius',
              'source_rotations': fixture['rotations'],
              'actual_union_points_B': 256, 'folded_columns_K': 26,
              'source_points_per_slot': 64, 'summands': 8,
              'workers': 1, 'setup_cap_seconds': 120,
              'online_cap_seconds': 120, 'rss_cap_bytes': 4*1024**3,
              'host': {'system': platform.system(), 'machine': platform.machine(),
                       'release': platform.release()},
              'compiler': subprocess.check_output(['clang++','--version'], text=True).splitlines()[0],
              'compile_flags': ['-std=c++17','-O3','-Wall','-Wextra'],
              'source_sha256': {name: sha(path) for name, path in sources.items()}}
    (HERE/'protocol.json').write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': record['status'], 'source_sha256': record['source_sha256']}))


if __name__ == '__main__':
    main()
