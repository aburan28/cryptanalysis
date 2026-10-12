"""Bind every executed native dependency and its recorded source files."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bindings():
    result = {}
    for version in (20, 23, 31, 32, 33, 34, 35, 36, 37, 38, 44, 48, 49, 51):
        folder = HERE.parent / f'round{version}'
        receipt = folder / 'build/receipt.json'
        result[str(receipt)] = sha(receipt)
        value = json.loads(receipt.read_text())
        for name, expected in value.get('sources', value.get('source_sha256', {})).items():
            path = (HERE.parents[2] if name.startswith('experiments/') else HERE.parent) / name
            assert sha(path) == expected, path
            result[str(path)] = expected
        for name, expected in value['binaries'].items():
            path = (HERE.parents[2] / name) if name.startswith('experiments/') else folder / 'build' / name
            assert sha(path) == expected, path
            result[str(path)] = expected
        for name, expected in value.get('generated', {}).items():
            path = folder / 'build' / name
            assert sha(path) == expected, path
            result[str(path)] = expected
    return result
