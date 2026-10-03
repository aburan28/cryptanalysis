"""Opt-in lazy host nullspace construction; unchanged GPU kernel and independent checker."""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Each load creates private factories. Changing this module's library directory
# cannot change a separately imported round49 comparator or its query factories.
base = load('lazy51_adapter49', HERE.parent / 'round49/adapter.py')
producer, Checker, accepted_checker = base.producer, base.Checker, base.accepted_checker
producer.HERE = HERE
# Keep this experiment's sibling harnesses ahead of the loaded legacy modules.
sys.path.insert(0, str(HERE))


class ProjectionQuery(base.ProjectionQuery):
    def solve(self, target):
        answer = super().solve(target)
        answer['query_arm'] = 'lazy-metal-nullspace-' + self.backend
        return answer


IdentityQuery = TransformQuery = SymmetryQuery = ProjectionQuery
