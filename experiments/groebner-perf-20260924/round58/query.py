"""Column-indexed F4 with the unchanged independent native certificate checker."""
import ctypes as C
import importlib.util
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent/'round11'
sys.path.insert(0,str(P))
from packed_proof import anf_from_equations
VARIANTS=('baseline','indexed','tiny')
TOP_NAMES=('calls','reductions','irreducible_heads','deferred_terms','zero_rows','output_pivots','skipped_reducer_pivots')
COLUMN_NAMES=('indexed_matrices','fallback_matrices','columns','peak_columns','converted_terms')
class TopStats(C.Structure):_fields_=[(name,C.c_uint64) for name in TOP_NAMES]
class ColumnStats(C.Structure):_fields_=[(name,C.c_uint64) for name in COLUMN_NAMES]
class Query:
    def __init__(self,variant,sanitizer=False):
        if variant not in VARIANTS:raise ValueError('unknown variant')
        spec=importlib.util.spec_from_file_location('column58_'+variant,P/'packed_proof.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.HERE=HERE/'build'/variant
        self.base=module.PackedProof(sanitizer=sanitizer)
        self.variant=variant;self.binary_sha256=self.base.binary_sha256
        for label,kind in (('top',TopStats),('column',ColumnStats)):
            size=getattr(self.base.producer,'producer_'+label+'_stats_size');size.restype=C.c_uint64
            assert size()==C.sizeof(kind)
            getattr(self.base.producer,'producer_'+label+'_stats').restype=C.POINTER(kind)
    def compute(self,*args,**kwargs):
        result=self.base.compute(*args,**kwargs)
        for label,names in (('top',TOP_NAMES),('column',COLUMN_NAMES)):
            stats=getattr(self.base.producer,'producer_'+label+'_stats')().contents
            result[label+'_stats']={name:getattr(stats,name) for name in names}
        return result
