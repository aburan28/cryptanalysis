"""Opt-in independent symmetry checker with the unchanged round44 producer."""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / 'round44'
sys.path.insert(0, str(PRIOR))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


accepted_checker = load('symmetry_prior_checker44', PRIOR / 'checker_base.py')
producer = load('symmetry_prior_producer44', PRIOR / 'normalized.py')
# Bind the temporary setup checker as well as the producer. A comparator
# may already have imported another module named checker_base.
producer.Checker = accepted_checker.Checker
query_base = load('symmetry_prior_query44', PRIOR / 'normalized_query.py')
# Pin the producer factory even when another experimental normalized module
# was already imported by a comparator in this process. This baseline module
# is local to this adapter's independently loaded query class.
query_base.baseline.Basis = producer.Basis
from independent_checker import Checker


class SymmetryQuery(query_base.NormalizedQuery):
    def __init__(self, n, mod, b, m, ell, *, backend='cpu', sanitizer=False,
                 partial=True, symmetry=True):
        if type(symmetry) is not bool:
            raise ValueError('symmetry must be bool')
        super().__init__(n, mod, b, m, ell, backend=backend,
                         sanitizer=sanitizer, partial=partial)
        try:
            replacement = Checker(2 * ell, ell, n, sanitizer=sanitizer,
                                  symmetry=symmetry)
        except Exception:
            self.close()
            raise
        previous = self.basis.checker
        self.basis.checker = self.checker = replacement
        self.basis.verifier_path = replacement.path
        previous.close()

    def solve(self, target):
        answer = super().solve(target)
        answer['query_arm'] = 'independent-symmetry-' + self.backend
        return answer
