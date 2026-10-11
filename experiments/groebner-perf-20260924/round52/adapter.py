"""Opt-in independent partial coefficient locality; unchanged round51 producer."""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load('local52_adapter51', HERE.parent / 'round51/adapter.py')
native = load('local52_checker', HERE / 'independent_checker.py')
Checker = native.Checker
producer, accepted_checker = base.producer, base.accepted_checker


class ProducerChecker(Checker):
    def __init__(self, *args, **kwargs):
        # Preserve the prior direct-producer checker contract: every tagged
        # record is independently reconstructed, including symmetry copies.
        kwargs.setdefault('symmetry', False)
        super().__init__(*args, **kwargs)


# Every loaded adapter owns private factories; the accepted comparator stays
# bound to its old checker even when both modules are used in one process.
producer.Checker = ProducerChecker
base.base.Checker = Checker
sys.path.insert(0, str(HERE))


class ProjectionQuery(base.ProjectionQuery):
    def __init__(self, *args, partial_coefficients='local', **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.checker.configure_partial_coefficients(partial_coefficients)
        except Exception:
            self.close()
            raise

    def solve(self, target):
        answer = super().solve(target)
        answer['query_arm'] = 'partial-coefficient-locality-' + self.backend
        return answer


IdentityQuery = TransformQuery = SymmetryQuery = ProjectionQuery
