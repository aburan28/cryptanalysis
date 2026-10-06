"""Check the retained source/evidence inventory before auditing paired runs."""
import hashlib
import json
from pathlib import Path

from audit import main

HERE = Path(__file__).resolve().parent


def verify():
    inventory = json.loads((HERE / 'results/inventory.json').read_text())
    for name, digest in inventory.items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest, name
    main()


if __name__ == '__main__':
    verify()
