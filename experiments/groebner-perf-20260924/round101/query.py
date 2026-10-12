"""Fresh leased coefficients through an opt-in reusable Macaulay layout."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('leased95_for101', P/'round95/query.py')
previous = importlib.util.module_from_spec(spec)
_import_path = sys.path[:]
try:
    spec.loader.exec_module(previous)
finally:
    # Legacy modules prepend their own helper directories. Keep that lookup
    # local to their import so a full checkout cannot shadow round101 helpers.
    sys.path[:] = _import_path
module = previous
while module is not None:
    module.HERE = HERE
    if hasattr(module, 'abi'):
        module.abi.HERE = HERE
    module = getattr(module, 'previous', None)
abi = previous.abi
PackedDescentPlan = previous.PackedDescentPlan
DenseInput = previous.previous.DenseInput
MatrixStats = previous.previous.MatrixStats
LayoutStats = previous.previous.LayoutStats
ARMS = ('baseline', 'fresh2', 'reused2', 'reused3')


class Query(previous.Query):
    def __init__(self, *, sanitizer=False, arm='baseline', checker='release-live'):
        if arm not in ARMS:
            raise ValueError('unknown Macaulay query arm')
        super().__init__(sanitizer=sanitizer, arm=checker)
        self.arm = arm
        self.dense_lib = self.lib
        suffix = ('-ubsan' if sanitizer else '') + ('.dylib' if sys.platform == 'darwin' else '.so')
        path = HERE/'build'/('sparse_macaulay'+suffix)
        library = C.CDLL(str(path))
        for name in ('macaulay_layout_create', 'macaulay_layout_destroy',
                     'macaulay_layout_support', 'macaulay_apply', 'macaulay_view',
                     'macaulay_result_destroy', 'macaulay_error', 'macaulay_stats_size',
                     'macaulay_layout_stats_size'):
            new, old = getattr(library, name), getattr(self.lib, name)
            new.argtypes, new.restype = old.argtypes, old.restype
        assert library.macaulay_stats_size() == C.sizeof(MatrixStats)
        assert library.macaulay_layout_stats_size() == C.sizeof(LayoutStats)
        self.lib = library
        self.binary_sha256[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def compute(self, *args, **kwargs):
        result = super().compute(*args, **kwargs)
        result['macaulay_policy'] = self.arm
        return result
