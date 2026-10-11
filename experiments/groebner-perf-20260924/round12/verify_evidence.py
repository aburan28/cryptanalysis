"""Check the retained inventory and original profiler receipts before auditing."""
import hashlib
import json
from pathlib import Path

from audit import main

HERE = Path(__file__).resolve().parent


def verify():
    inventory = json.loads((HERE / 'results/inventory.json').read_text())
    for name, digest in inventory.items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest, name
    formatting = json.loads((HERE / 'results/formatting-build-receipt.json').read_text())
    measured = json.loads((HERE / 'results/build-receipt.json').read_text())
    assert formatting['before'] == formatting['after']
    for name, digest in formatting['before'].items():
        assert measured['binaries'][name] == digest
    for directory in (HERE / 'profile', HERE / 'profile/first'):
        receipt = json.loads((directory / 'receipt.json').read_text())
        assert hashlib.sha256((directory / 'profile.py').read_bytes()).hexdigest() == receipt['profile_script_sha256']
        assert receipt['source_sha256'] == hashlib.sha256((HERE.parent / 'round5/native_f4.cpp').read_bytes()).hexdigest()
        assert receipt['result_status'] == 'inconclusive'
        assert receipt['returncode'] == 3 and not receipt['timed_out']
        assert json.loads((directory / 'stdout.json').read_text())['status'] == 'inconclusive'
    main()


if __name__ == '__main__':
    verify()
