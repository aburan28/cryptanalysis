"""Opt-in row work reservations over the independently prepared checker."""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load('reservation54_adapter53', HERE.parent/'round53/adapter.py')
native = load('reservation54_checker', HERE/'independent_checker.py')
Checker = native.Checker
producer, accepted_checker, scheduling = base.producer, base.accepted_checker, base.scheduling


class ProducerChecker(Checker):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('symmetry', False)
        super().__init__(*args, **kwargs)


producer.Checker = ProducerChecker
base.base.base.base.Checker = Checker
sys.path.insert(0, str(HERE))


class ProjectionQuery(base.ProjectionQuery):
    def __init__(self, *args, partial_reservation='reserved', **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.checker.configure_partial_reservation(partial_reservation)
        except BaseException:
            self.close()
            raise

    def solve(self, target):
        answer = super().solve(target)
        answer['query_arm'] = 'partial-work-reservation-'+self.backend
        return answer


IdentityQuery = TransformQuery = SymmetryQuery = ProjectionQuery
