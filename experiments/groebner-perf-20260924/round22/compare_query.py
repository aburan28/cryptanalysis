"""Four explicit arms; production CPU dispatch is unchanged."""
from contextlib import AbstractContextManager
import sys
from coefficient_query import HERE, GPUQuery as CoefficientQuery, Curve, GF2n, Point

_path = sys.path[:]
try:
    sys.path.insert(0,str(HERE.parent/'round19'))
    from gpu_query import GPUQuery as TiledQuery
finally:
    sys.path[:] = _path

ARMS = ('cpu','tiled','coeff','coeff-poll')


class GPUQuery(AbstractContextManager):
    def __init__(self,*shape,arm='cpu',**kwargs):
        if arm not in ARMS: raise ValueError('unknown comparison arm')
        self.arm = arm
        if arm in ('cpu','tiled'):
            self.delegate = TiledQuery(*shape,arm='cpu' if arm=='cpu' else 'gpu-blocking',**kwargs)
        else:
            self.delegate = CoefficientQuery(*shape,arm='gpu-poll' if arm=='coeff-poll' else 'gpu-blocking',**kwargs)

    def __getattr__(self,name):
        return getattr(self.delegate,name)

    def solve(self,target):
        result = self.delegate.solve(target)
        result['query_arm'] = self.arm
        return result

    def __exit__(self,*args):
        self.delegate.close()
