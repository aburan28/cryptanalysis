"""Opt-in producer transform using the unchanged, separately loaded round66 checker."""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load('shared68_reference66', HERE.parent / 'round66/adapter.py')
inherited = load('shared68_adapter66', HERE.parent / 'round66/adapter.py')
producer = load('shared68_producer', HERE / 'build/normalized.py')
Checker, scheduling = inherited.Checker, inherited.scheduling
producer.Checker = inherited.ProducerChecker
producer.Basis = scheduling.basis_class(producer.Basis)
# Each adapter load owns this factory chain. A separately loaded round66
# comparator keeps its original producer and its own checker context.
query_factory = inherited
for _ in range(5):
    query_factory = query_factory.base
assert query_factory.HERE.name == 'round49'
query_factory.query_base.baseline.Basis = producer.Basis
sys.path.insert(0, str(HERE))


class ProjectionQuery(inherited.ProjectionQuery):
    def __init__(self, *args, producer_transform='cpu', **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.basis.producer.configure_producer_transform(producer_transform)
        except BaseException:
            self.close()
            raise

    def solve(self, target):
        answer = super().solve(target)
        answer['query_arm'] = 'shared-producer-transform-' + self.basis.producer.producer_transform + '-' + self.backend
        return answer


IdentityQuery = TransformQuery = SymmetryQuery = ProjectionQuery
