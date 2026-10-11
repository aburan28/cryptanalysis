"""Unchanged producer/checker calls with either legacy or leased packed input."""
import ctypes as C
import importlib.util
from pathlib import Path
import sys
from input_plan import BorrowedInput,InputWorkspace
HERE=Path(__file__).resolve().parent
P=HERE.parent
sys.path.insert(0,str(P/'round11'))
from packed_proof import anf_from_equations
VARIANTS=('baseline','indexed')
TOP_NAMES=('calls','reductions','irreducible_heads','deferred_terms','zero_rows','output_pivots','skipped_reducer_pivots')
COLUMN_NAMES=('indexed_matrices','fallback_matrices','columns','peak_columns','converted_terms')
class TopStats(C.Structure):_fields_=[(name,C.c_uint64) for name in TOP_NAMES]
class ColumnStats(C.Structure):_fields_=[(name,C.c_uint64) for name in COLUMN_NAMES]
class Query:
    def __init__(self,sanitizer=False,variant='indexed'):
        if variant not in VARIANTS:raise ValueError('unknown producer variant')
        spec=importlib.util.spec_from_file_location('leased_input60_'+variant,P/'round11/packed_proof.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.HERE=P/'round58/build'/variant
        original_owner=module.InputOwner
        def owner(nvars,equations,value):
            if isinstance(value,BorrowedInput):return value.validate(nvars,equations,module.PackedInput)
            return original_owner(nvars,equations,value)
        # Each Query owns a separate module namespace. Its factory is immutable
        # after construction, so no per-call global mutation or shared monkey
        # patch can race with another query or alter the historical adapter.
        module.InputOwner=owner
        self._view_type=module.PackedInput
        self.base=module.PackedProof(sanitizer=sanitizer)
        self.binary_sha256=self.base.binary_sha256
        for label,kind in (('top',TopStats),('column',ColumnStats)):
            size=getattr(self.base.producer,'producer_'+label+'_stats_size');size.restype=C.c_uint64
            assert size()==C.sizeof(kind)
            getattr(self.base.producer,'producer_'+label+'_stats').restype=C.POINTER(kind)
    def workspace(self,nvars,equations,support):
        return InputWorkspace(nvars,equations,support,view_type=self._view_type)
    def compute(self,*args,**kwargs):
        result=self.base.compute(*args,**kwargs)
        for label,names in (('top',TOP_NAMES),('column',COLUMN_NAMES)):
            stats=getattr(self.base.producer,'producer_'+label+'_stats')().contents
            result[label+'_stats']={name:getattr(stats,name) for name in names}
        return result
