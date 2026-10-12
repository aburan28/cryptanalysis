"""Opt-in GPU affine projection with the unchanged independent round48 checker."""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PRIOR = HERE
CHECKER = HERE.parent / 'round48'
ACCEPTED = HERE.parent / 'round44'
sys.path.insert(0, str(PRIOR))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


accepted_checker = load('gpu_projection49_checker44', ACCEPTED / 'checker_base.py')
producer = load('gpu_projection49_producer44', PRIOR / 'normalized.py')
# Bind the temporary setup checker as well as the producer. A comparator
# may already have imported another module named checker_base.
producer.Checker = accepted_checker.Checker
query_base = load('gpu_projection49_query44', PRIOR / 'normalized_query.py')
# Pin the producer factory even when another experimental normalized module
# was already imported by a comparator in this process. This baseline module
# is local to this adapter's independently loaded query class.
query_base.baseline.Basis = producer.Basis
native = load('gpu_projection49_independent_checker48', CHECKER / 'independent_checker.py')
Checker = native.Checker


class ProjectionQuery(query_base.NormalizedQuery):
    def __init__(self, n, mod, b, m, ell, *, backend='cpu', sanitizer=False,
                 partial=True, symmetry=True, transform="full", transform_audit_test=False, identity="dense", identity_audit_test=False):
        if type(symmetry) is not bool:
            raise ValueError('symmetry must be bool')
        super().__init__(n, mod, b, m, ell, backend=backend,
                         sanitizer=sanitizer, partial=partial)
        try:
            replacement = Checker(2 * ell, ell, n, sanitizer=sanitizer,
                                  symmetry=symmetry, transform=transform,
                                  transform_audit_test=transform_audit_test, identity=identity,
                                  identity_audit_test=identity_audit_test)
        except Exception:
            self.close()
            raise
        previous = self.basis.checker
        self.basis.checker = self.checker = replacement
        self.basis.verifier_path = replacement.path
        previous.close()

    def solve(self, target):
        answer = super().solve(target)
        answer['query_arm'] = 'gpu-affine-witnesses-' + self.backend
        return answer

# Compatibility name for the unchanged adversarial symmetry test harness.
IdentityQuery = TransformQuery = SymmetryQuery = ProjectionQuery
