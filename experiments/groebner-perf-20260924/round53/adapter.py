"""Independent preparation interface over the unchanged round51 producer."""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load('prepared53_adapter52', HERE.parent/'round52/adapter.py')
native = load('prepared53_checker', HERE/'independent_checker.py')
scheduling = load('prepared53_scheduling', HERE/'scheduling.py')
Checker = native.Checker
producer, accepted_checker = base.producer, base.accepted_checker


class ProducerChecker(Checker):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('symmetry', False)
        super().__init__(*args, **kwargs)


producer.Checker = ProducerChecker
base.base.base.Checker = Checker
producer.Basis = scheduling.basis_class(producer.Basis)
base.base.base.query_base.baseline.Basis = producer.Basis
sys.path.insert(0, str(HERE))


class ProjectionQuery(base.ProjectionQuery):
    def __init__(self, *args, preparation='serial', **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.basis.configure_preparation(preparation)
        except BaseException:
            self.close()
            raise

    def solve(self, target):
        answer = super().solve(target)
        answer['query_arm'] = 'prepared-independent-checker-' + self.backend
        return answer


IdentityQuery = TransformQuery = SymmetryQuery = ProjectionQuery
