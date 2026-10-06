"""Explicit independent-checker transform selection over the unchanged producer."""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load('device65_adapter54', HERE.parent / 'round54/adapter.py')
native = load('device65_checker', HERE / 'independent_checker.py')
Checker = native.Checker
producer, scheduling = base.producer, base.scheduling


class ProducerChecker(Checker):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('symmetry', False)
        super().__init__(*args, **kwargs)


producer.Checker = ProducerChecker
base.base.base.base.base.Checker = Checker
sys.path.insert(0, str(HERE))


class ProjectionQuery(base.ProjectionQuery):
    def __init__(self, *args, transform_backend='cpu', **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.checker.configure_transform_backend(transform_backend)
        except BaseException:
            self.close()
            raise

    def solve(self, target):
        answer = super().solve(target)
        answer['query_arm'] = 'independent-transform-' + self.checker.transform_backend + '-' + self.backend
        return answer


IdentityQuery = TransformQuery = SymmetryQuery = ProjectionQuery
