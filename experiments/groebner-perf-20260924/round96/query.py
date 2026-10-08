"""Expose thread-local diagnostic counters after the unchanged complete solve."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent
spec=importlib.util.spec_from_file_location('query95_for96',P/'round95/query.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
module=previous
while module is not None:
    module.HERE=HERE
    if hasattr(module,'abi'):module.abi.HERE=HERE
    module=getattr(module,'previous',None)
abi=previous.abi;PackedDescentPlan=previous.PackedDescentPlan
ARMS={'baseline':None,'profiled':None}
STAGES=('decode','compute','canonical','multiply','add','ordered_multiple','ordered_add','normal','install','chain','symbolic','column','packed','sparse','compaction')
spec=importlib.util.spec_from_file_location('counters62_for96',P/'round62/query.py')
counters=importlib.util.module_from_spec(spec);spec.loader.exec_module(counters)
CHAIN_NAMES=('mode','candidate_pairs','scanned_leaders','eligible_chains','pruned_pairs','represented_pairs_skipped','field_pairs','probes','probe_zero','probe_nonzero','probe_soft_limits','probe_aborted','probe_work','peak_probe_nodes','cache_hits','product_hits','failed_probe_hits','represented_entries','failed_entries','cache_saturated','raw_zero_pairs','overhead_work')
class ChainStats(C.Structure):_fields_=[(n,abi.U64) for n in CHAIN_NAMES]
class WorkProfile(C.Structure):
    _fields_=[(n,abi.U64*len(STAGES)) for n in ('exclusive','inclusive','calls')]+[(n,abi.U64) for n in ('overflow','active','depth','peak_depth')]

class Query(previous.Query):
    def __init__(self,*,sanitizer=False,arm='baseline'):
        if arm not in ARMS:raise ValueError('unknown profile arm')
        super().__init__(sanitizer=sanitizer,arm='legacy');self.arm=arm
        if arm=='profiled':
            suffix=('-ubsan' if sanitizer else '')+('.dylib' if sys.platform=='darwin' else '.so')
            path=HERE/'build'/('profiled_producer'+suffix);library=C.CDLL(str(path))
            for name in ('produce_packed','producer_view','producer_destroy','producer_error'):
                new=getattr(library,name);old=getattr(self.base.producer,name)
                new.argtypes=old.argtypes;new.restype=old.restype
            self.base.producer=library;self.binary_sha256[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            self.structures=dict(top=counters.TopStats,column=counters.ColumnStats,scratch=counters.ScratchStats,packed=counters.PackedStats,chain=ChainStats,work=WorkProfile)
            for label,kind in self.structures.items():
                size=getattr(library,'producer_'+label+'_stats_size');size.argtypes=[];size.restype=abi.U64
                assert size()==C.sizeof(kind)
                get=getattr(library,'producer_'+label+'_stats');get.argtypes=[];get.restype=C.POINTER(kind)

    def compute(self,*args,**kwargs):
        result=super().compute(*args,**kwargs);result['instrumented']=self.arm=='profiled'
        if self.arm=='profiled':
            profile={}
            for label,kind in self.structures.items():
                stats=getattr(self.base.producer,'producer_'+label+'_stats')().contents
                profile[label]={name:(dict(zip(STAGES,map(int,getattr(stats,name)))) if label=='work' and name in ('exclusive','inclusive','calls') else int(getattr(stats,name))) for name,_ in kind._fields_}
            result['profile']=profile
        return result
