"""Use the unchanged packed wrapper/checker with independently built producers."""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'round11'
sys.path.insert(0, str(PREVIOUS))
from packed_proof import anf_from_equations


def load(variant='combined', *, sanitizer=False):
    if variant not in ('baseline', 'pivots', 'ordered', 'combined'):
        raise ValueError('unknown reduction variant')
    # A private module instance avoids changing the previous wrapper's globals.
    spec = importlib.util.spec_from_file_location('reduction_' + variant, PREVIOUS / 'packed_proof.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    directory = HERE / 'build' / variant / 'build'
    suffix = ('-ubsan' if sanitizer else '') + ('.dylib' if sys.platform == 'darwin' else '.so')
    # The wrapper resolves both libraries from HERE/build; symlinks share the
    # independent checker binary without sharing any per-query numeric state.
    checker = directory / ('native_checker' + suffix)
    if not checker.exists():
        checker.symlink_to('../../' + checker.name)
    module.HERE = directory.parent
    return module.PackedProof(sanitizer=sanitizer)
