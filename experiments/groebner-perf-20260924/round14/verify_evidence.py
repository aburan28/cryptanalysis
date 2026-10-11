"""Verify the live experiment inventory and audit exact historical measurements."""
import hashlib
import gzip
import json
from pathlib import Path

from audit import main

HERE = Path(__file__).resolve().parent


def verify():
    inventory = json.loads((HERE/'results/inventory.json').read_text())
    for name, expected in inventory.items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==expected, name
    interruption = json.loads((HERE/'results/interruption.json').read_text())
    raw = (HERE/'results'/interruption['artifact']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==interruption['sha256']
    partial = json.loads(gzip.decompress(raw))
    assert partial.get('status')!='RECORDED'
    assert len(partial['rows'])==interruption['retained_rows']==118
    assert sum(len(row['order']) for row in partial['rows'])==interruption['retained_attempts']==354
    assert not interruption['counted_in_completed_comparisons']
    for name, source in partial['source_snapshot'].items():
        assert hashlib.sha256(source.encode()).hexdigest()==partial['source_sha256'][name]
    for row in partial['rows']:
        for arm in row['order']:
            assert row[arm]['result'].get('verified')
            assert sum(row[arm]['phases_ns'].values())==row[arm]['wall_ns']
    main()


if __name__ == '__main__':
    verify()
