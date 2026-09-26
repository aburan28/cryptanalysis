"""Use the unchanged packed wrapper/checker with independently built producers."""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'round11'
sys.path.insert(0, str(PREVIOUS))
from packed_proof import anf_from_equations


def load(variant='cached', *, sanitizer=False):
    if variant not in ('baseline', 'ordered', 'frontier', 'indexed', 'cached', 'cached_indexed'):
        raise ValueError('unknown reduction variant')
    # A private module instance avoids changing the previous wrapper's globals.
    spec = importlib.util.spec_from_file_location('reduction_' + variant, PREVIOUS / 'packed_proof.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    directory = HERE / 'build' / variant / 'build'
    module.HERE = directory.parent
    return module.PackedProof(sanitizer=sanitizer)
