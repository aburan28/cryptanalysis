#!/usr/bin/env python3
"""Archive the exact N83 K600/K800/K899 compact-orbit point sets cited by IC1."""

import hashlib
import argparse
import json
from pathlib import Path

import fbarchive

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / 'experiments/n83-compact-orbit-size-sweep-20261012'
EXP_K899 = ROOT / 'experiments/n83-compact-orbit-k899-20261012'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_doc(k):
    source = EXP_K899 if k == 899 else EXP
    candidate_path = source / f'candidate_K{k}.json'
    base_path = source / 'runs' / f'K{k}' / 'base.jsonl'
    replay_path = source / 'full_base_replay.json'
    candidate = json.loads(candidate_path.read_text())
    base = json.loads(base_path.read_text())
    replay = json.loads(replay_path.read_text())
    factor_base = candidate['factor_base']
    assert replay['status'] == 'PASS'
    matching = [row for row in replay['records'] if row['K'] == k]
    assert len(matching) == 1
    assert matching[0]['base_sha256'] == sha(base_path)
    assert matching[0]['point_and_label_rows_checked'] == 166 * k
    assert factor_base['ordered_base_dump_sha256'] == sha(base_path)
    assert factor_base['actual_usable_points'] == len(base['factor_base_point_coordinates']) == 166 * k
    assert factor_base['effective_columns'] == len(base['factor_base_representatives']) == k
    points = sorted(base['factor_base_point_coordinates'],
                    key=lambda pair: (int(pair[0]), int(pair[1])))
    assert len({tuple(point) for point in points}) == len(points)
    assert fbarchive.sha256_hex(points) == factor_base['enumerated_set_sha256']
    record = {
        'curve_id': candidate['curve']['curve_id'],
        'construction': factor_base['recipe'],
        'candidate_factor_base': factor_base,
        'actual_usable_point_count': 166 * k,
        'geometric_point_count': 166 * k,
        'strict_subgroup_point_count': 166 * k,
        'effective_columns': k,
        'enumerated_set_sha256': factor_base['enumerated_set_sha256'],
        'quotient_rule': 'sign+frobenius',
    }
    return {
        'schema': fbarchive.SCHEMA,
        'field': candidate['field'],
        'curve': candidate['curve'],
        'isogeny': 'none',
        'factor_base': record,
        'factor_base_sha256': fbarchive.sha256_hex(record),
        'points': points,
        'points_encoding': 'sorted [x,y] decimal strings in polynomial basis',
        'point_columns': None,
        'column_representatives': base['factor_base_representatives'],
        'recipe': {'n': 83, 'family': 'compactorbit', 'l': None, 'seed': 0,
                   'columns': k, 'raw_x_start': 1},
        'source_sha256': {
            'candidate_manifest': sha(candidate_path),
            'ordered_base_dump': sha(base_path),
            'independent_full_base_replay': sha(replay_path),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    preserve_crlf = b'\r\n' in fbarchive.INDEX.read_bytes()
    for k in (600, 800, 899):
        doc = build_doc(k)
        if args.verify_only:
            matching = [row for row in fbarchive.read_index()
                        if row['factor_base_sha256'] == doc['factor_base_sha256']]
            assert len(matching) == 1
            row = matching[0]
            path = fbarchive.HERE / row['path']
            assert fbarchive.decompress(path) == fbarchive.canonical(doc).encode()
        else:
            row = fbarchive.store(doc, chunk_bytes=32 * 1024 * 1024)
        assert fbarchive.verify_row({key: str(value) for key, value in row.items()},
                                    rebuild=False, rebuild_max_points=300) == []
        print(json.dumps({'K': k, 'archive': row['path'],
                          'enumerated_set_sha256': row['enumerated_set_sha256'],
                          'storage': row['storage']}))
    if not args.verify_only and preserve_crlf:
        current = fbarchive.INDEX.read_bytes()
        assert b'\r' not in current
        fbarchive.INDEX.write_bytes(current.replace(b'\n', b'\r\n'))


if __name__ == '__main__':
    main()
