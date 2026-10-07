#!/usr/bin/env python3
"""Freeze scattered-pair orbit entries using the earlier compact-pos fixture."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent


def sha256(data): return hashlib.sha256(data).hexdigest()


def unit_maps(digits, unit):
    digit_ids = {pair: i for i, pair in enumerate(digits, 1)}
    return [[0] + [18 * ((pattern - 1) // 18) +
                   digit_ids[unit(*digits[(pattern - 1) % 18], code)]
                   for pattern in range(1, 55)] for code in range(6)]


def scalar_blocks(order, eigen, scalar, digits, residue, representatives, recode, block_pattern):
    _, a, b = min(representatives(order, eigen, scalar), key=lambda row: row[0])
    seq = recode(a, b, digits, residue)
    patterns = [block_pattern((seq[i:i + 3] + [0] * 3)[:3]) for i in range(0, len(seq), 3)]
    return [(i, v) for i, v in enumerate(patterns) if v]


def freeze(repo, output):
    sys.path.insert(0, str(repo))
    from make_tau3_fused import build, recode, block_pattern, unit
    from run import representatives

    digits, residue, *_ = build()
    maps = unit_maps(digits, unit)
    fixture_path = repo / 'compact-pos-inputs.json'
    panel_path = repo / 'compact-pos-panel.json'
    fixture = json.loads(fixture_path.read_text())
    panel = json.loads(panel_path.read_text())
    old_rows = {(r['case_id'], r['mode']): r for r in panel['rows']}
    records = []
    for curve, extra_budget, full_slots in [('glv-j0-32', 1372, 1372), ('j0-56', 2401, 2401)]:
        freq = Counter()
        scalar_files = []
        count = 0
        for case in fixture['cases']:
            if case['curve']['name'] != curve: continue
            content = (repo / case['scalar_file']).read_bytes()
            assert sha256(content) == case['scalar_file_sha256']
            scalar_files.append({'file': case['scalar_file'], 'sha256': sha256(content)})
            order = case['curve']['order']
            eigen = (order - int(old_rows[(case['id'], 'pos-compact')]['fields']['endo_lambda'])) % order
            for (scalar,) in struct.iter_unpack('<Q', content):
                count += 1
                blocks = scalar_blocks(order, eigen, scalar, digits, residue,
                                       representatives, recode, block_pattern)
                residual = [(i, u) for i, u in blocks if not any(j != i and j // 2 == i // 2 for j, _ in blocks)]
                for x, (i, u) in enumerate(residual):
                    for j, v in residual[x+1:]:
                        freq[(i, j, min((mapping[u], mapping[v]) for mapping in maps))] += 1
        selected = sorted(freq, key=lambda k: (-freq[k], k))[:extra_budget]
        records.append({'curve': curve, 'training_scalars': count, 'full6_point_entries': full_slots,
                        'extra_budget': extra_budget, 'extra_point_entries': len(selected),
                        'total_point_entries': full_slots + len(selected),
                        'selection': 'descending frequency of cross-pair residual singles after fixed-six baseline; ties by key',
                        'scalar_files': scalar_files,
                        'entries': [[i, j, u, v] for i, j, (u, v) in sorted(selected)]})
    source = Path(__file__).read_bytes()
    design = {'schema': 1, 'status': 'frozen_retrospective_design',
              'cpu_timing_claim': None,
              'mathematics': 'width-three tau NAF, fixed six-step orbit table plus selected scattered cross-pair orbits, exact maximum cardinality matching',
              'source_sha256': sha256(source),
              'training_fixture_sha256': sha256(fixture_path.read_bytes()),
              'training_panel_sha256': sha256(panel_path.read_bytes()),
              'records': records}
    content = json.dumps(design, sort_keys=True, separators=(',', ':')).encode() + b'\n'
    if output.exists() and output.read_bytes() != content:
        raise ValueError('frozen design changed')
    output.write_bytes(content)
    return {'design_sha256': sha256(content),
            'records': [{k: r[k] for k in ('curve','training_scalars','full6_point_entries','extra_point_entries','total_point_entries')} for r in records]}


if __name__ == '__main__':
    if len(sys.argv) != 3: raise SystemExit('usage: make_tau3_scatter_design.py REPO OUTPUT')
    print(json.dumps(freeze(Path(sys.argv[1]), Path(sys.argv[2])), sort_keys=True))
