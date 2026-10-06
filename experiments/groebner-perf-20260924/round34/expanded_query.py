"""Complete public-point query with fresh descent and independent branch proof."""
import sys
import threading

from expanded_baseline import Basis, HERE
sys.path.insert(0, str(HERE.parent/'round32'))
from quadratic import BaselineQuery, QuadraticQuery
from full_query import complete_query
from native_descent import NativeDescent
sys.path.insert(0, str(HERE.parent/'round17'))
from public_replay import replay
from wide_descent import NativeDescent as WideDescent


class ExpandedQuery:
    def __init__(self, n, mod, b, m, ell, *, backend='cpu', sanitizer=False):
        if type(m) is not int or m != 3 or type(ell) is not int or not 1 <= ell <= 10:
            raise ValueError('three coordinate blocks, residual dimension 1..10')
        self.shape = n, mod, b, m, ell
        self.backend = backend
        self._lock, self._closed = threading.Lock(), False
        self.basis = self.descent = self.replay = self.checker = None
        try:
            self.replay = replay(n, mod, b, 'native-or-python', sanitizer=sanitizer)
            self.basis = Basis(2*ell, ell, n, backend=backend, sanitizer=sanitizer)
            self.checker = self.basis.checker
            descent = NativeDescent if m*ell <= 20 else WideDescent
            self.descent = descent(n, mod, b, m, ell, sanitizer=sanitizer)
        except Exception:
            self.close()
            raise

    def solve(self, target):
        return complete_query(self, target, 'quadratic-expanded-'+self.backend)

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                for component in (self.basis, self.descent, self.replay):
                    if component is not None:
                        component.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
