#!/usr/bin/env python3
"""Bind the later independent full-base replay to immutable v1 rows."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = json.loads((HERE / 'measurements.json').read_text())
    replay_path = HERE / 'full_base_replay.json'
    replay = json.loads(replay_path.read_text())
    assert replay['status'] == 'PASS'
    by_k = {record['K']: record for record in replay['records']}
    assert set(by_k) == {600, 800}
    out = []
    for row in rows:
        k = row['effective_columns']
        assert by_k[k]['point_and_label_rows_checked'] == 166 * k
        assert by_k[k]['base_sha256'] == sha(HERE / 'runs' / f'K{k}' / 'base.jsonl')
        out.append({**row, 'full_base_replay_sha256': sha(replay_path),
                    'full_base_replay_status': 'PASS'})
    with (HERE / 'measurements_v2.json').open('x') as file:
        json.dump(out, file, indent=2, sort_keys=True)
        file.write('\n')
    print(json.dumps({'status': 'PASS', 'rows': len(out),
                      'full_base_replay_sha256': sha(replay_path)}))


if __name__ == '__main__':
    main()
