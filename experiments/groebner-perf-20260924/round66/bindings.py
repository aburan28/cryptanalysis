"""Bind unchanged native dependencies and the generated full checker separately."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bindings():
    spec = importlib.util.spec_from_file_location('constant66_bindings65', HERE.parent/'round65/bindings.py')
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    result = prior.bindings()
    kernel_receipt = HERE/'build/receipt.json'
    result[str(kernel_receipt)] = sha(kernel_receipt)
    kernel = json.loads(kernel_receipt.read_text())
    for name, digest in kernel['sources'].items():
        path = HERE/name
        assert sha(path) == digest, path
        result[str(path)] = digest
    for name, digest in kernel['binaries'].items():
        path = HERE/'build'/name
        assert sha(path) == digest, path
        result[str(path)] = digest
    receipt = HERE/'build/native-receipt.json'
    result[str(receipt)] = sha(receipt)
    value = json.loads(receipt.read_text())
    for name, digest in value['sources'].items():
        path = (HERE.parents[2] if name.startswith('experiments/') else HERE.parent)/name
        assert sha(path) == digest, path
        result[str(path)] = digest
    for group in ('generated', 'binaries'):
        for name, digest in value[group].items():
            path = HERE/'build'/name
            assert sha(path) == digest, path
            result[str(path)] = digest
    return result
