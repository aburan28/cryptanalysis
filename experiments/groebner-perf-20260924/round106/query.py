"""Opt-in selected-row producer; independent checker and query boundary retained."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('query105_for106', P/'round105/query.py')
previous = importlib.util.module_from_spec(spec)
_path = sys.path[:]
try:
    spec.loader.exec_module(previous)
finally:
    sys.path[:] = _path
module = previous
while module is not None:
    module.HERE = HERE
    if hasattr(module, 'abi'):
        module.abi.HERE = HERE
    module = getattr(module, 'previous', None)
abi = previous.abi
PackedDescentPlan = previous.PackedDescentPlan
ARMS = ('f4-quotient', 'matrix-quotient', 'matrix-minimal')


class Query(previous.Query):
    def __init__(self, *, sanitizer=False, arm='matrix-minimal', **kwargs):
        if arm not in ARMS:
            raise ValueError('unknown minimal Macaulay arm')
        self.minimal_arm = arm
        super().__init__(sanitizer=sanitizer,
            arm='f4-quotient' if arm.startswith('f4-') else 'matrix-quotient', **kwargs)
        if arm == 'matrix-minimal':
            suffix = ('-ubsan' if sanitizer else '')+('.dylib' if sys.platform == 'darwin' else '.so')
            path = HERE/'build'/('minimal_macaulay'+suffix)
            library = C.CDLL(str(path))
            for name in ('macaulay_layout_create', 'macaulay_layout_destroy',
                         'macaulay_layout_support', 'macaulay_apply', 'macaulay_view',
                         'macaulay_result_destroy', 'macaulay_error', 'macaulay_stats_size',
                         'macaulay_layout_stats_size'):
                new, old = getattr(library, name), getattr(self.lib, name)
                new.argtypes, new.restype = old.argtypes, old.restype
            assert library.macaulay_stats_size() == self.lib.macaulay_stats_size()
            assert library.macaulay_layout_stats_size() == self.lib.macaulay_layout_stats_size()
            # Every layout/result is created and destroyed by this same library.
            self.lib = library
            self.binary_sha256[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def compute(self, *args, **kwargs):
        result = super().compute(*args, **kwargs)
        result['back_substitution_policy'] = ('minimal-rows' if self.minimal_arm == 'matrix-minimal'
            else 'all-pivots' if self.minimal_arm == 'matrix-quotient' else 'f4-control')
        return result
