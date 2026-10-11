"""Deferred-tail variants with unchanged independent algebraic checking."""
import ctypes as C
import importlib.util
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent/'round11'
sys.path.insert(0,str(P))
from packed_proof import anf_from_equations
VARIANTS=('prior','chain','top_new','top_all','chain_top_new','chain_top_all',
          'filter','chain_filter','filter_top','chain_filter_top')
NAMES=('calls','reductions','irreducible_heads','deferred_terms','zero_rows',
       'output_pivots','skipped_reducer_pivots')
class TopStats(C.Structure): _fields_=[(name,C.c_uint64) for name in NAMES]
class Query:
    def __init__(self,variant,sanitizer=False):
        if variant not in VARIANTS: raise ValueError('unknown variant')
        spec=importlib.util.spec_from_file_location('deferred_tail56_'+variant,P/'packed_proof.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.HERE=HERE/'build'/variant
        self.base=module.PackedProof(sanitizer=sanitizer)
        self.variant=variant
        self.binary_sha256=self.base.binary_sha256
        lib=self.base.producer
        lib.producer_top_stats_size.restype=C.c_uint64
        assert lib.producer_top_stats_size()==C.sizeof(TopStats)
        lib.producer_top_stats.restype=C.POINTER(TopStats)
    def compute(self,*args,**kwargs):
        result=self.base.compute(*args,**kwargs)
        stats=self.base.producer.producer_top_stats().contents
        result['top_stats']={name:getattr(stats,name) for name in NAMES}
        return result
