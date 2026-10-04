"""Bind the full unchanged verifier graph and generated producer sources/native code."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bindings():
    spec = importlib.util.spec_from_file_location('shared68_bindings66', HERE.parent / 'round66/bindings.py')
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    result = prior.bindings()
    path = HERE / 'build/receipt.json'
    result[str(path)] = sha(path)
    receipt = json.loads(path.read_text())
    for name, digest in receipt['sources'].items():
        path = HERE.parent / name
        assert sha(path) == digest, path
        result[str(path)] = digest
    for group in ('generated', 'binaries'):
        for name, digest in receipt[group].items():
            path = HERE / 'build' / name
            assert sha(path) == digest, path
            result[str(path)] = digest
    return result
