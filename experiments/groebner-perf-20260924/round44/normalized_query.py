"""Complete query with invariant normalization setup and fresh solving/checking."""
import importlib.util
import sys
from pathlib import Path
from normalized import Basis
HERE = Path(__file__).resolve().parent
DEPENDENCIES = HERE.parent

for version in (32, 17, 37):
    sys.path.insert(0, str(DEPENDENCIES / ('round' + str(version))))
spec = importlib.util.spec_from_file_location('partial_affine_query_base', DEPENDENCIES / 'round37/fixed_width_query.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
baseline.Basis = Basis


class NormalizedQuery(baseline.FixedWidthQuery):
    def __init__(self, n, mod, b, m, ell, *, backend='cpu', sanitizer=False, partial=True):
        super().__init__(n, mod, b, m, ell, backend=backend, sanitizer=sanitizer)
        try:
            self.basis.producer.configure_partial(partial)
            self.basis.producer.configure_normalization(mod)
        except Exception:
            self.close()
            raise

    def solve(self, target):
        answer = super().solve(target)
        answer['query_arm'] = 'quadratic-partial-affine-' + self.basis.producer.backend + ('-enabled' if self.basis.producer.partial_enabled else '-disabled')
        return answer
