"""Compare one Metal host change against both independently verified CPU paths."""
from contextlib import AbstractContextManager
import importlib.util
import sys

from mapped_query import HERE, GPUQuery as MappedQuery, Curve, GF2n, Point

spec = importlib.util.spec_from_file_location('frozen_coefficient_query', HERE.parent/'round22/coefficient_query.py')
coefficient = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coefficient)
_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent/'round23'))
    from sparse_checker import SparseQuery
finally:
    sys.path[:] = _path

ARMS = ('cpu', 'sparse-cpu', 'coeff', 'mapped', 'mapped-poll')


class GPUQuery(AbstractContextManager):
    def __init__(self, *shape, arm='cpu', **kwargs):
        if arm not in ARMS:
            raise ValueError('unknown mapping comparison arm')
        self.arm = arm
        if arm in ('cpu', 'sparse-cpu'):
            self.delegate = SparseQuery(*shape, arm='cpu' if arm=='cpu' else 'sparse', **kwargs)
        elif arm == 'coeff':
            self.delegate = coefficient.GPUQuery(*shape, arm='gpu-blocking', **kwargs)
        else:
            self.delegate = MappedQuery(*shape, arm='gpu-poll' if arm=='mapped-poll' else 'gpu-blocking', **kwargs)

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def solve(self, target):
        result = self.delegate.solve(target)
        result['query_arm'] = self.arm
        result['gpu_device'] = getattr(self.delegate.checker, 'device_name', None)
        return result

    def __exit__(self, *args):
        self.delegate.close()
