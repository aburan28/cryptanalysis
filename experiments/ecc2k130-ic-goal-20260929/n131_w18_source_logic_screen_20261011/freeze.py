"""Freeze source and workload for the exact W18 source-logic census."""

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    path = HERE/'protocol.json'
    if path.exists():
        raise FileExistsError(path)
    record = {'status': 'FROZEN_BEFORE_SOURCE_LOGIC_SCREEN',
              'candidate_id': None,
              'curve_id': 'EC1N131Ckb1heb5f1998f20b',
              'source_dimension': 18,
              'random_orders': 30,
              'permutation_seed': 20261011,
              'workers': 1,
              'wall_cap_seconds': 120,
              'rss_cap_bytes': 4*1024**3,
              'platform': platform.platform(),
              'head': subprocess.check_output(['git','rev-parse','HEAD'],
                                              cwd=ROOT,text=True).strip(),
              'utc': datetime.now(timezone.utc).isoformat(),
              'source_sha256': {name: run.sha(source)
                                for name, source in run.source_paths().items()},
              'input_law': 'Exact W18 rational-mask table; invalidity ANF and 30 fixed-seed random root-to-leaf orders plus the current order.'}
    path.write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': record['status'],
                      'protocol_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
